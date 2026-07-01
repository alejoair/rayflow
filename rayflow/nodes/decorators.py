"""Node definition: decorators and pin descriptors.

ONE single way to declare pins: descriptors assigned as class attributes.
A data pin's type is ALWAYS a canonical string from rayflow.types
("int", "list[str]", "dict[str, Any]", "Any"). No type annotations, no
Python classes used as types, and no `from __future__ import annotations`.

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

Every node uses the same ExecContext: it locates the FlowEngine by Ray
actor name ("engine_{graph_id}") and can make a blocking ctx.fire() from
any process in the cluster — there is no distinction between engine_node
and ray_node at this level.
"""
from dataclasses import dataclass, field
from typing import Any

import ray

from rayflow.types import parse_type, TypeError_

# Sentinel to detect that a data input has no declared default.
_MISSING = object()

# Attribute under which node metadata is stored.
_NODE_META_ATTR = "__rayflow_node__"


# ---------------------------------------------------------------------------
# Pin descriptors — the only way to declare a pin
# ---------------------------------------------------------------------------

class Input:
    """Data input pin. Usage: x = Input("int", default=5)."""
    def __init__(self, type_str: str = "Any", default: Any = _MISSING):
        self.type_str = type_str
        self.default = default


class Output:
    """Data output pin. Usage: result = Output("float")."""
    def __init__(self, type_str: str = "Any"):
        self.type_str = type_str


class ExecInput:
    """Execution input pin. Usage: exec_in = ExecInput()."""


class ExecOutput:
    """Execution output pin. Usage: exec_out = ExecOutput()."""


# ---------------------------------------------------------------------------
# ExecContext — single, unified, serializable
# ---------------------------------------------------------------------------

class ExecContext:
    """Unified execution context for every node type.

    Locates the FlowEngine and the GraphState by Ray actor name using
    graph_id — works both inside the engine's own process and inside remote
    @ray_node actors. Holds no non-serializable handles in its persistent
    state; it acquires them on demand and caches them locally.

    Sync methods: set_output, get_variable, set_variable, emit_event.
    Async methods: fire, exec_outputs_except.

    _output_writer: optional callable for engine_nodes — avoids a blocking
    remote call back to the engine (a self-call that would deadlock the
    engine actor's event loop). Not serialized; stays None when ctx travels
    to a worker.
    """

    def __init__(
        self,
        node_id: str,
        graph_id: str,
        state_path: str | None = None,
        _output_writer=None,
        _fire_handler=None,
        _response_writer=None,
    ):
        self._node_id = node_id
        self._graph_id = graph_id
        self._state_path = state_path
        self._run_id: str | None = None  # run this execution belongs to
        self._engine_handle = None
        self._state_handle = None
        self._output_writer = _output_writer  # only valid locally
        self._fire_handler = _fire_handler    # only valid locally
        self._response_writer = _response_writer  # only valid locally
        self._pending_outputs: dict[str, Any] = {}  # local in-memory buffer for engine_nodes

    def __getstate__(self):
        # Exclude handles, callbacks, and the local buffer — reacquired on demand.
        # _run_id DOES travel: a @ray_node needs it to scope its return RPCs
        # to the engine (fire/set_output) to the correct run.
        return {
            "_node_id": self._node_id,
            "_graph_id": self._graph_id,
            "_state_path": self._state_path,
            "_run_id": self._run_id,
            "_engine_handle": None,
            "_state_handle": None,
            "_output_writer": None,
            "_fire_handler": None,
            "_response_writer": None,
            "_pending_outputs": {},
        }

    def __setstate__(self, state):
        self.__dict__.update(state)

    # Exposes graph_id so the engine can read it if needed.
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
        """Fires the given exec output pin (blocking: runs the whole downstream subgraph)."""
        if self._fire_handler is not None:
            await self._fire_handler(pin_name)
        else:
            await self._engine().fire.remote(self._run_id, self._node_id, pin_name)

    def set_output(self, pin_name: str, value: Any) -> None:
        """Writes a data output of the current node into the GraphState.

        For engine_nodes: accumulates into a local buffer (_pending_outputs)
        and the engine flushes it asynchronously before continuing. For
        ray_nodes: writes directly to the remote actor (no self-call).
        """
        if self._output_writer is not None:
            self._pending_outputs[pin_name] = value
        else:
            ray.get(self._engine().set_output.remote(self._run_id, self._node_id, pin_name, value))

    def get_variable(self, name: str) -> Any:
        """Reads a variable from the GraphState (prefixed by state_path if applicable)."""
        key = f"{self._state_path}/{name}" if self._state_path else name
        value = ray.get(self._state_actor().get_variable.remote(key))
        if isinstance(value, ray.ObjectRef):
            value = ray.get(value)
        return value

    def set_variable(self, name: str, value: Any) -> None:
        """Writes a variable into the GraphState (prefixed by state_path if applicable)."""
        key = f"{self._state_path}/{name}" if self._state_path else name
        ray.get(self._state_actor().set_variable.remote(key, value))

    def set_response_status(self, status: int) -> None:
        """Sets the HTTP status code for this run's response, if the flow
        is being served over rayflow serve's REST API (a no-op effect for
        MCP tools / programmatic execute() callers — they don't read it).
        Written into this run's RunContext, so whichever branch actually
        executes determines the final status regardless of how many
        FlowOutput nodes the flow has. If two truly parallel branches both
        call this, the last write wins — only one branch of a fork should
        set it."""
        if self._response_writer is not None:
            self._response_writer("status", status)
        else:
            ray.get(self._engine().set_response_meta.remote(self._run_id, "status", status))

    def set_response_header(self, name: str, value: str) -> None:
        """Sets a response header for this run's HTTP response, if served.
        Same caveats as set_response_status regarding parallel branches."""
        if self._response_writer is not None:
            self._response_writer("header", (name, value))
        else:
            ray.get(self._engine().set_response_meta.remote(self._run_id, "header", (name, value)))

    def emit_event(self, event_name: str, payload: Any = None) -> None:
        """Emits an event to the global bus (fire-and-forget)."""
        try:
            from rayflow.events.bus import get_event_broker
            broker = get_event_broker()
            broker.publish.remote(event_name, payload)
        except Exception:
            pass

    async def exec_outputs_except(self, *exclude: str) -> list[str]:
        """Returns the current node's exec output pins, excluding the given ones."""
        return await self._engine().get_exec_outputs.remote(
            self._node_id, list(exclude)
        )


