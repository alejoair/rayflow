"""Ray actor for the per-execution event queue.

Lets the FlowEngine (a remote actor) publish events that FastAPI consumes
via a blocking get() to forward them as SSE to the HTTP client.

A single actor per flow persists for the whole lifetime of the loaded flow.
Each execution reserves a sub-queue identified by run_id.
"""
from __future__ import annotations
import asyncio
from typing import Any
import ray


@ray.remote
class RunQueue:
    """FIFO queue of execution events, reachable from any Ray process.

    Manages multiple simultaneous executions (in practice sequential, due to
    the FlowEngine's event loop) via a dict {run_id -> asyncio.Queue}.

    The engine calls push() fire-and-forget. The driver calls a blocking
    get() — it unblocks the instant each event arrives, with no polling.
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}

    async def create_run(self, run_id: str) -> None:
        self._queues[run_id] = asyncio.Queue()

    async def push(self, run_id: str, event: dict[str, Any]) -> None:
        q = self._queues.get(run_id)
        if q is not None:
            await q.put(event)

    async def get(self, run_id: str, timeout: float = 300.0) -> dict[str, Any]:
        """Blocks until an event is available or the timeout elapses."""
        q = self._queues.get(run_id)
        if q is None:
            raise KeyError(f"unknown run_id: {run_id}")
        return await asyncio.wait_for(q.get(), timeout)

    async def close_run(self, run_id: str) -> None:
        self._queues.pop(run_id, None)
