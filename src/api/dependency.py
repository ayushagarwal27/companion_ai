from src.graph.graph import get_compiled_graph

def get_graph():
    """
    Yields the compiled Companion LangGraph graph for FastAPI dependency injection.
    """
    yield from get_compiled_graph()