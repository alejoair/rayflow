from __future__ import annotations

from typing import Any

import ray

_BUS_NAME = "rayflow_event_bus"


@ray.remote
class EventBus:
    """Actor Ray global que gestiona la publicación y suscripción de eventos.

    Un grafo se suscribe al arrancar (serve) y se desuscribe al terminar.
    El dispatch es fire-and-forget: emit no espera a los suscriptores.
    """

    def __init__(self):
        # event_name → lista de (flow_path, grafo_id)
        self._subscriptions: dict[str, list[tuple[str, str]]] = {}

    def subscribe(self, event_name: str, flow_path: str, graph_id: str) -> None:
        self._subscriptions.setdefault(event_name, []).append((flow_path, graph_id))

    def unsubscribe(self, event_name: str, graph_id: str) -> None:
        subs = self._subscriptions.get(event_name, [])
        self._subscriptions[event_name] = [
            (fp, gid) for fp, gid in subs if gid != graph_id
        ]

    def emit(self, event_name: str, payload: Any) -> None:
        """Fire-and-forget: lanza una ejecución por cada suscriptor."""
        subs = self._subscriptions.get(event_name, [])
        for flow_path, _graph_id in subs:
            # Importación diferida para evitar ciclos.
            from rayflow.api import _run_event_flow
            _run_event_flow.remote(flow_path, event_name, payload)  # type: ignore[attr-defined]

    def list_subscriptions(self) -> dict[str, list[tuple[str, str]]]:
        return dict(self._subscriptions)


# ---------------------------------------------------------------------------
# Singleton de acceso al bus
# ---------------------------------------------------------------------------

def get_event_bus() -> EventBus:
    """Obtiene (o crea) el actor global del bus de eventos."""
    try:
        return ray.get_actor(_BUS_NAME)
    except ValueError:
        return EventBus.options(name=_BUS_NAME, lifetime="detached").remote()  # type: ignore[attr-defined]
