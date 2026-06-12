"""Definición de nodos: decoradores y descriptores de pin.

UNA sola forma de declarar pines: descriptores asignados como atributos de clase.
El tipo de un data pin es SIEMPRE un string canónico de rayflow.types
("int", "list[str]", "dict[str, Any]", "Any"). No se usan anotaciones de tipo,
ni clases Python como tipo, ni `from __future__ import annotations`.

    @ray_node
    class Add:
        exec_in = ExecInput()
        a = Input("int", default=0)
        b = Input("int", default=0)
        result = Output("int")
        exec_out = ExecOutput()

        def run(self, ctx: ExecContext, a: int, b: int) -> dict:
            ctx.fire("exec_out")
            return {"result": a + b}

    @engine_node
    class Branch:
        exec_in = ExecInput()
        condition = Input("bool", default=False)
        true = ExecOutput()
        false = ExecOutput()

        def run(self, ctx: ExecContext, condition: bool) -> dict:
            ctx.fire("true" if condition else "false")
            return {}
"""
import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

import ray

from rayflow.types import parse_type, TypeError_

# Sentinel para detectar que un data input no tiene default declarado.
_MISSING = object()

# Atributo donde se almacena la metadata del nodo.
_NODE_META_ATTR = "__rayflow_node__"


# ---------------------------------------------------------------------------
# Descriptores de pin — la única forma de declarar un pin
# ---------------------------------------------------------------------------

class Input:
    """Data input pin. Uso: x = Input("int", default=5).

    type_str es un tipo canónico de rayflow.types. Si se omite el default, el
    pin es requerido (el build exige conexión o literal).
    """
    def __init__(self, type_str: str = "Any", default: Any = _MISSING):
        self.type_str = type_str
        self.default = default


class Output:
    """Data output pin. Uso: result = Output("float")."""
    def __init__(self, type_str: str = "Any"):
        self.type_str = type_str


class ExecInput:
    """Execution input pin. Uso: exec_in = ExecInput()."""


class ExecOutput:
    """Execution output pin. Uso: exec_out = ExecOutput()."""


# ---------------------------------------------------------------------------
# ExecContext — pasado a run() para controlar exec outputs
# ---------------------------------------------------------------------------

class ExecContext:
    """Controla el disparo de exec outputs desde dentro de run().

    En @ray_node: fire() acumula los pins disparados; el engine los recoge
    al finalizar run() y los encola en el ciclo de control.

    En @engine_node: fire() es bloqueante — el engine ejecuta el subgrafo
    conectado al pin antes de retornar el control al nodo.

    get_variable / set_variable solo están disponibles en @engine_node.
    Llamarlos desde un @ray_node lanza NotImplementedError.
    """

    def __init__(
        self,
        fire_fn: Callable[[str], None],
        set_output_fn: Callable[[str, Any], None],
        get_variable_fn: Callable[[str], Any] | None = None,
        set_variable_fn: Callable[[str, Any], None] | None = None,
        emit_event_fn: Callable[[str, Any], None] | None = None,
        graph_id: str | None = None,
    ):
        self._fire_fn = fire_fn
        self._set_output_fn = set_output_fn
        self._get_variable_fn = get_variable_fn
        self._set_variable_fn = set_variable_fn
        self._emit_event_fn = emit_event_fn
        self.graph_id = graph_id

    async def fire(self, pin_name: str) -> None:
        """Dispara el exec output indicado (bloqueante: ejecuta el subgrafo).

        En @engine_node con exec pins, el contrato es `await ctx.fire(pin)`. El
        await es el punto de suspensión donde el engine persiste los outputs ya
        expuestos con set_output antes de hundirse en el subgrafo, y donde varias
        ramas lanzadas con asyncio.gather pueden solaparse.
        """
        result = self._fire_fn(pin_name)
        if inspect.isawaitable(result):
            await result

    def set_output(self, pin_name: str, value: Any) -> None:
        """Expone un data output (útil en @engine_node con outputs intermedios)."""
        self._set_output_fn(pin_name, value)

    def get_variable(self, name: str) -> Any:
        """Lee una variable del GraphState. Solo disponible en @engine_node."""
        if self._get_variable_fn is None:
            raise NotImplementedError("get_variable solo está disponible en @engine_node")
        return self._get_variable_fn(name)

    def set_variable(self, name: str, value: Any) -> None:
        """Escribe una variable en el GraphState. Solo disponible en @engine_node."""
        if self._set_variable_fn is None:
            raise NotImplementedError("set_variable solo está disponible en @engine_node")
        self._set_variable_fn(name, value)

    def emit_event(self, event_name: str, payload: Any = None) -> None:
        """Emite un evento al bus global. Solo disponible en @engine_node."""
        if self._emit_event_fn is None:
            raise NotImplementedError("emit_event solo está disponible en @engine_node")
        self._emit_event_fn(event_name, payload)


