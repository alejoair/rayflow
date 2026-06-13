"""Nodos de control de flujo."""
import asyncio
import inspect
from typing import Any

from rayflow.nodes.decorators import (
    ExecContext,
    ExecInput,
    ExecOutput,
    Input,
    Output,
    engine_node,
    parallel_node,
    ray_node,
)


class _MapCaptureCtx:
    """Contexto de captura para Map: recoge set_output, ignora fire().

    Permite ejecutar el run() de cualquier nodo inline (sin actores Ray)
    capturando sus data outputs sin propagar el exec flow.
    Las operaciones de variables/eventos se delegan al contexto padre.
    """

    def __init__(self, parent: ExecContext):
        self._parent = parent
        self.outputs: dict[str, Any] = {}

    async def fire(self, pin_name: str) -> None:
        pass

    def set_output(self, pin_name: str, value: Any) -> None:
        self.outputs[pin_name] = value

    def get_variable(self, name: str) -> Any:
        return self._parent.get_variable(name)

    def set_variable(self, name: str, value: Any) -> None:
        self._parent.set_variable(name, value)

    def emit_event(self, event_name: str, payload: Any = None) -> None:
        self._parent.emit_event(event_name, payload)

    async def exec_outputs_except(self, *exclude: str) -> list[str]:
        return []


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


@ray_node
class Branch:
    """Desvío condicional. Dispara `true` o `false` según `condition`."""
    exec_in = ExecInput()
    condition = Input("bool", default=False)
    true = ExecOutput()
    false = ExecOutput()

    async def run(self, ctx: ExecContext, condition: bool) -> None:
        await ctx.fire("true" if condition else "false")


@ray_node
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


@engine_node
class While:
    """Itera mientras una variable booleana sea True.

    Lee la variable `condition_var` del GraphState al inicio de cada iteración.
    El loop body es responsable de actualizarla (via Set) para controlar la salida.

    Ejemplo de uso en JSON:
        variables: [{"name": "keep_going", "type": "bool", "default": true}]
        {"id": "w", "type": "While", "exec_in": "entry",
         "inputs": {"condition_var": "keep_going"}}
    """
    exec_in = ExecInput()
    condition_var = Input("str", default="")
    loop_body = ExecOutput()
    completed = ExecOutput()

    async def run(self, ctx: ExecContext, condition_var: str) -> None:
        while ctx.get_variable(condition_var):
            await ctx.fire("loop_body")
        await ctx.fire("completed")


@engine_node
class Map:
    """Aplica un nodo de transformación a cada elemento de un array.

    `node_type` es el nombre del tipo de nodo (string literal en el JSON).
    El elemento se pasa al primer data input del nodo; los demás inputs
    usan sus valores por defecto declarados. El primer data output de cada
    invocación se recoge en la lista resultado.

    Funciona con cualquier nodo del catálogo (pure o exec, engine o ray_node).
    Los exec outputs del nodo aplicado se ignoran — Map solo captura datos.

    Ejemplo de uso en JSON:
        {"id": "m", "type": "Map", "exec_in": "entry",
         "inputs": {"array": "entry.items", "node_type": "ToStr"}}
    """
    exec_in = ExecInput()
    array = Input("list", default=None)
    node_type = Input("str", default="")
    result = Output("list")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, array: list, node_type: str) -> None:
        from rayflow.nodes.registry import get_catalog
        entry = get_catalog().get(node_type)
        if entry is None:
            raise RuntimeError(f"Map: nodo '{node_type}' no encontrado en el catálogo")
        cls, meta = entry
        if not meta.inputs:
            raise RuntimeError(f"Map: '{node_type}' no tiene data inputs")
        if not meta.outputs:
            raise RuntimeError(f"Map: '{node_type}' no tiene data outputs")

        first_in = meta.inputs[0].name
        first_out = meta.outputs[0].name
        base_inputs = {pin.name: pin.default for pin in meta.inputs if pin.has_default}

        results = []
        for element in (array or []):
            inputs = {**base_inputs, first_in: element}
            node_instance = cls()
            capture = _MapCaptureCtx(ctx)
            ret = node_instance.run(capture, **inputs)
            if inspect.isawaitable(ret):
                ret = await ret
            # pure nodes devuelven dict; exec nodes usan set_output (ret=None)
            if isinstance(ret, dict):
                results.append(ret.get(first_out))
            else:
                results.append(capture.outputs.get(first_out))

        ctx.set_output("result", results)
        await ctx.fire("exec_out")
