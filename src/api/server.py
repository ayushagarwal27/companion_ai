"""FastAPI app for the Companion AI chat endpoint.

Three mechanisms keep long-term memory (Postgres) in sync with ongoing sessions
(Redis-checkpointed), none of which block the /chat response:
  1. maybe_extract_memory_node (in the graph) - fires every N turns.
  2. POST /chat/{session_id}/end - explicit flush when a client knows a session is done.
  3. The idle-session listener below - Redis keyspace-expiry driven backstop for
     sessions that end without calling #2.
See README.md for the full picture.
"""

from fastapi import BackgroundTasks, FastAPI, Depends
from src.api.models import UserLLMQueryRequest
from src.api.dependency import get_graph
from src.agents.country_agent import finalize_pending_memory
from src.graph.graph import get_compiled_graph
from src.config.settings import settings
from langchain.messages import HumanMessage
from langgraph.checkpoint.redis import RedisSaver
from langgraph.store.postgres import PostgresStore
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr
from contextlib import asynccontextmanager
import redis.asyncio as redis
import uvicorn
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)

SESSION_ALIVE_PREFIX = "session:alive:"
SESSION_USER_PREFIX = "session:user:"


def _finalize_idle_session(graph, session_id: str, user_id: str) -> None:
    """Sync helper run off the event loop (via asyncio.to_thread) by the idle listener,
    since finalize_pending_memory may invoke a blocking LLM call.
    """
    config = {"configurable": {"thread_id": session_id}}
    snapshot = graph.get_state(config)
    if snapshot and snapshot.values.get("turns_since_extraction", 0) > 0:
        finalize_pending_memory(snapshot.values, user_id, graph.store)
        graph.update_state(config, {"turns_since_extraction": 0})


async def _listen_for_idle_sessions(app: FastAPI) -> None:
    """Subscribes to Redis key-expiry events for session:alive:* marker keys. Each
    /chat call refreshes a session's marker with a short TTL; once it expires without
    being refreshed, the session is idle, so we flush whatever long-term memory the
    periodic in-graph trigger hasn't picked up yet."""
    pubsub = app.state.redis.pubsub()
    await pubsub.psubscribe("__keyevent@*__:expired")

    async for message in pubsub.listen():
        if message.get("type") != "pmessage":
            continue

        key = message["data"]
        if not key.startswith(SESSION_ALIVE_PREFIX):
            continue

        session_id = key[len(SESSION_ALIVE_PREFIX):]
        user_id = await app.state.redis.getdel(f"{SESSION_USER_PREFIX}{session_id}")
        if not user_id:
            continue

        try:
            await asyncio.to_thread(_finalize_idle_session, app.state.bg_graph, session_id, user_id)
        except Exception:
            logger.exception("Failed to finalize idle session %s", session_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run DB/checkpointer migrations, then start the long-lived resources used
    outside the per-request dependency: a Redis client for session-alive markers,
    a background compiled graph for the idle listener, and the listener task itself.
    """
    print("Running database setup...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=SecretStr(settings.openai_api_key))
    with RedisSaver.from_conn_string(settings.redis_url) as checkpointer, \
         PostgresStore.from_conn_string(
             settings.database_url,
             index={"embed": embeddings, "dims": 1536}
         ) as store:
        checkpointer.setup()
        store.setup()
    print("Database setup complete!")

    app.state.redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await app.state.redis.config_set("notify-keyspace-events", "Ex")
    except Exception:
        logger.warning(
            "Could not enable Redis keyspace notifications (CONFIG SET may be disabled on managed Redis). "
            "Idle-session memory flushing will not run until 'notify-keyspace-events' includes 'Ex' is set manually."
        )

    bg_graph_gen = get_compiled_graph()
    app.state.bg_graph = next(bg_graph_gen)
    app.state.idle_listener_task = asyncio.create_task(_listen_for_idle_sessions(app))

    yield

    app.state.idle_listener_task.cancel()
    try:
        await app.state.idle_listener_task
    except asyncio.CancelledError:
        pass
    bg_graph_gen.close()
    await app.state.redis.aclose()


app = FastAPI(title="Companion AI", lifespan=lifespan)


@app.post('/chat')
async def companion(userLLMQueryRequest:UserLLMQueryRequest, background_tasks: BackgroundTasks, graph = Depends(get_graph)):
    """Run one conversation turn and refresh this session's idle-detection marker."""
    session_id = userLLMQueryRequest.session_id or str(uuid.uuid4())
    configurable = {"thread_id": session_id}
    if userLLMQueryRequest.user_id:
        configurable["user_id"] = userLLMQueryRequest.user_id
        configurable["background_tasks"] = background_tasks
    message = HumanMessage(userLLMQueryRequest.query)

    graph_input = {"messages": [message]}
    if userLLMQueryRequest.country:
        graph_input["country"] = userLLMQueryRequest.country

    response = graph.invoke(graph_input, config={"configurable": configurable})

    if userLLMQueryRequest.user_id:
        async with app.state.redis.pipeline() as pipe:
            pipe.set(f"{SESSION_ALIVE_PREFIX}{session_id}", "1", ex=settings.session_idle_seconds)
            pipe.set(f"{SESSION_USER_PREFIX}{session_id}", userLLMQueryRequest.user_id, ex=settings.session_idle_seconds + 60)
            await pipe.execute()

    return {"session_id":session_id,"user_id": userLLMQueryRequest.user_id, "response":response["messages"][-1].content}


@app.post('/chat/{session_id}/end')
async def end_session(session_id: str, user_id: str, background_tasks: BackgroundTasks, graph = Depends(get_graph)):
    """Call when a conversation ends, so any turns not yet picked up by the periodic
    extraction trigger (e.g. a short session) still get saved to long-term memory."""
    config = {"configurable": {"thread_id": session_id}}
    snapshot = graph.get_state(config)

    pending = bool(snapshot and snapshot.values.get("turns_since_extraction", 0) > 0)
    if pending:
        background_tasks.add_task(finalize_pending_memory, snapshot.values, user_id, graph.store)
        graph.update_state(config, {"turns_since_extraction": 0})

    await app.state.redis.delete(f"{SESSION_ALIVE_PREFIX}{session_id}", f"{SESSION_USER_PREFIX}{session_id}")

    return {"session_id": session_id, "pending_memory_extracted": pending}


if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host='127.0.0.1', reload=True, port=8001)
