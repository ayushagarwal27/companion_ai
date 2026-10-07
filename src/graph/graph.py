from langgraph.graph import StateGraph, MessagesState, START, END
from src.agents.country_agent import country_agent_node
from langchain.messages import HumanMessage

def graph_builder():
    graph = StateGraph(MessagesState)
    graph.add_node('country_agent_node', country_agent_node)
    graph.add_edge(START, 'country_agent_node')
    graph.add_edge('country_agent_node', END)
    compiled_graph = graph.compile()
    return compiled_graph


companion_graph = graph_builder()
