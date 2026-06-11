"""Nodos de eventos (OnEvent/EmitEvent). Se ejecutan en el engine (@engine_node)."""
from rayflow.nodes.decorators import (
    ExecContext,
    ExecInput,
    ExecOutput,
    Input,
    Output,
    engine_node,
)


@engine_node
class OnEvent:
    """Punto de entrada disparado por un evento externo. Sin exec input."""
    event_name = Input("str", default="")
    exec_out = ExecOutput()
    payload = Output("Any")

    def run(self, ctx: ExecContext) -> dict:
        ctx.fire("exec_out")
        return {}


@engine_node
class EmitEvent:
    """Emite un evento al bus global. Fire-and-forget."""
    exec_in = ExecInput()
    event_name = Input("str", default="")
    payload = Input("Any", default=None)
    exec_out = ExecOutput()

    def run(self, ctx: ExecContext, event_name: str, payload: any) -> dict:
        ctx.fire("exec_out")
        return {}
