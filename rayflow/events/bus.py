from __future__ import annotations

from typing import Any

import ray

_BROKER_NAME = "rayflow_event_broker"


@ray.remote
class EventBroker:
    """Actor Ray global que enruta eventos entre flows (pub/sub fire-and-forget).

    Es el análogo del GraphState para eventos: un único actor detached para todo
    el cluster. El aislamiento se logra por NAMESPACE en el nombre del evento,
    estilo clave de S3 — los `/` son solo parte del nombre, no contenedores:

        "ventas/order_created"   ← un namespace
        "inventario/stock_low"   ← otro
        "tick"                   ← namespace global (sin prefijo)

    El broker hace matching EXACTO por el nombre completo del evento: emisor y
    receptor deben usar el mismo string. No persiste mensajes — `publish`
    despacha a los suscriptores actuales y olvida (fire-and-forget). Si nadie
    escucha, el evento se pierde.
    """

    def __init__(self):
        # event_name (con namespace) → lista de (flow_source, graph_id)
        self._subscriptions: dict[str, list[tuple[Any, str]]] = {}
        # event_name → nº de veces publicado (introspección/debug; no retiene
        # mensajes — el broker sigue siendo fire-and-forget).
        self._publish_count: dict[str, int] = {}

    def subscribe(self, event_name: str, flow_source: Any, graph_id: str) -> None:
        self._subscriptions.setdefault(event_name, []).append((flow_source, graph_id))

    def unsubscribe(self, event_name: str, graph_id: str) -> None:
        subs = self._subscriptions.get(event_name, [])
        self._subscriptions[event_name] = [
            (src, gid) for src, gid in subs if gid != graph_id
        ]

    def publish(self, event_name: str, payload: Any) -> int:
        """Fire-and-forget: lanza una ejecución por cada suscriptor al evento.

        Devuelve el número de suscriptores despachados (0 si nadie escucha).
        El matching es exacto por el nombre completo (namespace incluido).
        """
        self._publish_count[event_name] = self._publish_count.get(event_name, 0) + 1
        subs = self._subscriptions.get(event_name, [])
        for flow_source, _graph_id in subs:
            # Importación diferida para evitar ciclos.
            from rayflow.api import _run_event_flow
            _run_event_flow.remote(flow_source, event_name, payload)  # type: ignore[attr-defined]
        return len(subs)

    def list_subscriptions(self) -> dict[str, list[tuple[Any, str]]]:
        return dict(self._subscriptions)

    def publish_count(self, event_name: str) -> int:
        """Cuántas veces se publicó un evento (introspección)."""
        return self._publish_count.get(event_name, 0)


# ---------------------------------------------------------------------------
# Singleton de acceso al broker
# ---------------------------------------------------------------------------

def get_event_broker() -> EventBroker:
    """Obtiene (o crea) el actor global del broker de eventos."""
    try:
        return ray.get_actor(_BROKER_NAME)
    except ValueError:
        return EventBroker.options(  # type: ignore[attr-defined]
            name=_BROKER_NAME, lifetime="detached"
        ).remote()
