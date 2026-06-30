from __future__ import annotations

from typing import Any

import ray


@ray.remote
class GraphState:
    """Ray actor that holds the persistent memory of a loaded flow.

    Single responsibility: named variables (a mutable name → ObjectRef
    binding) that persist across runs of the flow. Node outputs do NOT live
    here — they're per-run scratch owned by the FlowEngine's RunContext.

    The engine's sequentiality guarantees that two writes never arrive
    concurrently, so no additional locking mechanism is needed.
    """

    def __init__(self, variables_defaults: dict[str, Any] | None = None):
        # variable_name → ObjectRef (or a direct value)
        self._variables: dict[str, Any] = {}
        # watched variables: variable_key → name of the event to publish on change
        self._watched: dict[str, str] = {}
        self._broker = None  # handle to the EventBroker (lazy)

        if variables_defaults:
            for name, value in variables_defaults.items():
                self._variables[name] = ray.put(value)

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------

    def set_variable(self, name: str, ref: Any) -> None:
        event_name = self._watched.get(name)
        if event_name is None:
            self._variables[name] = ref
            return
        # Watched variable: compare old vs new and publish if it changed.
        old = self._resolve(self._variables.get(name))
        new = self._resolve(ref)
        self._variables[name] = ref
        try:
            changed = old != new
        except Exception:
            changed = True  # if the comparison fails, assume it changed
        if changed:
            self._publish_change(event_name, name, new, old)

    def watch_variable(self, key: str, event_name: str) -> None:
        """Marks a variable as watched: publishes `event_name` when it changes."""
        self._watched[key] = event_name

    def unwatch_variable(self, key: str) -> None:
        self._watched.pop(key, None)

    @staticmethod
    def _resolve(v: Any) -> Any:
        return ray.get(v) if isinstance(v, ray.ObjectRef) else v

    def _publish_change(self, event_name: str, var: str, new: Any, old: Any) -> None:
        # Fire-and-forget: don't block the state actor waiting on the broker.
        try:
            if self._broker is None:
                from rayflow.events.bus import get_event_broker
                self._broker = get_event_broker()
            self._broker.publish.remote(
                event_name, {"value": new, "old": old, "variable": var}
            )
        except Exception:
            pass

    def get_variable(self, name: str) -> Any | None:
        return self._variables.get(name)

    def get_all_variables(self) -> dict[str, Any]:
        return dict(self._variables)
