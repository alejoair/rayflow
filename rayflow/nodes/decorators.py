"""Definición de nodos: decoradores y descriptores de pin.

UNA sola forma de declarar pines: descriptores asignados como atributos de clase.
El tipo de un data pin es SIEMPRE un string canónico de rayflow.types
("int", "list[str]", "dict[str, Any]", "Any"). No se usan anotaciones de tipo,
ni clases Python como tipo, ni `from __future__ import annotations`.

    @node
    class Add:
        exec_in = ExecInput()
        a = Input("int", default=0)
        b = Input("int", default=0)
        result = Output("int")
        exec_out = ExecOutput()

        async def run(self, ctx: ExecContext, a: int, b: int) -> None:
            ctx.set_output("result", a + b)
            await ctx.fire("exec_out")

Todos los nodos usan el mismo ExecContext: localiza el FlowEngine por nombre de
actor Ray ("engine_{graph_id}") y puede hacer ctx.fire() bloqueante desde
cualquier proceso del cluster — no hay distinción entre engine_node y ray_node.
"""
import inspect
from dataclasses import dataclass, field
from typing import Any

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
    """Data input pin. Uso: x = Input("int", default=5)."""
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
# ExecContext — único, unificado, serializable
# ---------------------------------------------------------------------------

class ExecContext:
    """Contexto de ejecución unificado para todos los nodos.

    Localiza el FlowEngine y el GraphState por nombre de actor Ray usando
    graph_id — funciona tanto en el proceso del engine como en actores
    @ray_node remotos. No contiene handles no-serializables en su estado
    persistente; los adquiere bajo demanda y los cachea localmente.

    Métodos sync: set_output, get_variable, set_variable, emit_event.
    Métodos async: fire, exec_outputs_except.

    _output_writer: callable opcional para engine_nodes — evita la llamada
    remota bloqueante al engine (self-call que deadlockearía el event loop
    del actor). No se serializa; queda None cuando el ctx viaja a un worker.
    """

    def __init__(
        self,
        node_id: str,
        graph_id: str,
        state_path: str | None = None,
        _output_writer=None,
    ):
        self._node_id = node_id
        self._graph_id = graph_id
        self._state_path = state_path
        self._engine_handle = None
        self._state_handle = None
        self._output_writer = _output_writer  # solo válido localmente

    def __getstate__(self):
        # Excluir handles y callbacks — se reacquieren bajo demanda.
        return {
            "_node_id": self._node_id,
            "_graph_id": self._graph_id,
            "_state_path": self._state_path,
            "_engine_handle": None,
            "_state_handle": None,
            "_output_writer": None,
        }

    def __setstate__(self, state):
        self.__dict__.update(state)

    # Acceso al graph_id para que el engine pueda leerlo si es necesario.
    @property
    def graph_id(self) -> str:
        return self._graph_id

    def _engine(self):
        if self._engine_handle is None:
            self._engine_handle = ray.get_actor(
                f"engine_{self._graph_id}", namespace="rayflow"
            )
        return self._engine_handle

    def _state_actor(self):
        if self._state_handle is None:
            self._state_handle = ray.get_actor(
                f"gs_{self._graph_id}", namespace="rayflow"
            )
        return self._state_handle

    async def fire(self, pin_name: str) -> None:
        """Dispara el exec output indicado (bloqueante: ejecuta el subgrafo completo)."""
        await self._engine().fire.remote(self._node_id, pin_name)

    def set_output(self, pin_name: str, value: Any) -> None:
        """Escribe un data output del nodo actual en el GraphState."""
        if self._output_writer is not None:
            self._output_writer(self._node_id, pin_name, value)
        else:
            ray.get(self._engine().set_output.remote(self._node_id, pin_name, value))

    def get_variable(self, name: str) -> Any:
        """Lee una variable del GraphState (con prefijo state_path si aplica)."""
        key = f"{self._state_path}/{name}" if self._state_path else name
        value = ray.get(self._state_actor().get_variable.remote(key))
        if isinstance(value, ray.ObjectRef):
            value = ray.get(value)
        return value

    def set_variable(self, name: str, value: Any) -> None:
        """Escribe una variable en el GraphState (con prefijo state_path si aplica)."""
        key = f"{self._state_path}/{name}" if self._state_path else name
        ray.get(self._state_actor().set_variable.remote(key, value))

    def emit_event(self, event_name: str, payload: Any = None) -> None:
        """Emite un evento al bus global (fire-and-forget)."""
        try:
            from rayflow.events.bus import get_event_broker
            broker = get_event_broker()
            broker.publish.remote(event_name, payload)
        except Exception:
            pass

    async def exec_outputs_except(self, *exclude: str) -> list[str]:
        """Devuelve los exec output pins del nodo actual excepto los excluidos."""
        return await self._engine().get_exec_outputs.remote(
            self._node_id, list(exclude)
        )


# ---------------------------------------------------------------------------
# Metadata extraída
# ---------------------------------------------------------------------------

@dataclass
class PinSpec:
    name: str
    kind: str  # "data_in" | "data_out" | "exec_in" | "exec_out"
    type: str | None = None
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
        state = self.__dict__.copy()
        state["ray_handle"] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
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

    Con exec pins → actor de Ray. run_with_ctx(ctx, **inputs) invoca run() y
    el nodo controla su propio flujo via ctx.set_output() + await ctx.fire().
    Sin exec pins → task de Ray (función pura evaluada bajo demanda).
    """
    meta = _extract_meta(cls)
    meta.is_engine_node = False
    meta.is_async = inspect.iscoroutinefunction(getattr(cls, "run", None))

    if meta.is_exec_node:
        original_run = cls.run

        async def run_with_ctx(self, ctx, **inputs):
            result = original_run(self, ctx, **inputs)
            if inspect.isawaitable(result):
                await result

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

    Mismo contrato que @ray_node: ctx.fire() bloqueante, ctx.set_output() para
    data outputs. La distinción engine_node/ray_node es solo sobre dónde corre
    el nodo, no sobre sus capacidades.
    """
    meta = _extract_meta(cls)
    meta.is_engine_node = True
    meta.is_async = False
    _strip_pin_descriptors(cls, meta)
    setattr(cls, _NODE_META_ATTR, meta)
    return cls


def parallel_node(cls: type) -> type:
    """Registra un nodo de fork/join paralelo.

    El nodo declara su propio run() que usa ctx.exec_outputs_except("joined")
    para descubrir sus ramas dinámicas y asyncio.gather para lanzarlas en paralelo.
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
