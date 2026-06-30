"""Explicit casting nodes between primitives."""
from typing import Any

from rayflow.nodes.decorators import engine_node, Input, Output, ExecInput, ExecOutput, ExecContext


@engine_node
class ToInt:
    """Converts a value to int. Use it to cast between incompatible types
    (e.g. connecting a float or str to an int pin)."""
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("int")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, value: Any) -> None:
        ctx.set_output("result", int(value))
        await ctx.fire("exec_out")


@engine_node
class ToFloat:
    """Converts a value to float. Use it to cast an int or str into a float
    pin (int and float are incompatible without an explicit cast)."""
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("float")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, value: Any) -> None:
        ctx.set_output("result", float(value))
        await ctx.fire("exec_out")


@engine_node
class ToStr:
    """Converts any value to its text representation (str)."""
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("str")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, value: Any) -> None:
        ctx.set_output("result", str(value))
        await ctx.fire("exec_out")


@engine_node
class ToBool:
    """Converts a value to boolean (Python truthiness rules: 0, '', [], {}
    and None are False; everything else is True)."""
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("bool")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, value: Any) -> None:
        ctx.set_output("result", bool(value))
        await ctx.fire("exec_out")
