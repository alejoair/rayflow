from __future__ import annotations

import asyncio
from typing import Any
import inspect
import time
import uuid

import ray

from rayflow.build.validator import BuiltFlow, ResolvedNode
from rayflow.nodes.decorators import ExecContext
from rayflow.state.actor import GraphState


def _var_key(state_path: str | None, var_name: str) -> str:
    return f"{state_path}/{var_name}" if state_path else var_name


@ray.remote
class FlowEngine:
    """Motor de ejecución stateful de un flow ya construido (BuiltFlow).

    El actor vive mientras el flow esté cargado. El GraphState y los actores
    @ray_node se crean en __init__ y persisten entre ejecuciones — las variables
    mantienen su valor entre requests.

    Cada llamada a execute() es serializada por Ray (event loop del actor):
    si llega un segundo request mientras el primero corre, espera en la cola.

    Emite eventos a una RunQueue por ejecución para streaming SSE al cliente.
    """

    def __init__(
        self,
        built: BuiltFlow,
        actors: dict[str, Any],
    ):
        self._built = built
        self._actors: dict[str, Any] = actors

        # GraphState persistente — se inicializa con los defaults de variables
        var_defaults = {v.name: v.default for v in self._built.flow_def.variables}
        self._state = GraphState.options(
            name=f"gs_{self._get_graph_id()}",
            namespace="rayflow",
            lifetime="detached",
        ).remote(var_defaults)

        # Estado por ejecución — se resetea en cada execute()
        self._output_refs: dict[str, Any] = {}
        self._exec_arrivals: dict[str, set[str]] = {}
        self._run_queue: Any | None = None  # handle a RunQueue activo

    def _get_graph_id(self) -> str:
        # El graph_id se deriva del nombre del actor engine — se asigna en LoadedFlow
        # Usamos el nombre del flow como base estable
        return self._built.flow_def.name

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    async def execute(self, flow_inputs: dict[str, Any], queue_ref: Any) -> dict[str, Any]:
        """Ejecuta el flow con los inputs dados, emitiendo eventos a queue_ref."""
        self._run_queue = queue_ref
        self._output_refs = {}
        self._exec_arrivals = {}

        for node_id, rnode in self._built.nodes.items():
            if rnode.exec_join == "and" and len(rnode.exec_sources) > 1:
                self._exec_arrivals[node_id] = set()

        self._write_node_outputs(self._built.entry_node_id, dict(flow_inputs))

        try:
            await self._run_loop(self._built.entry_node_id)
            result = dict(self._output_refs)
            ray.get(queue_ref.push.remote({"event": "flow_done", "result": result, "ts": time.time()}))
            return result
        except Exception as e:
            ray.get(queue_ref.push.remote({"event": "flow_error", "error": str(e), "ts": time.time()}))
            raise

    async def fire(self, source_node_id: str, pin_name: str) -> None:
        rnode = self._built.nodes[source_node_id]
        targets = rnode.exec_targets.get(pin_name, [])
        if targets:
            ray.get(self._run_queue.push.remote({
                "event": "edge_fire",
                "from": source_node_id,
                "to": targets[0],
                "pin": pin_name,
                "ts": time.time(),
            }))
        if len(targets) > 1:
            await asyncio.gather(*[self._run_loop(t, source_node_id) for t in targets])
        elif targets:
            await self._run_loop(targets[0], source_node_id)

    async def set_output(self, node_id: str, pin_name: str, value: Any) -> None:
        ray.get(self._state.set_node_outputs.remote(node_id, {pin_name: value}))

    async def get_exec_outputs(self, node_id: str, exclude: list[str]) -> list[str]:
        rnode = self._built.nodes[node_id]
        return [p for p in rnode.meta.exec_outputs if p not in exclude]

    def get_graph_id(self) -> str:
        return self._get_graph_id()

    # ------------------------------------------------------------------
    # Ciclo interno
    # ------------------------------------------------------------------

    async def _run_loop(self, entry_id: str, arrived_from: str | None = None) -> None:
        if not self._is_ready(entry_id, arrived_from):
            return
        next_ids = await self._fire_node(entry_id)
        if len(next_ids) > 1:
            await asyncio.gather(*[self._run_loop(nid, entry_id) for nid in next_ids])
        elif next_ids:
            await self._run_loop(next_ids[0], entry_id)

    def _is_ready(self, node_id: str, arrived_from: str | None) -> bool:
        if node_id not in self._exec_arrivals:
            return True
        arrivals = self._exec_arrivals[node_id]
        if arrived_from is not None:
            arrivals.add(arrived_from)
        return len(arrivals) >= len(self._built.nodes[node_id].exec_sources)

    async def _fire_node(self, node_id: str) -> list[str]:
        rnode = self._built.nodes[node_id]
        if rnode.node_def.subflow_entry is not None:
            return await self._fire_callflow_node(node_id, rnode)
        if rnode.meta.is_engine_node or rnode.meta.is_parallel:
            return await self._fire_engine_node(node_id, rnode)
        return await self._fire_ray_node(node_id, rnode)

    # ------------------------------------------------------------------
    # CallFlow
    # ------------------------------------------------------------------

    async def _fire_callflow_node(self, node_id: str, rnode: ResolvedNode) -> list[str]:
        started_at = time.time()
        entry_id = rnode.node_def.subflow_entry
        exit_id = rnode.node_def.subflow_exit

        if rnode.node_def.subflow_vars:
            sub_state = self._built.nodes[entry_id].state_path
            for var_name, default in rnode.node_def.subflow_vars:
                ray.get(self._state.set_variable.remote(
                    _var_key(sub_state, var_name), default
                ))

        await self._run_loop(entry_id)

        result: dict[str, Any] = {}
        if exit_id is not None:
            exit_rnode = self._built.nodes[exit_id]
            for pin_name in exit_rnode.resolved_inputs:
                result[pin_name] = ray.get(self._resolve_pin(exit_rnode, pin_name))

        duration_ms = (time.time() - started_at) * 1000
        self._write_node_outputs(node_id, {
            "result": result,
            "meta": self._build_meta(node_id, rnode, started_at, duration_ms),
        })
        return rnode.exec_targets.get("exec_out", [])

    # ------------------------------------------------------------------
    # @engine_node y @parallel_node
    # ------------------------------------------------------------------

    async def _fire_engine_node(self, node_id: str, rnode: ResolvedNode) -> list[str]:
        name = rnode.meta.name
        resolved = self._resolve_inputs(rnode)
        inputs = {k: ray.get(v) for k, v in resolved.items()}

        if name == "FlowOutput":
            if rnode.node_def.subflow_of is None:
                self._output_refs.update({k: ray.get(v) for k, v in resolved.items()})
            return []

        if name in ("OnStart", "OnEvent") and rnode.node_def.subflow_of is not None:
            self._write_node_outputs(node_id, {k: ray.get(v) for k, v in resolved.items()})
            targets = rnode.exec_targets.get("exec_out", [])
            if len(targets) > 1:
                await asyncio.gather(*[self._run_loop(t, node_id) for t in targets])
            elif targets:
                await self._run_loop(targets[0], node_id)
            return []

        graph_id = self._get_graph_id()
        ctx = ExecContext(
            node_id, graph_id, rnode.state_path,
            _output_writer=lambda nid, pin, val: self._write_node_outputs(nid, {pin: val}),
        )

        started_at = time.time()
        self._emit_node_start(node_id, rnode)
        self._write_node_outputs(node_id, {"meta": self._build_meta(node_id, rnode, started_at, 0.0)})

        run_fn = getattr(rnode.meta.py_class, "run", None)
        if run_fn is not None:
            instance = rnode.meta.py_class()
            result = instance.run(ctx, **inputs)
            if inspect.isawaitable(result):
                result = await result
            if result:
                raise RuntimeError(
                    f"Nodo '{name}' (id={node_id}) devolvió data por return "
                    f"({list(result)}). Usa ctx.set_output(pin, valor)."
                )

        duration_ms = (time.time() - started_at) * 1000
        self._write_node_outputs(node_id, {"meta": self._build_meta(node_id, rnode, started_at, duration_ms)})
        self._emit_node_done(node_id, rnode, duration_ms)
        return []

    # ------------------------------------------------------------------
    # @ray_node
    # ------------------------------------------------------------------

    async def _fire_ray_node(self, node_id: str, rnode: ResolvedNode) -> list[str]:
        actor = self._actors[node_id]
        resolved = self._resolve_inputs(rnode)

        graph_id = self._get_graph_id()
        ctx = ExecContext(node_id, graph_id, rnode.state_path)

        started_at = time.time()
        self._emit_node_start(node_id, rnode)
        self._write_node_outputs(node_id, {"meta": self._build_meta(node_id, rnode, started_at, 0.0)})

        await actor.run_with_ctx.remote(ctx, **resolved)

        duration_ms = (time.time() - started_at) * 1000
        self._write_node_outputs(node_id, {"meta": self._build_meta(node_id, rnode, started_at, duration_ms)})
        self._emit_node_done(node_id, rnode, duration_ms)
        return []

    # ------------------------------------------------------------------
    # Emisión de eventos a la RunQueue
    # ------------------------------------------------------------------

    def _emit_node_start(self, node_id: str, rnode: ResolvedNode) -> None:
        if self._run_queue is None:
            return
        ray.get(self._run_queue.push.remote({
            "event": "node_start",
            "node_id": node_id,
            "node_type": rnode.meta.name,
            "ts": time.time(),
        }))

    def _emit_node_done(self, node_id: str, rnode: ResolvedNode, duration_ms: float) -> None:
        if self._run_queue is None:
            return
        ray.get(self._run_queue.push.remote({
            "event": "node_done",
            "node_id": node_id,
            "node_type": rnode.meta.name,
            "duration_ms": round(duration_ms, 3),
            "ts": time.time(),
        }))

    # ------------------------------------------------------------------
    # Resolución de data inputs
    # ------------------------------------------------------------------

    def _resolve_inputs(self, rnode: ResolvedNode) -> dict[str, Any]:
        return {
            pin_name: self._resolve_pin(rnode, pin_name)
            for pin_name in rnode.resolved_inputs
        }

    def _resolve_pin(self, rnode: ResolvedNode, pin_name: str) -> Any:
        res_pin = rnode.resolved_inputs[pin_name]

        if not res_pin.is_ref:
            return ray.put(res_pin.literal)

        src_id = res_pin.source_node
        src_pin = res_pin.source_pin
        src_rnode = self._built.nodes.get(src_id)

        ref = ray.get(self._state.get_node_output.remote(src_id, src_pin))
        if ref is not None:
            if isinstance(ref, ray.ObjectRef):
                ref = ray.get(ref)
            return ray.put(ref)

        if src_rnode and not src_rnode.meta.is_exec_node:
            value = self._eval_pure_engine_node(src_rnode, src_pin)
            return ray.put(value)

        consumer_pin = next(
            (p for p in rnode.meta.inputs if p.name == pin_name), None
        )
        default = consumer_pin.default if consumer_pin and consumer_pin.has_default else None
        return ray.put(default)

    def _eval_pure_engine_node(self, rnode: ResolvedNode, src_pin: str) -> Any:
        resolved = self._resolve_inputs(rnode)
        inputs = {k: ray.get(v) for k, v in resolved.items()}
        graph_id = self._get_graph_id()
        ctx = ExecContext(rnode.node_def.id, graph_id, rnode.state_path)
        run_fn = getattr(rnode.meta.py_class, "run", None)
        if run_fn is None:
            return None
        outputs = rnode.meta.py_class().run(ctx, **inputs) or {}
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

    def _write_node_outputs(self, node_id: str, outputs: dict[str, Any]) -> None:
        ray.get(self._state.set_node_outputs.remote(node_id, outputs))