# ---------------------------------------------------------------------------
# Metadata extraída
# ---------------------------------------------------------------------------

@dataclass
class PinSpec:
    name: str
    kind: str  # "data_in" | "data_out" | "exec_in" | "exec_out"
    type: str | None = None  # tipo canónico (string), None para exec pins
    default: Any = _MISSING
    required: bool = False

    @property
    def has_default(self) -> bool:
        return self.default is not _MISSING


@dataclass
class NodeMeta:
    name: str
    py_class: type
    ray_handle: Any = None
    inputs: list[PinSpec] = field(default_factory=list)
    outputs: list[PinSpec] = field(default_factory=list)
    exec_outputs: list[str] = field(default_factory=list)
    has_exec_in: bool = False
    has_exec_out: bool = False
    is_exec_node: bool = False
    is_engine_node: bool = False
    is_async: bool = False
    is_parallel: bool = False

    def __getstate__(self):
        # ray_handle no es serializable — se reconstruye en el worker a partir de py_class
        state = self.__dict__.copy()
        state["ray_handle"] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        # Reconstruir ray_handle en el proceso destino
        if not self.is_engine_node and self.is_exec_node and self.py_class is not None:
            self.ray_handle = ray.remote(self.py_class)
        elif not self.is_engine_node and not self.is_exec_node and self.py_class is not None:
            run_fn = getattr(self.py_class, "run", None)
            if run_fn is not None:
                self.ray_handle = ray.remote(_make_data_task(self.py_class))


# ---------------------------------------------------------------------------
# Decoradores
# ---------------------------------------------------------------------------

def ray_node(cls: type) -> type:
    """Registra una clase como nodo Ray (actor o task distribuido).

    - Con exec pins → actor de Ray. El engine llama run_with_ctx(ctx, **inputs)
      que devuelve (fired_pins, outputs_dict).
    - Sin exec pins → task de Ray (función pura sin estado).
    """
    meta = _extract_meta(cls)
    meta.is_engine_node = False
    meta.is_async = inspect.iscoroutinefunction(getattr(cls, "run", None))

    # Inyectar run_with_ctx en la clase para que el actor lo exponga.
    # Si run es una corrutina (async def), el actor expone un método async y el
    # engine lo await-ea vía el ObjectRef — Ray soporta actores async nativamente.
    if meta.is_exec_node:
        original_run = cls.run

        if meta.is_async:
            async def run_with_ctx(self, ctx, **inputs):
                outputs = await original_run(self, ctx, **inputs)
                return (ctx.fired, outputs or {})
        else:
            def run_with_ctx(self, ctx, **inputs):
                outputs = original_run(self, ctx, **inputs)
                return (ctx.fired, outputs or {})

        cls.run_with_ctx = run_with_ctx

    _strip_pin_descriptors(cls, meta)

    if meta.is_exec_node:
        meta.ray_handle = ray.remote(cls)
    elif getattr(cls, "run", None) is not None:
        meta.ray_handle = ray.remote(_make_data_task(cls))

    setattr(cls, _NODE_META_ATTR, meta)
    return cls


