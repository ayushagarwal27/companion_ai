"""Builds and compiles the Companion LangGraph graph.

Per /chat turn: country_agent_node answers, maybe_extract_memory_node periodically
persists long-term memory, summarize_conversation_node compacts the checkpointer
once the session gets long. See README.md for the full architecture.
"""

from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.redis import RedisSaver
from langgraph.store.postgres import PostgresStore
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr
from backend.agents.country_agent import country_agent_node, maybe_extract_memory_node, summarize_conversation_node
from backend.config.settings import settings
from backend.state.country_state import CompanionState

graph = StateGraph(CompanionState)
graph.add_node('country_agent_node', country_agent_node)
graph.add_node('maybe_extract_memory_node', maybe_extract_memory_node)
graph.add_node('summarize_conversation_node', summarize_conversation_node)
graph.add_edge(START, 'country_agent_node')
graph.add_edge('country_agent_node', 'maybe_extract_memory_node')
graph.add_edge('maybe_extract_memory_node', 'summarize_conversation_node')
graph.add_edge('summarize_conversation_node', END)

def get_compiled_graph():
    """Open a Redis checkpointer + Postgres store and yield a compiled graph bound to them.

    A generator so it can be driven two ways: as a FastAPI dependency (opens fresh
    connections per request, torn down via the `with` block when the generator is
    closed after the request) via backend.api.dependency.get_graph, or manually driven
    once at startup for a long-lived background instance (see server.py's lifespan,
    which uses this for the idle-session listener).
    """
    # Initialize embeddings for the semantic search
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=SecretStr(settings.openai_api_key))
    
    # Open connections
    with RedisSaver.from_conn_string(settings.redis_url) as checkpointer, \
         PostgresStore.from_conn_string(
             settings.database_url, 
             index={"embed": embeddings, "dims": 1536} # Required for semantic search
         ) as store:
            
            compiled_graph = graph.compile(checkpointer=checkpointer, store=store)
            yield compiled_graph