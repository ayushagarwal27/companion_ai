"""Graph nodes for the country-guide agent.

Three nodes run in sequence per /chat turn: country_agent_node (answer the user,
using short-term state plus long-term memory retrieved from the store),
maybe_extract_memory_node (periodically persist durable facts to long-term memory),
and summarize_conversation_node (compact old messages out of the checkpointer once
the session gets long). See README.md for the full memory architecture.
"""

import uuid
from typing import Sequence

from langchain.messages import HumanMessage, RemoveMessage, SystemMessage
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field
from backend.state.country_state import CompanionState
from backend.config.settings import settings
from backend.prompts.country_agent import build_system_prompt

llm = ChatOpenAI(model=settings.chat_model, api_key=settings.openai_api_key)  # type: ignore


class MemoryExtraction(BaseModel):
    """Structured output schema for distilling a conversation excerpt into long-term memory."""

    new_facts: list[str] = Field(default_factory=list, description="New durable facts learned about the user in this turn")
    episodic_summary: str | None = Field(default=None, description="One-line summary of this exchange, worth recalling later")
    updated_procedural_rules: str | None = Field(default=None, description="Updated behavioral rules for this user, if anything changed")


def country_agent_node(state: CompanionState, config: RunnableConfig, *, store: BaseStore):
    """Answer the user's latest message.

    Builds the system prompt from: the static country-guide instructions, the
    session's running summary (if any older messages have been compacted away),
    and long-term memory for this user_id (semantic facts, episodic summaries
    relevant to the current query, and procedural behavioral rules). Does not
    write anything to long-term memory itself — see maybe_extract_memory_node.
    """
    user_id = config["configurable"].get("user_id") # type: ignore
    query = state["messages"][-1].content

    system_prompt = build_system_prompt(state["country"])

    summary = state.get("summary", "")
    if summary:
        system_prompt += f"\n\nSummary of earlier conversation in this session:\n{summary}"

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

    return {"messages": [response]}


def maybe_extract_memory_node(state: CompanionState, config: RunnableConfig, *, store: BaseStore):
    """Periodically flush recent turns to long-term memory, independent of summarization.

    Increments turns_since_extraction every turn; once it reaches
    settings.memory_extraction_every_n_turns, extracts the pending turns and resets
    the counter to 0. Runs via BackgroundTasks when available (see server.py) so the
    extraction LLM call never adds latency to the /chat response. This is what makes
    even a short session (e.g. "my name is X" and nothing else) eventually durable,
    without waiting for the session to grow long enough to trigger summarization.
    """
    user_id = config["configurable"].get("user_id") # type: ignore
    if not user_id:
        return {}

    turns_since_extraction = state.get("turns_since_extraction", 0) + 1
    if turns_since_extraction < settings.memory_extraction_every_n_turns:
        return {"turns_since_extraction": turns_since_extraction}

    pending_messages = state["messages"][-(turns_since_extraction * 2):]
    transcript = _format_transcript(pending_messages)

    background_tasks = config["configurable"].get("background_tasks") # type: ignore
    if background_tasks is not None:
        background_tasks.add_task(_extract_and_store_memories, store, user_id, transcript)
    else:
        _extract_and_store_memories(store, user_id, transcript)

    return {"turns_since_extraction": 0}


def finalize_pending_memory(values: dict, user_id: str, store: BaseStore) -> bool:
    """Extract whatever maybe_extract_memory_node hasn't picked up yet, for a session
    that ended (explicitly, via /chat/{session_id}/end, or by going idle) before
    turns_since_extraction reached the threshold. `values` is a CompanionState dict,
    typically from graph.get_state(config).values. Returns True if anything was
    extracted, False if there was nothing pending.
    """
    turns_since_extraction = values.get("turns_since_extraction", 0)
    if turns_since_extraction <= 0:
        return False

    pending_messages = values.get("messages", [])[-(turns_since_extraction * 2):]
    if not pending_messages:
        return False

    _extract_and_store_memories(store, user_id, _format_transcript(pending_messages))
    return True


