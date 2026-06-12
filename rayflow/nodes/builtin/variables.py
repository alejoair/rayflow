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
    """Lee una variable del estado del grafo.

    Nodo pure (sin exec pins): se evalúa bajo demanda cuando otro nodo
    necesita su output. No requiere conexión exec — el engine lo llama
    implícitamente al resolver los inputs del nodo consumidor.
    """
    variable_name = Input("str", default="")
    value = Output("Any")

    def run(self, ctx: ExecContext, variable_name: str) -> dict:
        return {"value": ctx.get_variable(variable_name)}


@engine_node
class Set:
    """Escribe una variable en el estado del grafo."""
    exec_in = ExecInput()
    variable_name = Input("str", default="")
    value = Input("Any", default=None)
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, variable_name: str, value: any) -> None:
        ctx.set_variable(variable_name, value)
        await ctx.fire("exec_out")
