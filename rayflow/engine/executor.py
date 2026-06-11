from __future__ import annotations

from collections import deque
from typing import Any
import time
import uuid

import ray

from rayflow.build.validator import BuiltFlow, ResolvedNode
from rayflow.nodes.decorators import ExecContext
from rayflow.state.actor import GraphState


class FlowEngine:
    """Motor de ejecución de un flow ya construido (BuiltFlow).

    Los actores @ray_node se crean UNA VEZ al inicio con nombre único
    "{node_id}_{graph_id}" y son accesibles por cualquier parte del cluster
    que tenga el graph_id. Las ramas del Parallel y los subgrafos del mismo
    flow los reutilizan — no los duplican.
    """

    def __init__(self, built: BuiltFlow, flow_inputs: dict[str, Any] | None = None,
                 actors: dict[str, Any] | None = None):
        self._built = built
        self._flow_inputs = flow_inputs or {}
        self._state: GraphState | None = None
        self._graph_id: str | None = None
        self._output_refs: dict[str, Any] = {}
        # Handles de actores @ray_node — pasados desde el driver donde la clase es conocida
        self._actors: dict[str, Any] = actors or {}

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def execute(self) -> dict[str, Any]:
        """Crea GraphState y actores con nombre único, ejecuta el flow."""
        self._graph_id = str(uuid.uuid4())
        var_defaults = {v.name: v.default for v in self._built.flow_def.variables}
        self._state = GraphState.options(
            name=f"gs_{self._graph_id}", namespace="rayflow", lifetime="detached"
        ).remote(var_defaults)

        self._spawn_actors()
        self._run_and_collect()
        self._teardown_actors()
        ray.kill(self._state)
        return self._output_refs

    def execute_with_state(self, graph_id: str) -> dict[str, Any]:
        """Ejecuta compartiendo GraphState y actores de un engine padre.

        Usado por CallFlow modo compartido. El subflow tiene sus propios
        actores (nombrados con su propio graph_id) pero comparte el GraphState.
        NO destruye el GraphState al terminar.
        """
        self._graph_id = graph_id
        self._state = ray.get_actor(f"gs_{graph_id}", namespace="rayflow")

        self._spawn_actors()
        self._run_and_collect()
        self._teardown_actors()
        return self._output_refs

    # ------------------------------------------------------------------
    # Gestión de actores @ray_node — creados una vez por flow
    # ------------------------------------------------------------------

    def _spawn_actors(self) -> None:
        """Instancia actores @ray_node con nombre único "{node_id}_{graph_id}".

        Los handles se guardan en self._actors y se pasan a las tasks de ramas
        paralelas — así las ramas no necesitan redescubrir los actores por nombre
        desde un proceso donde la clase Python puede no estar importada.
        """
        for node_id, rnode in self._built.nodes.items():
            if rnode.meta.is_engine_node or rnode.meta.is_parallel:
                continue
            if rnode.meta.is_exec_node and rnode.meta.ray_handle is not None:
                actor_name = f"{node_id}_{self._graph_id}"
                actor = rnode.meta.ray_handle.options(
                    name=actor_name, namespace="rayflow", lifetime="detached"
                ).remote()
                self._actors[node_id] = actor

    def _teardown_actors(self) -> None:
        """Destruye todos los actores @ray_node de este flow."""
        for actor in self._actors.values():
            try:
                ray.kill(actor)
            except Exception:
                pass
        self._actors.clear()

    def _get_actor(self, node_id: str) -> Any:
        """Devuelve el handle del actor — siempre disponible en self._actors."""
        return self._actors[node_id]

    # ------------------------------------------------------------------
    # Ciclo interno
    # ------------------------------------------------------------------

    def _run_and_collect(self) -> None:
        input_refs = {name: ray.put(value) for name, value in self._flow_inputs.items()}
        self._write_node_outputs(self._built.entry_node_id, input_refs)
        self._run_loop(self._built.entry_node_id)
        self._output_refs = {
            name: ray.get(ref) for name, ref in self._output_refs.items()
        }

    def _run_loop(self, entry_id: str) -> None:
        queue: deque[str] = deque([entry_id])
        while queue:
            node_id = queue.popleft()
            next_ids = self._fire(node_id)
            queue.extend(next_ids)

    def _fire(self, node_id: str) -> list[str]:
        rnode = self._built.nodes[node_id]
        if rnode.node_def.subflow_entry is not None:
            return self._fire_callflow_node(node_id, rnode)
        if rnode.meta.is_parallel:
            return self._fire_parallel_node(node_id, rnode)
        if rnode.meta.is_engine_node:
            return self._fire_engine_node(node_id, rnode)
        return self._fire_ray_node(node_id, rnode)

    # ------------------------------------------------------------------
    # CallFlow — subgrafo inline orquestado por el engine
    # ------------------------------------------------------------------

    def _fire_callflow_node(self, node_id: str, rnode: ResolvedNode) -> list[str]:
        """Orquesta un CallFlow shell: corre el subgrafo inline y lee 'result'.

        El subflow ya está aplanado inline (flatten). El shell dispara su entry
        (bloqueante vía _run_loop), reúne los outputs del FlowOutput de retorno
        como dict 'result', y continúa hacia su exec_out (continuación del padre).
        """
        started_at = time.time()

        entry_id = rnode.node_def.subflow_entry
        exit_id = rnode.node_def.subflow_exit

        # Corre el subgrafo inline, bloqueante.
        self._run_loop(entry_id)

        # Reúne los outputs del subflow desde los inputs resueltos del FlowOutput
        # de retorno — ese es el dict 'result' que ve el padre.
        result: dict[str, Any] = {}
        if exit_id is not None:
            exit_rnode = self._built.nodes[exit_id]
            for pin_name in exit_rnode.resolved_inputs:
                result[pin_name] = ray.get(self._resolve_pin(exit_rnode, pin_name))

        duration_ms = (time.time() - started_at) * 1000
        self._write_node_outputs(node_id, {
            "result": ray.put(result),
            "meta": ray.put(self._build_meta(node_id, rnode, started_at, duration_ms)),
        })
        return rnode.exec_targets.get("exec_out", [])

    # ------------------------------------------------------------------
    # Nodo Parallel — fork/join con tasks Ray
    # ------------------------------------------------------------------

    def _fire_parallel_node(self, node_id: str, rnode: ResolvedNode) -> list[str]:
        branch_ids = []
        for pin in rnode.meta.exec_outputs:
            if pin != "joined":
                branch_ids.extend(rnode.exec_targets.get(pin, []))

        started_at = time.time()
        if branch_ids:
            # Pasar handles directamente — las tasks reciben actores ya creados
            refs = [
                _run_subgraph_task.remote(self._built, self._graph_id, self._state, self._actors, eid)
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

        if name == "FlowOutput":
            # Un FlowOutput de subgrafo spliced (subflow_of) NO cierra el flow:
            # sus valores los recoge el CallFlow shell como 'result'. Solo el
            # FlowOutput del flow raíz alimenta _output_refs.
            if rnode.node_def.subflow_of is None:
                self._output_refs.update(resolved)
            return []

        if name in ("FlowInput", "OnEvent") and rnode.node_def.subflow_of is not None:
            # FlowInput de subgrafo spliced: sus data outputs (a, b, …) son los
            # inputs que el CallFlow le pasó. Copia input→output del mismo nombre
            # y dispara exec_out hacia el subgrafo. No se invoca run() — el nodo
            # builtin no acepta estos kwargs dinámicos.
            self._write_node_outputs(node_id, dict(resolved))
            for target in rnode.exec_targets.get("exec_out", []):
                self._run_loop(target)
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

        ctx = ExecContext(
            _fire_fn, _set_output_fn,
            _get_variable_fn, _set_variable_fn, _emit_event_fn,
            graph_id=self._graph_id,
        )

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
    # @ray_node — actor Ray, localizado por nombre en el cluster
    # ------------------------------------------------------------------

    def _fire_ray_node(self, node_id: str, rnode: ResolvedNode) -> list[str]:
        actor = self._get_actor(node_id)
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

        # 1) Output vigente en el state
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

        # 3) Fallback: default del pin consumidor
        consumer_pin = next(
            (p for p in rnode.meta.inputs if p.name == pin_name), None
        )
        default = consumer_pin.default if consumer_pin and consumer_pin.has_default else None
        return ray.put(default)

    def _eval_pure_engine_node(self, rnode: ResolvedNode, src_pin: str) -> Any:
        """Evalúa un @engine_node sin exec pins bajo demanda (pure node / lazy)."""
        resolved = self._resolve_inputs(rnode)
        inputs = {k: ray.get(v) for k, v in resolved.items()}

        def _get_variable_fn(var_name: str) -> Any:
            value = ray.get(self._state.get_variable.remote(var_name))
            if isinstance(value, ray.ObjectRef):
                value = ray.get(value)
            return value

        ctx = ExecContext(
            lambda pin: None, lambda pin, val: None,
            _get_variable_fn, lambda n, v: None,
            graph_id=self._graph_id,
        )
        run_fn = getattr(rnode.meta.py_class, "run", None)
        if run_fn is None:
            return None
        outputs = rnode.meta.py_class().run(ctx, **inputs) or {}
        return outputs.get(src_pin)

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
# Wrapper síncrono — compatibilidad con api.py y tests existentes
# ---------------------------------------------------------------------------

class FlowExecutor:
    """Wrapper síncrono sobre FlowEngine para compatibilidad."""

    def __init__(self, built: BuiltFlow, flow_inputs: dict[str, Any] | None = None):
        self._built = built
        self._flow_inputs = flow_inputs or {}

    def execute(self) -> dict[str, Any]:
        return FlowEngine(self._built, self._flow_inputs).execute()


# ---------------------------------------------------------------------------
# Task Ray para ramas paralelas del mismo flow
# ---------------------------------------------------------------------------

@ray.remote
def _run_subgraph_task(
    built: BuiltFlow,
    graph_id: str,
    state: Any,
    actors: dict[str, Any],
    entry_id: str,
) -> None:
    """Ejecuta un subgrafo (rama de Parallel) en un worker Ray.

    Recibe el GraphState y los handles de actores del flow padre directamente —
    los handles son serializables por Ray y funcionan desde cualquier proceso
    del cluster sin reimportar las clases Python.
    """
    executor = _SubgraphExecutor(built, graph_id, state, actors)
    executor.run(entry_id)


class _SubgraphExecutor:
    """Ejecutor liviano para ramas de Parallel — objeto Python puro, sin actor Ray.

    Reutiliza el GraphState y los actores @ray_node del flow padre.
    Se instancia dentro del worker de _run_subgraph_task.
    """

    def __init__(self, built: BuiltFlow, graph_id: str, state: Any, actors: dict[str, Any]):
        self._built = built
        self._graph_id = graph_id
        self._state = state
        self._actors = actors
        self._output_refs: dict[str, Any] = {}

    def run(self, entry_id: str) -> None:
        queue: deque[str] = deque([entry_id])
        while queue:
            node_id = queue.popleft()
            next_ids = self._fire(node_id)
            queue.extend(next_ids)

    def _fire(self, node_id: str) -> list[str]:
        rnode = self._built.nodes[node_id]
        if rnode.meta.is_parallel:
            return self._fire_parallel_node(node_id, rnode)
        if rnode.meta.is_engine_node:
            return self._fire_engine_node(node_id, rnode)
        return self._fire_ray_node(node_id, rnode)

    def _fire_parallel_node(self, node_id: str, rnode: ResolvedNode) -> list[str]:
        branch_ids = []
        for pin in rnode.meta.exec_outputs:
            if pin != "joined":
                branch_ids.extend(rnode.exec_targets.get(pin, []))

        started_at = time.time()
        if branch_ids:
            refs = [
                _run_subgraph_task.remote(self._built, self._graph_id, self._state, self._actors, eid)
                for eid in branch_ids
            ]
            ray.get(refs)
        duration_ms = (time.time() - started_at) * 1000

        self._write_node_outputs(node_id, {
            "meta": ray.put(self._build_meta(node_id, rnode, started_at, duration_ms))
        })
        return rnode.exec_targets.get("joined", [])

    def _fire_engine_node(self, node_id: str, rnode: ResolvedNode) -> list[str]:
        name = rnode.meta.name
        resolved = self._resolve_inputs(rnode)
        inputs = {k: ray.get(v) for k, v in resolved.items()}

        if name == "FlowOutput":
            self._output_refs.update(resolved)
            return []

        def _fire_fn(pin_name: str) -> None:
            for target in rnode.exec_targets.get(pin_name, []):
                self.run(target)

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

        ctx = ExecContext(
            _fire_fn, _set_output_fn,
            _get_variable_fn, _set_variable_fn, _emit_event_fn,
            graph_id=self._graph_id,
        )

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

        if src_rnode and src_rnode.meta.is_engine_node and not src_rnode.meta.is_exec_node:
            value = self._eval_pure_engine_node(src_rnode, src_pin)
            return ray.put(value)

        if src_rnode and not src_rnode.meta.is_exec_node and not src_rnode.meta.is_engine_node:
            data_inputs = self._resolve_inputs(src_rnode)
            result_ref = src_rnode.meta.ray_handle.remote(**data_inputs)
            result = ray.get(result_ref)
            value = result.get(src_pin) if isinstance(result, dict) else result
            return ray.put(value)

        consumer_pin = next(
            (p for p in rnode.meta.inputs if p.name == pin_name), None
        )
        default = consumer_pin.default if consumer_pin and consumer_pin.has_default else None
        return ray.put(default)

    def _eval_pure_engine_node(self, rnode: ResolvedNode, src_pin: str) -> Any:
        resolved = self._resolve_inputs(rnode)
        inputs = {k: ray.get(v) for k, v in resolved.items()}

        def _get_variable_fn(var_name: str) -> Any:
            value = ray.get(self._state.get_variable.remote(var_name))
            if isinstance(value, ray.ObjectRef):
                value = ray.get(value)
            return value

        ctx = ExecContext(
            lambda pin: None, lambda pin, val: None,
            _get_variable_fn, lambda n, v: None,
            graph_id=self._graph_id,
        )
        run_fn = getattr(rnode.meta.py_class, "run", None)
        if run_fn is None:
            return None
        outputs = rnode.meta.py_class().run(ctx, **inputs) or {}
        return outputs.get(src_pin)

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
# ExecContext serializable para @ray_node (vive en el proceso del actor)
# ---------------------------------------------------------------------------

class _SerializableExecContext:
    """ExecContext serializable que viaja al proceso del actor @ray_node."""

    def __init__(self, graph_id: str):
        self.fired: list[str] = []
        self._graph_id = graph_id

    def fire(self, pin_name: str) -> None:
        self.fired.append(pin_name)

    def set_output(self, pin_name: str, value: Any) -> None:
        pass

    def get_variable(self, name: str) -> Any:
        state = ray.get_actor(f"gs_{self._graph_id}", namespace="rayflow")
        value = ray.get(state.get_variable.remote(name))
        if isinstance(value, ray.ObjectRef):
            value = ray.get(value)
        return value

    def set_variable(self, name: str, value: Any) -> None:
        state = ray.get_actor(f"gs_{self._graph_id}", namespace="rayflow")
        ray.get(state.set_variable.remote(name, value))

    def emit_event(self, event_name: str, payload: Any = None) -> None:
        try:
            from rayflow.events.bus import get_event_bus
            bus = get_event_bus()
            bus.emit.remote(event_name, ray.put(payload))
        except Exception:
            pass
