"""Nodos de eventos (OnEvent/EmitEvent). Se ejecutan en el engine (@engine_node)."""
from typing import Any

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
    """Punto de entrada disparado por un evento externo. Sin exec input.

    `event_name` es configuración estática (a qué evento, con namespace, se
    suscribe el flow). El `payload` del evento lo inyecta el engine como output
    de este nodo (los flow_inputs del entry node se escriben como sus outputs),
    así el subgrafo lo consume como "<id>.payload".
    """
    event_name = Input("str", default="")
    exec_out = ExecOutput()
    payload = Output("Any")

@engine_node
class EmitEvent:
    """Emite un evento al bus global. Fire-and-forget.

    Despacha al bus vía ctx.emit_event: cada flow suscrito a `event_name`
    (registrado con serve_events) se dispara con el `payload`.
    """
    exec_in = ExecInput()
    event_name = Input("str", default="")
    payload = Input("Any", default=None)
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, event_name: str, payload: Any) -> None:
        ctx.emit_event(event_name, payload)
        await ctx.fire("exec_out")