def summarize_conversation_node(state: CompanionState, config: RunnableConfig, *, store: BaseStore):
    """Keep the checkpointer small by compacting old messages into a running summary.

    No-ops until the session exceeds settings.history_summarize_trigger messages.
    Once triggered, archives every message except the last settings.history_keep_last_n,
    re-extracts long-term memory from the archived chunk as a safety net (see the
    comment below), folds the chunk into (or starts) the session's summary via an LLM
    call, and emits RemoveMessage entries so langgraph's add_messages reducer deletes
    the archived messages from the checkpointed state.
    """
    messages = state["messages"]
    if len(messages) <= settings.history_summarize_trigger:
        return {}

    keep_n = settings.history_keep_last_n
    to_archive = messages[:-keep_n] if keep_n > 0 else messages

    # Safety net: re-extract the archived chunk in case the periodic trigger hasn't covered
    # all of it yet (e.g. memory_extraction_every_n_turns outlives history_keep_last_n).
    # Duplicate facts across the two triggers are cheap; losing facts on archive is not.
    user_id = config["configurable"].get("user_id") # type: ignore
    if user_id:
        transcript = _format_transcript(to_archive)
        background_tasks = config["configurable"].get("background_tasks") # type: ignore
        if background_tasks is not None:
            background_tasks.add_task(_extract_and_store_memories, store, user_id, transcript)
        else:
            _extract_and_store_memories(store, user_id, transcript)

    existing_summary = state.get("summary", "")
    if existing_summary:
        summary_prompt = (
            f"This is the summary of the conversation so far:\n{existing_summary}\n\n"
            "Extend the summary by incorporating the new messages below. Keep it concise (a few sentences), "
            "preserving important context, user preferences already covered, and any open threads."
        )
    else:
        summary_prompt = (
            "Summarize the conversation below concisely (a few sentences), preserving important context, "
            "user preferences, and any open threads."
        )

    summary_response = llm.invoke([SystemMessage(summary_prompt), *to_archive])

    remove_messages = [RemoveMessage(id=m.id) for m in to_archive if m.id is not None]

    return {"summary": str(summary_response.content), "messages": remove_messages}


def _format_transcript(messages: Sequence[BaseMessage]) -> str:
    """Render messages as a plain "Role: content" transcript for prompting the LLM."""
    lines = []
    for m in messages:
        role = "User" if isinstance(m, HumanMessage) else "Assistant"
        lines.append(f"{role}: {m.content}")
    return "\n".join(lines)


def _extract_and_store_memories(store: BaseStore, user_id: str, transcript: str) -> None:
    """Run structured-output extraction over a transcript and persist the results.

    Writes to three separate namespaces under ("memories", user_id, ...): "semantic"
    (one row per durable fact, each a fresh uuid key — facts are additive, never
    deduplicated, so re-extracting overlapping transcript ranges produces duplicate
    rows rather than lost data), "episodic" (one row per exchange summary), and
    "procedural" (a single row at key "rules" that gets overwritten, since behavioral
    rules supersede rather than accumulate).
    """
    extraction_llm = llm.with_structured_output(MemoryExtraction)
    extraction = extraction_llm.invoke([
        SystemMessage(
            "Given this conversation excerpt, extract anything worth remembering long-term about the user. "
            "Only extract durable facts, not one-off trivia. Leave fields empty if there's nothing worth saving."
        ),
        HumanMessage(transcript),
    ])

    for fact in extraction.new_facts:
        store.put(("memories", user_id, "semantic"), str(uuid.uuid4()), {"fact": fact})

    if extraction.episodic_summary:
        store.put(("memories", user_id, "episodic"), str(uuid.uuid4()), {"summary": extraction.episodic_summary})

    if extraction.updated_procedural_rules:
        store.put(("memories", user_id, "procedural"), "rules", {"rules": extraction.updated_procedural_rules})
