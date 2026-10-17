"""BackgroundTasks duck-type for a long-lived WS connection, which has no
FastAPI request/response scope to defer work until after - unlike a real
BackgroundTasks, nothing else keeps a fire-and-forget task alive, so callers
must drain `pending` themselves (see backend/voice/session.py's disconnect
cleanup) before tearing down the connection.
"""

import asyncio
from typing import Any, Callable


class BackgroundTasksAdapter:
    def __init__(self) -> None:
        self.pending: set[asyncio.Task] = set()

    def add_task(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        task = asyncio.create_task(asyncio.to_thread(fn, *args, **kwargs))
        self.pending.add(task)
        task.add_done_callback(self.pending.discard)
