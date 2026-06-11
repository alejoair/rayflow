from rayflow.nodes.decorators import ray_node, Input, Output, ExecInput, ExecOutput, ExecContext


@ray_node
class Add:
    """Suma dos enteros."""
    exec_in = ExecInput()
    a = Input("int", default=0)
    b = Input("int", default=0)
    result = Output("int")
    exec_out = ExecOutput()

    def run(self, ctx: ExecContext, a: int, b: int) -> dict:
        ctx.fire("exec_out")
        return {"result": a + b}
