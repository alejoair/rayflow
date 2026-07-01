"""State nodes (Get/Set)."""
from rayflow.nodes.decorators import (
    ExecContext,
    ExecInput,
    ExecOutput,
    Input,
    Output,
    engine_node,
    ray_node,
)


@ray_node
class Get:
    """Reads a variable from the graph's state.

    Pure node (no exec pins): evaluated on demand whenever another node
    needs its output. Requires no exec wiring — the engine calls it
    implicitly while resolving the consuming node's inputs.
    """
    variable_name = Input("str", default="")
    value = Output("Any")

    async def run(self, ctx: ExecContext, variable_name: str) -> dict:
        return {"value": ctx.get_variable(variable_name)}


@engine_node
class Set:
    """Writes a variable into the graph's state."""
    exec_in = ExecInput()
    variable_name = Input("str", default="")
    value = Input("Any", default=None)
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, variable_name: str, value: any) -> None:
        ctx.set_variable(variable_name, value)
        await ctx.fire("exec_out")
