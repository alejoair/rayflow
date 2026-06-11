"""Nodos de control de flujo. Se ejecutan localmente en el engine (@engine_node).

ctx.fire() es bloqueante: el subgrafo conectado se ejecuta completo antes de
que run() continúe. Los subgrafos conectados pueden contener @ray_node normales.
"""
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

    def run(self, ctx: ExecContext) -> dict:
        ctx.fire("exec_out")
        return {}


@engine_node
class FlowInput:
    """Punto de entrada para flows con parámetros.

    Sus data outputs se generan en build a partir de los `inputs` del flow.
    El ExecContext expone los valores de entrada via set_output antes de llamar run().
    """
    exec_out = ExecOutput()

    def run(self, ctx: ExecContext) -> dict:
        ctx.fire("exec_out")
        return {}


@engine_node
class FlowOutput:
    """Punto de salida del flow.

    Sus data inputs se generan en build a partir de los `outputs` del flow.
    """
    exec_in = ExecInput()

    def run(self, ctx: ExecContext) -> dict:
        return {}


@engine_node
class OnEvent:
    """Punto de entrada disparado por un evento externo."""
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
        ctx.emit_event(event_name, payload)
        ctx.fire("exec_out")
        return {}


@engine_node
class Branch:
    """Desvío condicional. Dispara `true` o `false` según `condition`."""
    exec_in = ExecInput()
    condition = Input("bool", default=False)
    true = ExecOutput()
    false = ExecOutput()

    def run(self, ctx: ExecContext, condition: bool) -> dict:
        ctx.fire("true" if condition else "false")
        return {}


@engine_node
class Sequence:
    """Dispara sus exec outputs en orden secuencial."""
    exec_in = ExecInput()
    then_0 = ExecOutput()
    then_1 = ExecOutput()
    then_2 = ExecOutput()

    def run(self, ctx: ExecContext) -> dict:
        ctx.fire("then_0")
        ctx.fire("then_1")
        ctx.fire("then_2")
        return {}


@parallel_node
class Parallel:
    """Fork/join paralelo. Lanza branch_0/1/2 simultáneamente como tasks Ray.

    Cada rama corre en su propio FlowExecutor parcial compartiendo el GraphState.
    El pin 'joined' se dispara cuando todas las ramas han terminado.
    """
    exec_in = ExecInput()
    branch_0 = ExecOutput()
    branch_1 = ExecOutput()
    branch_2 = ExecOutput()
    joined = ExecOutput()


@engine_node
class ForEach:
    """Itera sobre un array disparando loop_body por cada elemento."""
    exec_in = ExecInput()
    array = Input("list", default=None)
    loop_body = ExecOutput()
    completed = ExecOutput()
    element = Output("Any")
    index = Output("int")

    def run(self, ctx: ExecContext, array: list) -> dict:
        for i, element in enumerate(array or []):
            ctx.set_output("element", element)
            ctx.set_output("index", i)
            ctx.fire("loop_body")
        ctx.fire("completed")
        return {}
