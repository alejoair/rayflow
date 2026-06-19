"""Actor Ray de cola de eventos por ejecución.

Permite que el FlowEngine (actor remoto) publique eventos que FastAPI
puede consumir via get() bloqueante para reenviarlos como SSE al cliente HTTP.

Un único actor por flow persiste durante toda la vida del flow cargado.
Cada ejecución reserva una sub-queue identificada por run_id.
"""
from __future__ import annotations
import asyncio
from typing import Any
import ray


@ray.remote
class RunQueue:
    """Cola FIFO de eventos de ejecución, accesible desde cualquier proceso Ray.

    Gestiona múltiples ejecuciones simultáneas (en la práctica secuenciales por
    el event loop del FlowEngine) mediante un dict {run_id -> asyncio.Queue}.

    El engine llama push() fire-and-forget. El driver llama get() bloqueante
    — se desbloquea en el momento exacto en que llega cada evento, sin polling.
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
        """Bloquea hasta que haya un evento disponible o se agote el timeout."""
        q = self._queues.get(run_id)
        if q is None:
            raise KeyError(f"run_id desconocido: {run_id}")
        return await asyncio.wait_for(q.get(), timeout)

    async def close_run(self, run_id: str) -> None:
        self._queues.pop(run_id, None)
