from langchain_openai import ChatOpenAI
from langchain.messages import SystemMessage
from langgraph.graph import MessagesState
from src.config.settings import settings
from src.prompts.country_agent import SYSTEM_PROMPT

llm = ChatOpenAI(model=settings.chat_model, api_key=settings.openai_api_key) # type: ignore

def country_agent_node(state: MessagesState):
    response = llm.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
    return {"messages": [response]}

