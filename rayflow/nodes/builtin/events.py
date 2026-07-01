"""Event nodes (OnEvent/EmitEvent). Run inside the engine (@engine_node)."""
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
    """Entry point triggered by an external event. No exec input.

    `event_name` is static config (which namespaced event the flow
    subscribes to). The event's `payload` is injected by the engine as this
    node's output (the entry node's flow_inputs are written as its
    outputs), so the subgraph consumes it as "<id>.payload".
    """
    event_name = Input("str", default="")
    exec_out = ExecOutput()
    payload = Output("Any")

@engine_node
class OnVariableChange:
    """Entry point triggered when a state variable changes.

    Static config:
    - `variable`: name of the variable to watch.
    - `source`: name of the flow that owns the variable; empty = this same flow.

    When a `Set` node writes that variable with a different value, the
    source flow's GraphState publishes the event `var:{source}/{variable}`
    and this flow runs. The engine injects the new value (`value`) and the
    previous one (`old`) as this node's outputs.

    The source flow must be loaded (served) before the watching flow, so its
    GraphState exists when the watch is registered. Delivery is
    fire-and-forget with no order guarantee (same as the rest of the bus).
    """
    category = "Events"
    variable = Input("str", default="")
    source   = Input("str", default="")
    value    = Output("Any")
    old      = Output("Any")
    exec_out = ExecOutput()


@engine_node
class EmitEvent:
    """Emits an event to the global bus. Fire-and-forget.

    Dispatches to the bus via ctx.emit_event: every flow subscribed to
    `event_name` (registered with serve_events) fires with the `payload`.
    """
    exec_in = ExecInput()
    event_name = Input("str", default="")
    payload = Input("Any", default=None)
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, event_name: str, payload: Any) -> None:
        ctx.emit_event(event_name, payload)
        await ctx.fire("exec_out")
