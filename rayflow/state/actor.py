from __future__ import annotations

from typing import Any

import ray


@ray.remote
class GraphState:
    """Actor Ray que mantiene el estado mutable de una ejecución de grafo.

    Dos responsabilidades:
    - Variables nombradas: binding mutable nombre → ObjectRef
    - Outputs vigentes de nodos de ejecución: node_id → {pin_name: ObjectRef}

    La secuencialidad del engine garantiza que nunca llegan dos escrituras
    concurrentes, por lo que no se necesita ningún mecanismo de locking adicional.
    """

    def __init__(self, variables_defaults: dict[str, Any] | None = None):
        # nombre_variable → ObjectRef (o valor directo)
        self._variables: dict[str, Any] = {}
        # node_id → {pin_name → ObjectRef}
        self._node_outputs: dict[str, dict[str, Any]] = {}
        # variables vigiladas: clave_variable → nombre del evento a publicar al cambiar
        self._watched: dict[str, str] = {}
        self._broker = None  # handle al EventBroker (lazy)

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
        # Variable vigilada: comparar viejo vs nuevo y, si cambió, publicar.
        old = self._resolve(self._variables.get(name))
        new = self._resolve(ref)
        self._variables[name] = ref
        try:
            changed = old != new
        except Exception:
            changed = True  # si la comparación falla, asumir cambio
        if changed:
            self._publish_change(event_name, name, new, old)

    def watch_variable(self, key: str, event_name: str) -> None:
        """Marca una variable como vigilada: al cambiar, publica `event_name`."""
        self._watched[key] = event_name

    def unwatch_variable(self, key: str) -> None:
        self._watched.pop(key, None)

    @staticmethod
    def _resolve(v: Any) -> Any:
        return ray.get(v) if isinstance(v, ray.ObjectRef) else v

    def _publish_change(self, event_name: str, var: str, new: Any, old: Any) -> None:
        # Fire-and-forget: no bloquear el actor de estado esperando al broker.
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

    # ------------------------------------------------------------------
    # Outputs vigentes de nodos de ejecución
    # ------------------------------------------------------------------

    def set_node_outputs(self, node_id: str, outputs: dict[str, Any]) -> None:
        existing = self._node_outputs.get(node_id, {})
        self._node_outputs[node_id] = {**existing, **outputs}

    def get_node_output(self, node_id: str, pin_name: str) -> Any | None:
        node_outs = self._node_outputs.get(node_id)
        if node_outs is None:
            return None
        return node_outs.get(pin_name)

    def node_has_fired(self, node_id: str) -> bool:
        return node_id in self._node_outputs