# ---------------------------------------------------------------------------
# Extracted metadata
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
    is_parallel: bool = False
    # Newer fields:
    is_builtin: bool = False           # True for a builtin node, False for custom
    category: str = "General"          # User-facing category: "Control", "Math", etc.
    description: str | None = None     # Class docstring

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
# Decorators
# ---------------------------------------------------------------------------

def ray_node(cls: type) -> type:
    """Registers a class as a Ray node (a distributed actor or task).

    With exec pins → a Ray actor. run_with_ctx(ctx, **inputs) calls run(),
    and the node drives its own flow via ctx.set_output() + await ctx.fire().
    Without exec pins → a Ray task (a pure function evaluated on demand).
    """
    meta = _extract_meta(cls)
    meta.is_engine_node = False
    if meta.is_exec_node:
        original_run = cls.run

        async def run_with_ctx(self, ctx, **inputs):
            await original_run(self, ctx, **inputs)

        cls.run_with_ctx = run_with_ctx

    _strip_pin_descriptors(cls, meta)

    if meta.is_exec_node:
        meta.ray_handle = ray.remote(cls)
    elif getattr(cls, "run", None) is not None:
        meta.ray_handle = ray.remote(_make_data_task(cls))

    setattr(cls, _NODE_META_ATTR, meta)
    return cls


def engine_node(cls: type) -> type:
    """Registers a class as an engine node (runs locally, no Ray involved).

    Same contract as @ray_node: blocking ctx.fire(), ctx.set_output() for
    data outputs. The engine_node/ray_node distinction is only about where
    the node runs, not about what it can do.
    """
    meta = _extract_meta(cls)
    meta.is_engine_node = True
    _strip_pin_descriptors(cls, meta)
    setattr(cls, _NODE_META_ATTR, meta)
    return cls


def parallel_node(cls: type) -> type:
    """Registers a parallel fork/join node.

    The node declares its own run() that uses
    ctx.exec_outputs_except("joined") to discover its dynamic branches and
    asyncio.gather to launch them in parallel.
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
# Metadata extraction
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

    # Extract the docstring as the description.
    description = None
    if cls.__doc__:
        description = cls.__doc__.strip()

    # Extract the category from the class attribute (if present).
    category = getattr(cls, 'category', 'General')  # Defaults to "General"

    return NodeMeta(
        name=cls.__name__,
        py_class=cls,
        inputs=inputs,
        outputs=outputs,
        exec_outputs=exec_outputs,
        has_exec_in=has_exec_in,
        has_exec_out=has_exec_out,
        is_exec_node=is_exec_node,
        description=description,  # ← extracted docstring
        category=category,        # ← class category
    )


def _validate_type(cls: type, pin_name: str, type_str: str) -> None:
    try:
        parse_type(type_str)
    except TypeError_ as e:
        raise TypeError_(f"{cls.__name__}.{pin_name}: {e}")


def _strip_pin_descriptors(cls: type, meta: NodeMeta) -> None:
    """Removes pin descriptors from the class so they don't get in the way inside run()."""
    for name, value in list(vars(cls).items()):
        if isinstance(value, (Input, Output, ExecInput, ExecOutput)):
            try:
                delattr(cls, name)
            except AttributeError:
                pass


def _make_data_task(cls: type):
    """Plain function (a Ray task) that instantiates a data node and calls run."""
    def _data_task(ctx, **inputs: Any) -> dict:
        return cls().run(ctx, **inputs)
    _data_task.__name__ = f"{cls.__name__}_task"
    return _data_task
