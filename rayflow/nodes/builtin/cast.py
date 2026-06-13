"""Nodos de casteo explícito entre primitivos."""
from typing import Any

from rayflow.nodes.decorators import ray_node, Input, Output, ExecInput, ExecOutput, ExecContext


@ray_node
class ToInt:
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("int")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, value: Any) -> None:
        ctx.set_output("result", int(value))
        await ctx.fire("exec_out")


@ray_node
class ToFloat:
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("float")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, value: Any) -> None:
        ctx.set_output("result", float(value))
        await ctx.fire("exec_out")


@ray_node
class ToStr:
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("str")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, value: Any) -> None:
        ctx.set_output("result", str(value))
        await ctx.fire("exec_out")


@ray_node
class ToBool:
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("bool")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, value: Any) -> None:
        ctx.set_output("result", bool(value))
        await ctx.fire("exec_out")
