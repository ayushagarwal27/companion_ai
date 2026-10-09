from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.redis import RedisSaver
from langgraph.store.postgres import PostgresStore
from langchain_openai import OpenAIEmbeddings
from src.agents.country_agent import country_agent_node
from src.config.settings import settings

graph = StateGraph(MessagesState)
graph.add_node('country_agent_node', country_agent_node)
graph.add_edge(START, 'country_agent_node')
graph.add_edge('country_agent_node', END)

def get_compiled_graph():
    # Initialize embeddings for the semantic search
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # Open connections
    with RedisSaver.from_conn_string(settings.redis_url) as checkpointer, \
         PostgresStore.from_conn_string(
             settings.database_url, 
             index={"embed": embeddings, "dims": 1536} # Required for semantic search
         ) as store:
            
            compiled_graph = graph.compile(checkpointer=checkpointer, store=store)
            yield compiled_graph