"""Voice-mode WS connection handling: pipeline construction, session-identity
handshake, and the same disconnect-time memory flush POST /chat/{id}/end
performs for text sessions. See backend/api/server.py for the route that
calls handle_voice_connection, and README.md for the overall memory architecture
this plugs into unchanged.
"""

import asyncio
import logging
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.frameworks.rtvi import RTVIProcessor
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport

from backend.agents.country_agent import finalize_pending_memory
from backend.config.settings import settings
from backend.graph.graph import get_compiled_graph
from backend.voice.background_adapter import BackgroundTasksAdapter
from backend.voice.graph_llm_processor import GraphLLMProcessor
from backend.voice.voices import resolve_voice_id

logger = logging.getLogger(__name__)

SESSION_ALIVE_PREFIX = "session:alive:"
SESSION_USER_PREFIX = "session:user:"


async def handle_voice_connection(app: FastAPI, websocket: WebSocket) -> None:
    """Session identity (session_id/user_id/country) rides on the connect URL's
    query string, not a first app-level message - the Pipecat/RTVI client takes
    over the socket for its own protocol as soon as it connects, so there's no
    window to exchange a plain JSON handshake frame first. The server's side of
    the handshake (telling the client the session_id for a brand-new session) is
    delivered as an RTVI server message once the client signals ready - see the
    on_client_ready handler below.
    """
    params = websocket.query_params
    session_id = params.get("session_id") or str(uuid.uuid4())
    user_id = params.get("user_id") or None
    country = params.get("country") or None
    is_new_session = not params.get("session_id")

    await websocket.accept()

    if not settings.deepgram_api_key or not settings.cartesia_api_key:
        await websocket.close(code=1013, reason="Voice mode is not configured on this server.")
        return

    graph_gen = get_compiled_graph()
    graph = next(graph_gen)
    bg_adapter = BackgroundTasksAdapter()

    async def refresh_idle_markers() -> None:
        if not user_id:
            return
        async with app.state.redis.pipeline() as pipe:
            pipe.set(f"{SESSION_ALIVE_PREFIX}{session_id}", "1", ex=settings.session_idle_seconds)
            pipe.set(f"{SESSION_USER_PREFIX}{session_id}", user_id, ex=settings.session_idle_seconds + 60)
            await pipe.execute()

    # PipelineWorker adds an RTVIProcessor by default (enable_rtvi=True unless we
    # pass our own), but the default on_client_ready handler only marks the bot
    # ready - registering our own handler on the same instance *additionally*
    # tells the client which session_id it's talking to, for a brand-new session
    # where the client doesn't already have one.
    rtvi = RTVIProcessor()

    @rtvi.event_handler("on_client_ready")
    async def _send_session_info(rtvi_processor: RTVIProcessor) -> None:
        await rtvi_processor.send_server_message(
            {"type": "session", "session_id": session_id, "user_id": user_id}
        )

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
            serializer=ProtobufFrameSerializer(),
            allowed_origins=settings.frontend_origins,
        ),
    )
    stt = DeepgramSTTService(api_key=settings.deepgram_api_key)
    tts = CartesiaTTSService(
        api_key=settings.cartesia_api_key,
        settings=CartesiaTTSService.Settings(voice=resolve_voice_id(country)),
    )
    graph_llm = GraphLLMProcessor(
        graph,
        session_id,
        user_id,
        country,
        bg_adapter,
        starting_country=country if is_new_session else None,
        on_turn_complete=refresh_idle_markers,
    )

    pipeline = Pipeline([transport.input(), stt, graph_llm, tts, transport.output()])
    worker = PipelineWorker(pipeline, params=PipelineParams(), rtvi_processor=rtvi)

    try:
        await app.state.voice_runner.add_workers(worker)
        await worker.wait()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Voice session %s ended with an error", session_id)
    finally:
        await _finalize_session(app, graph, session_id, user_id, bg_adapter)
        graph_gen.close()


async def _finalize_session(app: FastAPI, graph, session_id: str, user_id: str | None, bg_adapter: BackgroundTasksAdapter) -> None:
    """Mirrors POST /chat/{session_id}/end's flush, run on voice disconnect instead
    of an explicit call - see backend/api/server.py's end_session for the sibling.
    """
    if bg_adapter.pending:
        await asyncio.gather(*bg_adapter.pending, return_exceptions=True)

    if not user_id:
        return

    config = {"configurable": {"thread_id": session_id}}
    snapshot = graph.get_state(config)
    if snapshot and snapshot.values.get("turns_since_extraction", 0) > 0:
        await asyncio.to_thread(finalize_pending_memory, snapshot.values, user_id, graph.store)
        graph.update_state(config, {"turns_since_extraction": 0})

    await app.state.redis.delete(f"{SESSION_ALIVE_PREFIX}{session_id}", f"{SESSION_USER_PREFIX}{session_id}")
