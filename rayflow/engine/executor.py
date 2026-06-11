from __future__ import annotations

from collections import deque
from typing import Any
import time
import uuid

import ray

from rayflow.build.validator import BuiltFlow, ResolvedNode
from rayflow.nodes.decorators import ExecContext
from rayflow.state.actor import GraphState


class FlowExecutor:
    """Motor de ejecución de un flow ya construido (BuiltFlow).

    Dos tipos de nodo:
    - @ray_node  → actor/task Ray. run(ctx, **inputs) corre en proceso remoto.
                   ctx.fire() acumula pins; el engine los encola al terminar.
    - @engine_node → ejecutado localmente. ctx.fire() es bloqueante: el
                   subgrafo conectado se ejecuta antes de que run() continúe.
    """

    def __init__(self, built: BuiltFlow, flow_inputs: dict[str, Any] | None = None):
        self._built = built
        self._flow_inputs = flow_inputs or {}
        self._actors: dict[str, Any] = {}
        self._state: GraphState | None = None
        self._graph_id: str | None = None
        # Refs de salida del flow, poblados por FlowOutput
        self._output_refs: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def execute(self) -> dict[str, Any]:
        flow = self._built.flow_def

        self._graph_id = str(uuid.uuid4())
        var_defaults = {v.name: v.default for v in flow.variables}
        self._state = GraphState.options(
            name=f"gs_{self._graph_id}", lifetime="detached"
        ).remote(var_defaults)
        self._spawn_actors()

        input_refs = {name: ray.put(value) for name, value in self._flow_inputs.items()}
        self._write_node_outputs(self._built.entry_node_id, input_refs)

        self._run_loop(self._built.entry_node_id)

        outputs = {name: ray.get(ref) for name, ref in self._output_refs.items()}
        self._teardown_actors()
        ray.kill(self._state)
        return outputs

    # ------------------------------------------------------------------
    # Ciclo de control
    # ------------------------------------------------------------------

    def _run_loop(self, entry_id: str) -> None:
        """BFS desde entry_id. Cada nodo disparado devuelve los siguientes a encolar."""
        queue: deque[str] = deque([entry_id])
        while queue:
            node_id = queue.popleft()
            next_ids = self._fire(node_id)
            queue.extend(next_ids)

    def _fire(self, node_id: str) -> list[str]:
        """Dispara un nodo y devuelve los node_ids a encolar a continuación."""
        rnode = self._built.nodes[node_id]
        if rnode.meta.is_parallel:
            return self._fire_parallel_node(node_id, rnode)
        if rnode.meta.is_engine_node:
            return self._fire_engine_node(node_id, rnode)
        return self._fire_ray_node(node_id, rnode)

    # ------------------------------------------------------------------
    # Nodo Parallel — fork/join mediante tasks Ray
    # ------------------------------------------------------------------

    def _fire_parallel_node(self, node_id: str, rnode: ResolvedNode) -> list[str]:
        """Lanza cada branch_N como task Ray independiente y espera fork/join."""
        branch_ids = []
        for pin in rnode.meta.exec_outputs:
            if pin != "joined":
                branch_ids.extend(rnode.exec_targets.get(pin, []))

        started_at = time.time()
        if branch_ids:
            refs = [
                _run_subgraph_task.remote(self._built, self._graph_id, eid)
                for eid in branch_ids
            ]
            ray.get(refs)
        duration_ms = (time.time() - started_at) * 1000

        self._write_node_outputs(node_id, {
            "meta": ray.put(self._build_meta(node_id, rnode, started_at, duration_ms))
        })

        return rnode.exec_targets.get("joined", [])

    # ------------------------------------------------------------------
    # @engine_node — ejecutado localmente, ctx.fire() bloqueante
    # ------------------------------------------------------------------

    def _fire_engine_node(self, node_id: str, rnode: ResolvedNode) -> list[str]:
        name = rnode.meta.name
        resolved = self._resolve_inputs(rnode)
        inputs = {k: ray.get(v) for k, v in resolved.items()}

        # FlowOutput: recolecta los outputs del flow y termina
        if name == "FlowOutput":
            self._output_refs.update(resolved)
            return []

        def _fire_fn(pin_name: str) -> None:
            for target in rnode.exec_targets.get(pin_name, []):
                self._run_loop(target)

        def _set_output_fn(pin_name: str, value: Any) -> None:
            self._write_node_outputs(node_id, {pin_name: ray.put(value)})

        def _get_variable_fn(var_name: str) -> Any:
            value = ray.get(self._state.get_variable.remote(var_name))
            if isinstance(value, ray.ObjectRef):
                value = ray.get(value)
            return value

        def _set_variable_fn(var_name: str, value: Any) -> None:
            ray.get(self._state.set_variable.remote(var_name, value))

        def _emit_event_fn(event_name: str, payload: Any) -> None:
            try:
                from rayflow.events.bus import get_event_bus
                bus = get_event_bus()
                bus.emit.remote(event_name, ray.put(payload))
            except Exception:
                pass

        ctx = ExecContext(_fire_fn, _set_output_fn, _get_variable_fn, _set_variable_fn, _emit_event_fn)

        started_at = time.time()
        run_fn = getattr(rnode.meta.py_class, "run", None)
        if run_fn is not None:
            instance = rnode.meta.py_class()
            outputs = instance.run(ctx, **inputs) or {}
            if outputs:
                self._write_node_outputs(node_id, {
                    k: ray.put(v) for k, v in outputs.items()
                })
        duration_ms = (time.time() - started_at) * 1000

        self._write_node_outputs(node_id, {
            "meta": ray.put(self._build_meta(node_id, rnode, started_at, duration_ms))
        })

        return []

    # ------------------------------------------------------------------
    # @ray_node — actor Ray, ctx.fire() acumula pins
    # ------------------------------------------------------------------

    def _spawn_actors(self) -> None:
        for node_id, rnode in self._built.nodes.items():
            if rnode.meta.is_engine_node:
                continue
            if rnode.meta.is_exec_node and rnode.meta.ray_handle is not None:
                self._actors[node_id] = rnode.meta.ray_handle.remote()

    def _teardown_actors(self) -> None:
        for actor in self._actors.values():
            ray.kill(actor)
        self._actors.clear()

    def _fire_ray_node(self, node_id: str, rnode: ResolvedNode) -> list[str]:
        actor = self._actors[node_id]
        resolved = self._resolve_inputs(rnode)

        ctx = _SerializableExecContext(self._graph_id)
        started_at = time.time()
        result_ref = actor.run_with_ctx.remote(ctx, **resolved)
        fired, outputs = ray.get(result_ref)
        duration_ms = (time.time() - started_at) * 1000

        out_refs = {pin: ray.put(value) for pin, value in outputs.items()}
        out_refs["meta"] = ray.put(self._build_meta(node_id, rnode, started_at, duration_ms))
        self._write_node_outputs(node_id, out_refs)

        result = []
        for pin in fired:
            result.extend(rnode.exec_targets.get(pin, []))
        return result

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

        # 1) Output vigente en el state (nodos exec o engine_node con set_output)
        ref = ray.get(self._state.get_node_output.remote(src_id, src_pin))
        if ref is not None:
            if isinstance(ref, ray.ObjectRef):
                ref = ray.get(ref)
            return ray.put(ref)

        # 2a) @engine_node pure (sin exec pins) → evaluar localmente bajo demanda
        if src_rnode and src_rnode.meta.is_engine_node and not src_rnode.meta.is_exec_node:
            value = self._eval_pure_engine_node(src_rnode, src_pin)
            return ray.put(value)

        # 2b) @ray_node pure (sin exec pins) → task Ray bajo demanda
        if src_rnode and not src_rnode.meta.is_exec_node and not src_rnode.meta.is_engine_node:
            data_inputs = self._resolve_inputs(src_rnode)
            result_ref = src_rnode.meta.ray_handle.remote(**data_inputs)
            result = ray.get(result_ref)
            value = result.get(src_pin) if isinstance(result, dict) else result
            return ray.put(value)

        # 4) Fallback: default del pin consumidor
        consumer_pin = next(
            (p for p in rnode.meta.inputs if p.name == pin_name), None
        )
        default = consumer_pin.default if consumer_pin and consumer_pin.has_default else None
        return ray.put(default)

    def _eval_pure_engine_node(self, rnode: ResolvedNode, src_pin: str) -> Any:
        """Evalúa un @engine_node sin exec pins bajo demanda (pure node / lazy)."""
        resolved = self._resolve_inputs(rnode)
        inputs = {k: ray.get(v) for k, v in resolved.items()}

        def _noop_fire(pin_name: str) -> None:
            pass

        def _noop_set_output(pin_name: str, value: Any) -> None:
            pass

        def _get_variable_fn(var_name: str) -> Any:
            value = ray.get(self._state.get_variable.remote(var_name))
            if isinstance(value, ray.ObjectRef):
                value = ray.get(value)
            return value

        def _set_variable_fn(var_name: str, value: Any) -> None:
            ray.get(self._state.set_variable.remote(var_name, value))

        ctx = ExecContext(_noop_fire, _noop_set_output, _get_variable_fn, _set_variable_fn)
        run_fn = getattr(rnode.meta.py_class, "run", None)
        if run_fn is None:
            return None
        outputs = rnode.meta.py_class().run(ctx, **inputs) or {}
        return outputs.get(src_pin)

    def _literal_input(self, rnode: ResolvedNode, pin_name: str, default: Any) -> Any:
        res = rnode.resolved_inputs.get(pin_name)
        if res is not None and not res.is_ref:
            return res.literal
        return default

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _build_meta(self, node_id: str, rnode: ResolvedNode, started_at: float, duration_ms: float) -> dict:
        return {
            "id": node_id,
            "type": rnode.meta.name,
            "flow": self._built.flow_def.name,
            "started_at": started_at,
            "duration_ms": round(duration_ms, 3),
        }

    def _write_node_outputs(self, node_id: str, ref_dict: dict[str, Any]) -> None:
        materialized = {pin: ray.get(ref) for pin, ref in ref_dict.items()}
        ray.get(self._state.set_node_outputs.remote(node_id, materialized))


