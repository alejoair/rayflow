from rayflow.nodes.decorators import engine_node, Input, Output, ExecInput, ExecOutput, ExecContext


@engine_node
class Add:
    """Adds two integers."""
    category = "Math"
    exec_in = ExecInput()
    a = Input("int", default=0)
    b = Input("int", default=0)
    result = Output("int")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, a: int, b: int) -> None:
        ctx.set_output("result", a + b)
        await ctx.fire("exec_out")
