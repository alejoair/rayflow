from __future__ import annotations

from typing import Any

import ray

_BROKER_NAME = "rayflow_event_broker"


@ray.remote
class EventBroker:
    """Global Ray actor that routes events between flows (fire-and-forget pub/sub).

    The events analogue of GraphState: a single detached actor for the
    whole cluster. Isolation comes from NAMESPACING the event name, S3-key
    style — the `/` characters are just part of the name, not containers:

        "sales/order_created"     ← one namespace
        "inventory/stock_low"     ← another
        "tick"                    ← global namespace (no prefix)

    The broker matches EXACTLY on the full event name: publisher and
    subscriber must use the same string. It doesn't persist messages —
    `publish` dispatches to current subscribers and forgets (fire-and-forget).
    If nobody is listening, the event is lost.
    """

    def __init__(self):
        # event_name (with namespace) → list of (flow_source, graph_id)
        self._subscriptions: dict[str, list[tuple[Any, str]]] = {}
        # event_name → number of times published (introspection/debug; does
        # not retain messages — the broker stays fire-and-forget).
        self._publish_count: dict[str, int] = {}

    def subscribe(self, event_name: str, flow_source: Any, graph_id: str) -> None:
        self._subscriptions.setdefault(event_name, []).append((flow_source, graph_id))

    def unsubscribe(self, event_name: str, graph_id: str) -> None:
        subs = self._subscriptions.get(event_name, [])
        self._subscriptions[event_name] = [
            (src, gid) for src, gid in subs if gid != graph_id
        ]

    def publish(self, event_name: str, payload: Any) -> int:
        """Fire-and-forget: launches one execution per subscriber to the event.

        Returns the number of subscribers dispatched to (0 if nobody is listening).
        Matching is exact on the full name (namespace included).
        """
        self._publish_count[event_name] = self._publish_count.get(event_name, 0) + 1
        subs = self._subscriptions.get(event_name, [])
        for flow_name, _graph_id in subs:
            from rayflow.api import _run_event_flow
            _run_event_flow.remote(flow_name, event_name, payload)  # type: ignore[attr-defined]
        return len(subs)

    def list_subscriptions(self) -> dict[str, list[tuple[Any, str]]]:
        return dict(self._subscriptions)

    def publish_count(self, event_name: str) -> int:
        """How many times an event was published (introspection)."""
        return self._publish_count.get(event_name, 0)


# ---------------------------------------------------------------------------
# Singleton accessor for the broker
# ---------------------------------------------------------------------------

def get_event_broker() -> EventBroker:
    """Gets (or creates) the global event broker actor."""
    try:
        return ray.get_actor(_BROKER_NAME)
    except ValueError:
        return EventBroker.options(  # type: ignore[attr-defined]
            name=_BROKER_NAME, lifetime="detached"
        ).remote()