# ---------------------------------------------------------------------------
# LoadedFlow — ciclo de vida de un flow cargado en Ray
# ---------------------------------------------------------------------------

class LoadedFlow:
    """Flow con actores Ray vivos y GraphState persistente.

    Se crea con LoadedFlow.load(built) y se destruye con .unload().
    Entre requests, el GraphState mantiene el estado de variables.
    """

    def __init__(self, graph_id: str, engine: Any, actors: dict[str, Any], flow_def=None):
        self.graph_id = graph_id
        self._engine = engine
        self._actors = actors
        self.flow_def = flow_def  # FlowDef original para inspección de interfaz

    @classmethod
    def load(cls, built: BuiltFlow) -> "LoadedFlow":
        graph_id = built.flow_def.name

        # Destruir engine previo si existía (recarga)
        try:
            old = ray.get_actor(f"engine_{graph_id}", namespace="rayflow")
            ray.kill(old)
        except Exception:
            pass
        try:
            old_gs = ray.get_actor(f"gs_{graph_id}", namespace="rayflow")
            ray.kill(old_gs)
        except Exception:
            pass

        # Spawn actores @ray_node
        actors: dict[str, Any] = {}
        for node_id, rnode in built.nodes.items():
            if rnode.meta.is_engine_node or rnode.meta.is_parallel:
                continue
            if rnode.meta.is_exec_node and rnode.meta.ray_handle is not None:
                # Destruir actor previo si existe
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

        engine = FlowEngine.options(
            name=f"engine_{graph_id}",
            namespace="rayflow",
            lifetime="detached",
        ).remote(built, actors)

        return cls(graph_id, engine, actors, flow_def=built.flow_def)

    def execute(self, flow_inputs: dict[str, Any], queue: Any) -> Any:
        """Lanza execute() en el engine y devuelve el ObjectRef (no bloquea)."""
        return self._engine.execute.remote(flow_inputs, queue)

    def unload(self) -> None:
        """Destruye todos los actores del flow."""
        for actor in self._actors.values():
            try:
                ray.kill(actor)
            except Exception:
                pass
        try:
            ray.kill(self._engine)
        except Exception:
            pass
        try:
            gs = ray.get_actor(f"gs_{self.graph_id}", namespace="rayflow")
            ray.kill(gs)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Registro global de flows cargados (en el proceso driver)
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
