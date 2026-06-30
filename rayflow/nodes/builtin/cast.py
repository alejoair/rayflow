"""Nodos de casteo explícito entre primitivos."""
from typing import Any

from rayflow.nodes.decorators import engine_node, Input, Output, ExecInput, ExecOutput, ExecContext


@engine_node
class ToInt:
    """Convierte un valor a entero. Úsalo para castear entre tipos incompatibles
    (p.ej. conectar un float o str a un pin int)."""
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("int")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, value: Any) -> None:
        ctx.set_output("result", int(value))
        await ctx.fire("exec_out")


@engine_node
class ToFloat:
    """Convierte un valor a float. Úsalo para castear un int o str a un pin float
    (int y float son incompatibles sin casteo explícito)."""
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("float")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, value: Any) -> None:
        ctx.set_output("result", float(value))
        await ctx.fire("exec_out")


@engine_node
class ToStr:
    """Convierte cualquier valor a su representación en texto (str)."""
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("str")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, value: Any) -> None:
        ctx.set_output("result", str(value))
        await ctx.fire("exec_out")


@engine_node
class ToBool:
    """Convierte un valor a booleano (reglas de truthiness de Python:
    0, '', [], {} y None son False; el resto True)."""
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("bool")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, value: Any) -> None:
        ctx.set_output("result", bool(value))
        await ctx.fire("exec_out")