# ---------------------------------------------------------------------------
# Task Ray para ramas paralelas — cada rama tiene su propio FlowExecutor
# ---------------------------------------------------------------------------

@ray.remote
def _run_subgraph_task(built: BuiltFlow, graph_id: str, entry_id: str) -> None:
    """Ejecuta un subgrafo desde entry_id en un proceso Ray aislado.

    Recupera el GraphState del grafo padre por nombre — único punto de
    sincronización entre ramas paralelas. Los @engine_node de cada rama no
    interfieren entre sí porque cada rama tiene su propio FlowExecutor.
    """
    executor = FlowExecutor(built)
    executor._graph_id = graph_id
    executor._state = ray.get_actor(f"gs_{graph_id}")
    executor._spawn_actors()
    executor._run_loop(entry_id)
    executor._teardown_actors()


# ---------------------------------------------------------------------------
# ExecContext serializable para @ray_node (vive en el proceso del actor)
# ---------------------------------------------------------------------------

class _SerializableExecContext:
    """ExecContext serializable que viaja al proceso del actor @ray_node.

    Acumula fired_pins y permite acceder al GraphState del grafo por nombre,
    lo que posibilita que cualquier actor Ray acceda a variables compartidas
    sin necesidad de recibir el handle directamente.
    """

    def __init__(self, graph_id: str):
        self.fired: list[str] = []
        self._graph_id = graph_id

    def fire(self, pin_name: str) -> None:
        self.fired.append(pin_name)

    def set_output(self, pin_name: str, value: Any) -> None:
        pass

    def get_variable(self, name: str) -> Any:
        state = ray.get_actor(f"gs_{self._graph_id}")
        value = ray.get(state.get_variable.remote(name))
        if isinstance(value, ray.ObjectRef):
            value = ray.get(value)
        return value

    def set_variable(self, name: str, value: Any) -> None:
        state = ray.get_actor(f"gs_{self._graph_id}")
        ray.get(state.set_variable.remote(name, value))

    def emit_event(self, event_name: str, payload: Any = None) -> None:
        try:
            from rayflow.events.bus import get_event_bus
            bus = get_event_bus()
            bus.emit.remote(event_name, ray.put(payload))
        except Exception:
            pass
