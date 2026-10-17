"""Bridges Pipecat's frame pipeline to the existing LangGraph conversation graph,
so a voice turn runs through the exact same brain (persona, running summary,
long-term memory, memory-extraction triggers) as a text turn in backend/api/server.py's
POST /chat - see that module's `companion` endpoint for the sibling implementation
this mirrors (same sync-call-in-a-thread + token_callback pattern, different consumer).
"""

import asyncio
from typing import Any, Awaitable, Callable

from langchain.messages import HumanMessage
from pipecat.frames.frames import (
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from backend.voice.background_adapter import BackgroundTasksAdapter

_DONE = object()


class GraphLLMProcessor(FrameProcessor):
    """Runs one graph.invoke() turn per final STT transcript, streaming the
    reply out as TextFrames for the downstream TTS service to speak.
    """

    def __init__(
        self,
        graph: Any,
        session_id: str,
        user_id: str | None,
        country: str | None,
        background_tasks: BackgroundTasksAdapter,
        *,
        starting_country: str | None = None,
        on_turn_complete: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        super().__init__()
        self._graph = graph
        self._configurable: dict[str, Any] = {"thread_id": session_id}
        if user_id:
            self._configurable["user_id"] = user_id
            self._configurable["background_tasks"] = background_tasks
        # Only set on the graph_input of the first turn of a brand-new session -
        # an existing thread already has `country` in its checkpointed state.
        self._pending_country = starting_country
        # Refreshes the same session:alive/session:user idle-detection Redis keys
        # POST /chat refreshes per request (see backend/api/server.py) - called once
        # per completed voice turn so the idle backstop treats both transports alike.
        self._on_turn_complete = on_turn_complete

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            await self._run_turn(frame.text)
        else:
            await self.push_frame(frame, direction)

    async def _run_turn(self, query: str) -> None:
        loop = asyncio.get_running_loop()
        token_queue: asyncio.Queue = asyncio.Queue()

        def on_token(token: str) -> None:
            loop.call_soon_threadsafe(token_queue.put_nowait, token)

        country_for_this_turn = self._pending_country
        self._pending_country = None

        def run_graph():
            try:
                configurable = {**self._configurable, "token_callback": on_token}
                graph_input: dict[str, Any] = {"messages": [HumanMessage(query)]}
                if country_for_this_turn:
                    graph_input["country"] = country_for_this_turn
                return self._graph.invoke(graph_input, config={"configurable": configurable})
            finally:
                loop.call_soon_threadsafe(token_queue.put_nowait, _DONE)

        await self.push_frame(LLMFullResponseStartFrame())
        graph_future = asyncio.ensure_future(asyncio.to_thread(run_graph))
        while True:
            item = await token_queue.get()
            if item is _DONE:
                break
            # LLMTextFrame (not plain TextFrame) so the RTVI observer recognizes
            # these as LLM-generated text and emits them via "bot-llm-text" - TTS
            # synthesis is unaffected either way (it isinstance-checks the base
            # TextFrame), but a plain TextFrame doesn't match the observer's
            # isinstance(frame, LLMTextFrame) check for that event.
            await self.push_frame(LLMTextFrame(item))
        await graph_future  # surfaces any exception from graph.invoke
        await self.push_frame(LLMFullResponseEndFrame())
        if self._on_turn_complete is not None:
            await self._on_turn_complete()
