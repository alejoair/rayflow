from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
import time
import uuid

import ray

from rayflow.build.validator import BuiltFlow, ResolvedNode
from rayflow.nodes.decorators import ExecContext
from rayflow.state.actor import GraphState


@dataclass
class RunContext:
    """Isolation boundary for a single flow execution (run).

    Owns all of a run's transient scratch state: identity, the event queue
    handle, node outputs (per-run scoped), AND-join readiness, and the
    flow result accumulator. What's persistent and shared across runs
    (GraphState variables, @ray_node `self`) lives outside this object.

    By threading a RunContext through each execute() call instead of keeping
    the active run in `self`, the engine supports isolated concurrent runs
    with no lock.
    """

    run_id: str
    queue: Any                                          # RunQueue handle
    node_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)  # node_id → {pin → value}
    exec_arrivals: dict[str, set[str]] = field(default_factory=dict)       # AND-join readiness
    output_refs: dict[str, Any] = field(default_factory=dict)              # result accumulator
    response_status: int = 200                          # set via ctx.set_response_status()
    response_headers: dict[str, str] = field(default_factory=dict)         # set via ctx.set_response_header()


def _var_key(state_path: str | None, var_name: str) -> str:
    return f"{state_path}/{var_name}" if state_path else var_name


def _resolve_refs(obj: Any) -> Any:
    """Recursively resolves nested ObjectRefs in dicts and lists."""
    if isinstance(obj, ray.ObjectRef):
        return _resolve_refs(ray.get(obj))
    if isinstance(obj, dict):
        return {k: _resolve_refs(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs(v) for v in obj]
    return obj


@ray.remote
class FlowEngine:
    """Stateful execution engine for an already-built flow (BuiltFlow).

    The actor lives as long as the flow stays loaded. GraphState and the
    @ray_node actors are created in __init__ and persist across executions —
    variables keep their value between requests.

    Each execute() call is serialized by Ray (the actor's event loop): if a
    second request arrives while the first is running, it waits in queue.

    Emits events to a per-execution RunQueue for SSE streaming to the client.
    """

    def __init__(
        self,
        built: BuiltFlow,
        actors: dict[str, Any],
    ):
        self._built = built
        self._actors: dict[str, Any] = actors

        # Persistent GraphState — initialized with variable defaults.
        var_defaults = {v.name: v.default for v in self._built.flow_def.variables}
        self._state = GraphState.options(
            name=f"gs_{self._get_graph_id()}",
            namespace="rayflow",
            lifetime="detached",
        ).remote(var_defaults)

        # Live runs, indexed by run_id. Each owns its own scratch state
        # (RunContext: run_id, queue, node_outputs, exec_arrivals, output_refs)
        # — nothing per-run lives on self, so two concurrent execute() calls
        # are isolated and the async actor can interleave them with no lock.
        # The only thing shared across runs is what should be: GraphState
        # variables and @ray_node `self`.
        self._runs: dict[str, RunContext] = {}

    def _get_graph_id(self) -> str:
        # graph_id is derived from the engine actor's name — assigned in LoadedFlow.
        # We use the flow's name as a stable base.
        return self._built.flow_def.name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(self, flow_inputs: dict[str, Any], queue_ref: Any, run_id: str) -> dict[str, Any]:
        """Executes the flow with the given inputs, emitting events to queue_ref.

        All of a run's scratch state lives in a local RunContext (not in
        self), threaded through the internal methods. No lock: two
        concurrent execute() calls are isolated by their own RunContext and
        the async actor can interleave them.
        """
        run = RunContext(run_id=run_id, queue=queue_ref)
        for node_id, rnode in self._built.nodes.items():
            if rnode.exec_join == "and" and len(rnode.exec_sources) > 1:
                run.exec_arrivals[node_id] = set()
        self._runs[run_id] = run

        try:
            await self._write_node_outputs(run, self._built.entry_node_id, dict(flow_inputs))
            await self._run_loop(run, self._built.entry_node_id)
            result = _resolve_refs(run.output_refs)
            await queue_ref.push.remote(run_id, {
                "event": "flow_done", "result": result, "ts": time.time(),
                "response_status": run.response_status,
                "response_headers": run.response_headers,
            })
            return result
        except Exception as e:
            await queue_ref.push.remote(run_id, {"event": "flow_error", "error": str(e), "ts": time.time()})
            raise
        finally:
            self._runs.pop(run_id, None)

    async def fire(self, run_id: str, source_node_id: str, pin_name: str) -> None:
        run = self._runs[run_id]
        rnode = self._built.nodes[source_node_id]
        await self._local_fire(run, source_node_id, rnode, pin_name)

    async def _local_fire(self, run: RunContext, source_node_id: str, rnode: Any, pin_name: str) -> None:
        targets = rnode.exec_targets.get(pin_name, [])
        if targets:
            # Awaited (not fire-and-forget): otherwise execute() can return
            # (its flow_done push IS awaited) before this event reaches the
            # RunQueue mailbox, so a driver draining the queue sees flow_done
            # first and closes the run — the trace ends up empty or mis-ordered.
            await run.queue.push.remote(run.run_id, {
                "event": "edge_fire",
                "from": source_node_id,
                "to": targets[0],
                "pin": pin_name,
                "ts": time.time(),
            })
        if len(targets) > 1:
            await asyncio.gather(*[self._run_loop(run, t, source_node_id) for t in targets])
        elif targets:
            await self._run_loop(run, targets[0], source_node_id)

    async def set_output(self, run_id: str, node_id: str, pin_name: str, value: Any) -> None:
        run = self._runs[run_id]
        await self._write_node_outputs(run, node_id, {pin_name: value})

    async def set_response_meta(self, run_id: str, kind: str, value: Any) -> None:
        """RPC path for ctx.set_response_status()/set_response_header() from
        a @ray_node running in a separate worker process. An engine_node
        instead uses a local closure (see _fire_engine_node) that writes
        directly to `run`, avoiding a blocking self-call."""
        run = self._runs[run_id]
        if kind == "status":
            run.response_status = value
        elif kind == "header":
            name, header_value = value
            run.response_headers[name] = header_value

    async def get_exec_outputs(self, node_id: str, exclude: list[str]) -> list[str]:
        rnode = self._built.nodes[node_id]
        return [p for p in rnode.meta.exec_outputs if p not in exclude]

    def get_graph_id(self) -> str:
        return self._get_graph_id()

    # ------------------------------------------------------------------
    # Internal execution loop
    # ------------------------------------------------------------------

    async def _run_loop(self, run: RunContext, entry_id: str, arrived_from: str | None = None) -> None:
        if not self._is_ready(run, entry_id, arrived_from):
            return
        next_ids = await self._fire_node(run, entry_id)
        if len(next_ids) > 1:
            await asyncio.gather(*[self._run_loop(run, nid, entry_id) for nid in next_ids])
        elif next_ids:
            await self._run_loop(run, next_ids[0], entry_id)

    def _is_ready(self, run: RunContext, node_id: str, arrived_from: str | None) -> bool:
        if node_id not in run.exec_arrivals:
            return True
        arrivals = run.exec_arrivals[node_id]
        if arrived_from is not None:
            arrivals.add(arrived_from)
        if len(arrivals) >= len(self._built.nodes[node_id].exec_sources):
            # Reset for the next wave: an AND join visited more than once
            # (inside a loop / re-entrancy) must wait on ALL its sources
            # again, not stay permanently "ready".
            arrivals.clear()
            return True
        return False

    async def _fire_node(self, run: RunContext, node_id: str) -> list[str]:
        rnode = self._built.nodes[node_id]
        if rnode.node_def.subflow_entry is not None:
            return await self._fire_callflow_node(run, node_id, rnode)
        if rnode.meta.is_engine_node or rnode.meta.is_parallel:
            return await self._fire_engine_node(run, node_id, rnode)
        return await self._fire_ray_node(run, node_id, rnode)

    # ------------------------------------------------------------------
    # CallFlow
    # ------------------------------------------------------------------

    async def _fire_callflow_node(self, run: RunContext, node_id: str, rnode: ResolvedNode) -> list[str]:
        started_at = time.time()
        entry_id = rnode.node_def.subflow_entry
        exit_id = rnode.node_def.subflow_exit

        if rnode.node_def.subflow_vars:
            sub_state = self._built.nodes[entry_id].state_path
            for var_name, default in rnode.node_def.subflow_vars:
                await self._state.set_variable.remote(
                    _var_key(sub_state, var_name), default
                )

        await self._run_loop(run, entry_id)

        result: dict[str, Any] = {}
        if exit_id is not None:
            exit_rnode = self._built.nodes[exit_id]
            for pin_name in exit_rnode.resolved_inputs:
                result[pin_name] = await self._resolve_pin(run, exit_rnode, pin_name)

        duration_ms = (time.time() - started_at) * 1000
        await self._write_node_outputs(run, node_id, {
            "result": result,
            "meta": self._build_meta(node_id, rnode, started_at, duration_ms),
        })
        return rnode.exec_targets.get("exec_out", [])

    # ------------------------------------------------------------------
    # @engine_node and @parallel_node
    # ------------------------------------------------------------------

    async def _fire_engine_node(self, run: RunContext, node_id: str, rnode: ResolvedNode) -> list[str]:
        name = rnode.meta.name
        resolved = await self._resolve_inputs(run, rnode)
        inputs = {k: await v for k, v in resolved.items()}

        if name == "FlowOutput":
            if rnode.node_def.subflow_of is None:
                run.output_refs.update(inputs)
            return []

        if name in ("OnStart", "OnEvent", "OnVariableChange"):
            await self._write_node_outputs(run, node_id, inputs)
            targets = rnode.exec_targets.get("exec_out", [])
            if len(targets) > 1:
                await asyncio.gather(*[self._run_loop(run, t, node_id) for t in targets])
            elif targets:
                await self._run_loop(run, targets[0], node_id)
            return []

        graph_id = self._get_graph_id()
        ctx = ExecContext(node_id, graph_id, rnode.state_path)

        async def _engine_fire(pin: str) -> None:
            # Flushes accumulated outputs to the RunContext only if there are
            # successor nodes that can read them. Avoids writes on every
            # iteration of a loop whose pin (e.g. loop_body) has no direct
            # targets.
            targets = rnode.exec_targets.get(pin, [])
            if ctx._pending_outputs and targets:
                await self._write_node_outputs(run, node_id, ctx._pending_outputs.copy())
                ctx._pending_outputs.clear()
            await self._local_fire(run, node_id, rnode, pin)

        def _response_writer(kind: str, value: Any) -> None:
            # Same rationale as _output_writer/_fire_handler: writes `run`
            # directly instead of an RPC back to this same actor, which
            # would deadlock (see set_response_meta's docstring).
            if kind == "status":
                run.response_status = value
            elif kind == "header":
                name, header_value = value
                run.response_headers[name] = header_value

        ctx._output_writer = lambda nid, pin, val: None  # set_output accumulates into _pending_outputs
        ctx._fire_handler = _engine_fire
        ctx._response_writer = _response_writer

        started_at = time.time()
        await self._emit_node_start(run, node_id, rnode)
        await self._write_node_outputs(run, node_id, {"meta": self._build_meta(node_id, rnode, started_at, 0.0)})

        run_fn = getattr(rnode.meta.py_class, "run", None)
        if run_fn is not None:
            instance = rnode.meta.py_class()
            await instance.run(ctx, **inputs)

        if ctx._pending_outputs:
            await self._write_node_outputs(run, node_id, ctx._pending_outputs)
            ctx._pending_outputs.clear()

        duration_ms = (time.time() - started_at) * 1000
        await self._write_node_outputs(run, node_id, {"meta": self._build_meta(node_id, rnode, started_at, duration_ms)})
        await self._emit_node_done(run, node_id, rnode, duration_ms)
        return []

    # ------------------------------------------------------------------
    # @ray_node
    # ------------------------------------------------------------------

    async def _fire_ray_node(self, run: RunContext, node_id: str, rnode: ResolvedNode) -> list[str]:
        actor = self._actors[node_id]
        resolved = await self._resolve_inputs(run, rnode)

        graph_id = self._get_graph_id()
        ctx = ExecContext(node_id, graph_id, rnode.state_path)
        ctx._run_id = run.run_id  # travels serialized to the worker: return RPCs (fire/set_output) are scoped to this run

        started_at = time.time()
        await self._emit_node_start(run, node_id, rnode)
        await self._write_node_outputs(run, node_id, {"meta": self._build_meta(node_id, rnode, started_at, 0.0)})

        await actor.run_with_ctx.remote(ctx, **resolved)

        duration_ms = (time.time() - started_at) * 1000
        await self._write_node_outputs(run, node_id, {"meta": self._build_meta(node_id, rnode, started_at, duration_ms)})
        await self._emit_node_done(run, node_id, rnode, duration_ms)
        return []

    # ------------------------------------------------------------------
    # Pushing events to the RunQueue
    # ------------------------------------------------------------------

    async def _emit_node_start(self, run: RunContext, node_id: str, rnode: ResolvedNode) -> None:
        if run.queue is None:
            return
        # Awaited (not fire-and-forget): see _local_fire. Awaiting guarantees
        # the event is in the RunQueue mailbox before the next one is pushed,
        # so a driver draining the queue sees node_start before node_done and
        # both before flow_done.
        await run.queue.push.remote(run.run_id, {
            "event": "node_start",
            "node_id": node_id,
            "node_type": rnode.meta.name,
            "ts": time.time(),
        })

    async def _emit_node_done(self, run: RunContext, node_id: str, rnode: ResolvedNode, duration_ms: float) -> None:
        if run.queue is None:
            return
        await run.queue.push.remote(run.run_id, {
            "event": "node_done",
            "node_id": node_id,
            "node_type": rnode.meta.name,
            "duration_ms": round(duration_ms, 3),
            "ts": time.time(),
        })

    # ------------------------------------------------------------------
    # Data input resolution
    # ------------------------------------------------------------------

    async def _resolve_inputs(self, run: RunContext, rnode: ResolvedNode) -> dict[str, Any]:
        return {
            pin_name: await self._resolve_pin(run, rnode, pin_name)
            for pin_name in rnode.resolved_inputs
        }

    async def _resolve_pin(self, run: RunContext, rnode: ResolvedNode, pin_name: str) -> Any:
        res_pin = rnode.resolved_inputs[pin_name]

        if not res_pin.is_ref:
            return ray.put(res_pin.literal)

        src_id = res_pin.source_node
        src_pin = res_pin.source_pin
        src_rnode = self._built.nodes.get(src_id)

        # Read from per-run scratch: if the producer wasn't fired IN THIS run,
        # there's no entry, and we fall back to the default (or evaluate the
        # pure node). Staleness across runs disappears by construction
        # (run.node_outputs starts empty on every execute()).
        node_outs = run.node_outputs.get(src_id)
        ref = node_outs.get(src_pin) if node_outs is not None else None
        if ref is not None:
            if isinstance(ref, ray.ObjectRef):
                ref = await ref
            return ray.put(ref)

        if src_rnode and not src_rnode.meta.is_exec_node:
            value = await self._eval_pure_engine_node(run, src_rnode, src_pin)
            return ray.put(value)

        consumer_pin = next(
            (p for p in rnode.meta.inputs if p.name == pin_name), None
        )
        default = consumer_pin.default if consumer_pin and consumer_pin.has_default else None
        return ray.put(default)

    async def _eval_pure_engine_node(self, run: RunContext, rnode: ResolvedNode, src_pin: str) -> Any:
        resolved = await self._resolve_inputs(run, rnode)
        inputs = {k: await v for k, v in resolved.items()}
        graph_id = self._get_graph_id()
        ctx = ExecContext(rnode.node_def.id, graph_id, rnode.state_path)
        run_fn = getattr(rnode.meta.py_class, "run", None)
        if run_fn is None:
            return None
        outputs = await rnode.meta.py_class().run(ctx, **inputs) or {}
        return outputs.get(src_pin)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_meta(self, node_id: str, rnode: ResolvedNode, started_at: float, duration_ms: float) -> dict:
        return {
            "id": node_id,
            "type": rnode.meta.name,
            "flow": rnode.node_def.flow_name or self._built.flow_def.name,
            "started_at": started_at,
            "duration_ms": round(duration_ms, 3),
        }

    async def _write_node_outputs(self, run: RunContext, node_id: str, outputs: dict[str, Any]) -> None:
        # Per-run scratch: a plain in-memory dict, no GraphState round-trip.
        existing = run.node_outputs.get(node_id)
        if existing is None:
            run.node_outputs[node_id] = dict(outputs)
        else:
            existing.update(outputs)


# ---------------------------------------------------------------------------
# LoadedFlow — lifecycle of a flow loaded into Ray
# ---------------------------------------------------------------------------

class LoadedFlow:
    """A flow with live Ray actors and persistent GraphState.

    Created with LoadedFlow.load(built) and destroyed with .unload().
    Between requests, GraphState keeps variable values around.
    """

    def __init__(self, graph_id: str, engine: Any, actors: dict[str, Any], queue: Any, flow_def=None):
        self.graph_id = graph_id
        self._engine = engine
        self._actors = actors
        self._queue = queue
        self.flow_def = flow_def  # original FlowDef, for interface inspection

    @classmethod
    def load(cls, built: BuiltFlow) -> "LoadedFlow":
        graph_id = built.flow_def.name

        # Destroy previous actors if they existed (reload).
        for actor_name in (f"engine_{graph_id}", f"gs_{graph_id}", f"queue_{graph_id}"):
            try:
                ray.kill(ray.get_actor(actor_name, namespace="rayflow"))
            except Exception:
                pass

        # Spawn @ray_node actors.
        actors: dict[str, Any] = {}
        for node_id, rnode in built.nodes.items():
            if rnode.meta.is_engine_node or rnode.meta.is_parallel:
                continue
            if rnode.meta.is_exec_node and rnode.meta.ray_handle is not None:
                # Destroy a previous actor of the same name if it exists.
                try:
                    old_actor = ray.get_actor(f"{node_id}_{graph_id}", namespace="rayflow")
                    ray.kill(old_actor)
                except Exception:
                    pass
                actor = rnode.meta.ray_handle.options(
                    name=f"{node_id}_{graph_id}",
                    namespace="rayflow",
                    lifetime="detached",
                ).remote()
                actors[node_id] = actor

        from rayflow.state.queue import RunQueue
        queue = RunQueue.options(
            name=f"queue_{graph_id}",
            namespace="rayflow",
            lifetime="detached",
        ).remote()

        engine = FlowEngine.options(
            name=f"engine_{graph_id}",
            namespace="rayflow",
            lifetime="detached",
        ).remote(built, actors)

        # Wait for the engine to finish __init__ (which creates GraphState)
        # before returning: this guarantees engine_{graph_id} and
        # gs_{graph_id} are resolvable by name as soon as load() returns —
        # needed, e.g., by variable-watch registration for a flow served
        # afterward.
        ray.get(engine.get_graph_id.remote())

        return cls(graph_id, engine, actors, queue, flow_def=built.flow_def)

    def execute(self, flow_inputs: dict[str, Any], run_id: str) -> Any:
        """Dispatches execute() on the engine and returns the ObjectRef (non-blocking)."""
        return self._engine.execute.remote(flow_inputs, self._queue, run_id)

    def unload(self) -> None:
        """Destroys every actor belonging to the flow."""
        for actor in self._actors.values():
            try:
                ray.kill(actor)
            except Exception:
                pass
        for actor in (self._engine, self._queue):
            try:
                ray.kill(actor)
            except Exception:
                pass
        try:
            ray.kill(ray.get_actor(f"gs_{self.graph_id}", namespace="rayflow"))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Global registry of loaded flows (in the driver process)
# ---------------------------------------------------------------------------

_loaded_flows: dict[str, LoadedFlow] = {}


def get_loaded_flow(name: str) -> LoadedFlow | None:
    return _loaded_flows.get(name)


def load_flow_into_ray(built: BuiltFlow) -> LoadedFlow:
    lf = LoadedFlow.load(built)
    _loaded_flows[built.flow_def.name] = lf
    return lf


def unload_flow_from_ray(name: str) -> None:
    lf = _loaded_flows.pop(name, None)
    if lf:
        lf.unload()


def is_flow_loaded(name: str) -> bool:
    return name in _loaded_flows
