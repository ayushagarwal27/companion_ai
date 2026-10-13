from langgraph.graph import MessagesState

class CompanionState(MessagesState):
    """Per-session graph state, persisted by the Redis checkpointer under a thread_id.

    messages: full turn history (inherited from MessagesState); older messages are
        periodically removed by summarize_conversation_node once the session is long.
    country: the country this session's conversation is scoped to.
    summary: running summary of messages already compacted out of `messages`.
    turns_since_extraction: turns since long-term memory was last persisted for this
        user; drives maybe_extract_memory_node's periodic trigger.
    """

    country: str
    summary: str
    turns_since_extraction: int