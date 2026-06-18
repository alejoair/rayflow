"""Actor Ray de cola de eventos por ejecución.

Permite que el FlowEngine (actor remoto) publique eventos que FastAPI
puede consumir via get() bloqueante para reenviarlos como SSE al cliente HTTP.
"""
from __future__ import annotations
import asyncio
from typing import Any
import ray


@ray.remote
class RunQueue:
    """Cola FIFO de eventos de ejecución, accesible desde cualquier proceso Ray.

    El engine llama push() fire-and-forget. El driver llama get() bloqueante
    — se desbloquea en el momento exacto en que llega cada evento, sin polling.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def push(self, event: dict[str, Any]) -> None:
        await self._queue.put(event)

    async def get(self, timeout: float = 300.0) -> dict[str, Any]:
        """Bloquea hasta que haya un evento disponible o se agote el timeout."""
        return await asyncio.wait_for(self._queue.get(), timeout)
