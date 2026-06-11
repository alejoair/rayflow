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

        if variables_defaults:
            for name, value in variables_defaults.items():
                self._variables[name] = ray.put(value)

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------

    def set_variable(self, name: str, ref: Any) -> None:
        self._variables[name] = ref

    def get_variable(self, name: str) -> Any | None:
        return self._variables.get(name)

    def get_all_variables(self) -> dict[str, Any]:
        return dict(self._variables)

    # ------------------------------------------------------------------
    # Outputs vigentes de nodos de ejecución
    # ------------------------------------------------------------------

    def set_node_outputs(self, node_id: str, outputs: dict[str, Any]) -> None:
        self._node_outputs[node_id] = outputs

    def get_node_output(self, node_id: str, pin_name: str) -> Any | None:
        node_outs = self._node_outputs.get(node_id)
        if node_outs is None:
            return None
        return node_outs.get(pin_name)

    def node_has_fired(self, node_id: str) -> bool:
        return node_id in self._node_outputs
