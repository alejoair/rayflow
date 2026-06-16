"""Actor Ray de cola de eventos por ejecución.

Permite que el FlowEngine (actor remoto) publique eventos que FastAPI
puede consumir via polling para reenviarlos como SSE al cliente HTTP.
"""
from __future__ import annotations
from typing import Any
import ray


@ray.remote
class RunQueue:
    """Cola FIFO de eventos de ejecución, accesible desde cualquier proceso Ray."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._done = False

    def push(self, event: dict[str, Any]) -> None:
        self._events.append(event)
        if event.get("event") in ("flow_done", "flow_error"):
            self._done = True

    def drain(self) -> list[dict[str, Any]]:
        events, self._events = self._events, []
        return events

    def is_done(self) -> bool:
        return self._done
