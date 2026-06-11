"""Nodos de estado (Get/Set). Se ejecutan en el engine (@engine_node)."""
from rayflow.nodes.decorators import (
    ExecContext,
    ExecInput,
    ExecOutput,
    Input,
    Output,
    engine_node,
)


@engine_node
class Get:
    """Lee una variable del estado del grafo. Nodo de datos (sin exec pins).

    El engine resuelve su valor leyendo del state actor en el momento de la lectura.
    """
    variable_name = Input("str", default="")
    value = Output("Any")


@engine_node
class Set:
    """Escribe una variable en el estado del grafo."""
    exec_in = ExecInput()
    variable_name = Input("str", default="")
    value = Input("Any", default=None)
    exec_out = ExecOutput()

    def run(self, ctx: ExecContext, variable_name: str, value: any) -> dict:
        ctx.fire("exec_out")
        return {}
