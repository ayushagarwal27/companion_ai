from langgraph.graph import StateGraph, MessagesState, START, END
from src.agents.country_agent import country_agent_node
from langchain.messages import HumanMessage

graph = StateGraph(MessagesState)

graph.add_node('country_agent_node', country_agent_node)

graph.add_edge(START, 'country_agent_node')
graph.add_edge('country_agent_node', END)

compiled = graph.compile()

response = compiled.invoke({"messages":[HumanMessage("What is national Animal of India")]})

print(response)