"""Nodos de control de flujo."""
import asyncio

from rayflow.nodes.decorators import (
    ExecContext,
    ExecInput,
    ExecOutput,
    Input,
    Output,
    engine_node,
    parallel_node,
)


@engine_node
class OnStart:
    """Punto de entrada para flows sin parámetros."""
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext) -> None:
        await ctx.fire("exec_out")


@engine_node
class FlowInput:
    """Punto de entrada para flows con parámetros.

    Sus data outputs se generan en build a partir de los `inputs` del flow.
    El ExecContext expone los valores de entrada via set_output antes de llamar run().
    """
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext) -> None:
        await ctx.fire("exec_out")


@engine_node
class FlowOutput:
    """Punto de salida del flow.

    Sus data inputs se generan en build a partir de los `outputs` del flow.
    """
    exec_in = ExecInput()

    async def run(self, ctx: ExecContext) -> None:
        pass


@engine_node
class Branch:
    """Desvío condicional. Dispara `true` o `false` según `condition`."""
    exec_in = ExecInput()
    condition = Input("bool", default=False)
    true = ExecOutput()
    false = ExecOutput()

    async def run(self, ctx: ExecContext, condition: bool) -> None:
        await ctx.fire("true" if condition else "false")


@engine_node
class Sequence:
    """Dispara sus exec outputs en orden secuencial."""
    exec_in = ExecInput()
    then_0 = ExecOutput()
    then_1 = ExecOutput()
    then_2 = ExecOutput()

    async def run(self, ctx: ExecContext) -> None:
        await ctx.fire("then_0")
        await ctx.fire("then_1")
        await ctx.fire("then_2")


@parallel_node
class Parallel:
    """Fork/join paralelo. Lanza N ramas simultáneamente.

    Los branch pins (branch_0, branch_1, …, branch_N) se inyectan dinámicamente
    en build a partir del wiring del JSON. Las ramas se descubren en runtime via
    ctx.exec_outputs_except("joined") y se lanzan con asyncio.gather.
    El pin 'joined' se dispara cuando todas las ramas han terminado.
    """
    exec_in = ExecInput()
    joined = ExecOutput()

    async def run(self, ctx: ExecContext) -> None:
        branches = await ctx.exec_outputs_except("joined")
        await asyncio.gather(*[ctx.fire(b) for b in branches])
        await ctx.fire("joined")


@engine_node
class ForEach:
    """Itera sobre un array disparando loop_body por cada elemento."""
    exec_in = ExecInput()
    array = Input("list", default=None)
    loop_body = ExecOutput()
    completed = ExecOutput()
    element = Output("Any")
    index = Output("int")

    async def run(self, ctx: ExecContext, array: list) -> None:
        for i, element in enumerate(array or []):
            ctx.set_output("element", element)
            ctx.set_output("index", i)
            await ctx.fire("loop_body")
        await ctx.fire("completed")
