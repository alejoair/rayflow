from __future__ import annotations

from collections import deque
from typing import Any
import time

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
        # Refs de salida del flow, poblados por FlowOutput
        self._output_refs: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def execute(self) -> dict[str, Any]:
        flow = self._built.flow_def

        var_defaults = {v.name: v.default for v in flow.variables}
        self._state = GraphState.remote(var_defaults)
        self._spawn_actors()

        input_refs = {name: ray.put(value) for name, value in self._flow_inputs.items()}
        self._write_node_outputs(self._built.entry_node_id, input_refs)

        self._run_loop(self._built.entry_node_id)

        outputs = {name: ray.get(ref) for name, ref in self._output_refs.items()}
        self._teardown_actors()
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
                _run_subgraph_task.remote(self._built, self._state, eid)
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

        # FlowOutput: recolecta los outputs del flow
        if name == "FlowOutput":
            self._output_refs.update(resolved)
            return []

        # Set: escribe en el state actor
        if name == "Set":
            var_name = inputs.get("variable_name", "")
            value = inputs.get("value")
            ray.get(self._state.set_variable.remote(var_name, value))

        # EmitEvent: emite al bus
        if name == "EmitEvent":
            event_name = inputs.get("event_name", "")
            payload = inputs.get("payload")
            self._emit_event(event_name, ray.put(payload))

        # Crear ctx bloqueante: fire() ejecuta el subgrafo inmediatamente
        next_ids: list[str] = []

        def _fire_fn(pin_name: str) -> None:
            for target in rnode.exec_targets.get(pin_name, []):
                self._run_loop(target)
                next_ids.append(target)

        def _set_output_fn(pin_name: str, value: Any) -> None:
            self._write_node_outputs(node_id, {pin_name: ray.put(value)})

        ctx = ExecContext(_fire_fn, _set_output_fn)

        started_at = time.time()
        run_fn = getattr(rnode.meta.py_class, "run", None)
        if run_fn is not None:
            instance = rnode.meta.py_class()
            instance.run(ctx, **inputs)
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

        ctx = _SerializableExecContext()
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

        # 2) Get: lee variable del state
        if src_rnode and src_rnode.meta.name == "Get":
            var_name = self._literal_input(src_rnode, "variable_name", default="")
            value = ray.get(self._state.get_variable.remote(var_name))
            if isinstance(value, ray.ObjectRef):
                value = ray.get(value)
            return ray.put(value)

        # 3) Nodo de datos puro (@ray_node sin exec pins) → task de Ray
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

    def _emit_event(self, event_name: str, payload_ref: Any) -> None:
        try:
            from rayflow.events.bus import get_event_bus
            bus = get_event_bus()
            bus.emit.remote(event_name, payload_ref)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Task Ray para ramas paralelas — cada rama tiene su propio FlowExecutor
# ---------------------------------------------------------------------------

@ray.remote
def _run_subgraph_task(built: BuiltFlow, state: GraphState, entry_id: str) -> None:
    """Ejecuta un subgrafo desde entry_id en un proceso Ray aislado.

    Comparte el GraphState del executor padre — único punto de sincronización
    entre ramas paralelas. Los @engine_node de cada rama no interfieren entre sí
    porque cada rama tiene su propio FlowExecutor y stack de llamadas.
    """
    executor = FlowExecutor(built)
    executor._state = state
    executor._spawn_actors()
    executor._run_loop(entry_id)
    executor._teardown_actors()


# ---------------------------------------------------------------------------
# ExecContext serializable para @ray_node (vive en el proceso del actor)
# ---------------------------------------------------------------------------

class _SerializableExecContext:
    """ExecContext que acumula fired_pins. Serializable por Ray (pickle)."""

    def __init__(self):
        self.fired: list[str] = []

    def fire(self, pin_name: str) -> None:
        self.fired.append(pin_name)

    def set_output(self, pin_name: str, value: Any) -> None:
        # En @ray_node set_output no aplica (los outputs se devuelven en el dict)
        pass