def engine_node(cls: type) -> type:
    """Registra una clase como nodo de engine (ejecutado localmente, sin Ray).

    Su run(ctx, **inputs) recibe un ExecContext bloqueante: ctx.fire() ejecuta
    el subgrafo completo antes de retornar. Habilita control de flujo avanzado,
    depuración, TryCatch, CallFlow, etc.
    """
    meta = _extract_meta(cls)
    meta.is_engine_node = True
    meta.is_async = False
    _strip_pin_descriptors(cls, meta)
    setattr(cls, _NODE_META_ATTR, meta)
    return cls


def parallel_node(cls: type) -> type:
    """Registra un nodo de fork/join paralelo.

    El engine lanza cada branch_N como task Ray independiente con su propio
    FlowExecutor parcial. Comparten el GraphState del executor padre.
    El pin 'joined' se dispara cuando todas las ramas terminan.
    """
    meta = _extract_meta(cls)
    meta.is_engine_node = True
    meta.is_parallel = True
    _strip_pin_descriptors(cls, meta)
    setattr(cls, _NODE_META_ATTR, meta)
    return cls


def get_node_meta(cls: type) -> NodeMeta | None:
    return getattr(cls, _NODE_META_ATTR, None)


# ---------------------------------------------------------------------------
# Extracción de metadata
# ---------------------------------------------------------------------------

def _extract_meta(cls: type) -> NodeMeta:
    inputs: list[PinSpec] = []
    outputs: list[PinSpec] = []
    exec_outputs: list[str] = []
    has_exec_in = False
    has_exec_out = False

    seen: set[str] = set()
    members: dict[str, Any] = {}
    for base in reversed(cls.__mro__):
        if base is object:
            continue
        members.update(vars(base))

    for name, value in members.items():
        if name.startswith("_") or name in seen:
            continue

        if isinstance(value, ExecInput):
            has_exec_in = True
            seen.add(name)
        elif isinstance(value, ExecOutput):
            has_exec_out = True
            exec_outputs.append(name)
            seen.add(name)
        elif isinstance(value, Input):
            _validate_type(cls, name, value.type_str)
            inputs.append(PinSpec(
                name=name,
                kind="data_in",
                type=value.type_str,
                default=value.default,
                required=(value.default is _MISSING),
            ))
            seen.add(name)
        elif isinstance(value, Output):
            _validate_type(cls, name, value.type_str)
            outputs.append(PinSpec(name=name, kind="data_out", type=value.type_str))
            seen.add(name)

    is_exec_node = has_exec_in or has_exec_out

    return NodeMeta(
        name=cls.__name__,
        py_class=cls,
        inputs=inputs,
        outputs=outputs,
        exec_outputs=exec_outputs,
        has_exec_in=has_exec_in,
        has_exec_out=has_exec_out,
        is_exec_node=is_exec_node,
    )


def _validate_type(cls: type, pin_name: str, type_str: str) -> None:
    try:
        parse_type(type_str)
    except TypeError_ as e:
        raise TypeError_(f"{cls.__name__}.{pin_name}: {e}")


def _strip_pin_descriptors(cls: type, meta: NodeMeta) -> None:
    """Quita los descriptores de pin de la clase para que no estorben en run()."""
    pin_names = {p.name for p in meta.inputs} | {p.name for p in meta.outputs}
    pin_names |= set(meta.exec_outputs)
    for name, value in list(vars(cls).items()):
        if isinstance(value, (Input, Output, ExecInput, ExecOutput)):
            try:
                delattr(cls, name)
            except AttributeError:
                pass


def _make_data_task(cls: type):
    """Función plana (task de Ray) que instancia el nodo de datos y llama run."""
    def _data_task(**inputs: Any) -> dict:
        return cls().run(**inputs)
    _data_task.__name__ = f"{cls.__name__}_task"
    return _data_task
