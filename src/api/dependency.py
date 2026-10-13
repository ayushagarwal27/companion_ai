from src.graph.graph import get_compiled_graph

def get_graph():
    """FastAPI dependency: yields a compiled graph with its own Redis/Postgres connections,
    opened for the duration of one request and closed once it (and any BackgroundTasks
    scheduled during it) complete.
    """
    yield from get_compiled_graph()