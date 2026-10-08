import uuid

from langchain.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState
from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from src.config.settings import settings
from src.prompts.country_agent import SYSTEM_PROMPT

llm = ChatOpenAI(model=settings.chat_model, api_key=settings.openai_api_key)  # type: ignore


class MemoryExtraction(BaseModel):
    new_facts: list[str] = Field(default_factory=list, description="New durable facts learned about the user in this turn")
    episodic_summary: str | None = Field(default=None, description="One-line summary of this exchange, worth recalling later")
    updated_procedural_rules: str | None = Field(default=None, description="Updated behavioral rules for this user, if anything changed")


def country_agent_node(state: MessagesState, config: RunnableConfig, *, store: BaseStore):
    user_id = config["configurable"].get("user_id") # type: ignore
    query = state["messages"][-1].content

    system_prompt = SYSTEM_PROMPT
    if user_id:
        semantic = store.search(("memories", user_id, "semantic"))
        episodic = store.search(("memories", user_id, "episodic"), query=query)
        procedural = store.get(("memories", user_id, "procedural"), "rules")

        if semantic:
            facts = "\n".join(item.value.get("fact", "") for item in semantic)
            system_prompt += f"\n\nKnown facts about this user:\n{facts}"
        if episodic:
            examples = "\n".join(item.value.get("summary", "") for item in episodic)
            system_prompt += f"\n\nRelevant past exchanges:\n{examples}"
        if procedural:
            system_prompt += f"\n\nBehavioral preferences for this user:\n{procedural.value.get('rules', '')}"

    response = llm.invoke([SystemMessage(system_prompt), *state["messages"]])

    if user_id:
        _extract_and_store_memories(store, user_id, query, response.content)

    return {"messages": [response]}


def _extract_and_store_memories(store: BaseStore, user_id: str, query: str, answer: str) -> None:
    extraction_llm = llm.with_structured_output(MemoryExtraction)
    extraction = extraction_llm.invoke([
        SystemMessage(
            "Given this exchange, extract anything worth remembering long-term about the user. "
            "Only extract durable facts, not one-off trivia. Leave fields empty if there's nothing worth saving."
        ),
        HumanMessage(f"User: {query}\nAssistant: {answer}"),
    ])

    for fact in extraction.new_facts:
        store.put(("memories", user_id, "semantic"), str(uuid.uuid4()), {"fact": fact})

    if extraction.episodic_summary:
        store.put(("memories", user_id, "episodic"), str(uuid.uuid4()), {"summary": extraction.episodic_summary})

    if extraction.updated_procedural_rules:
        store.put(("memories", user_id, "procedural"), "rules", {"rules": extraction.updated_procedural_rules})
