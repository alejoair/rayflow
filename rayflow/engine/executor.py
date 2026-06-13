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
    """Motor de ejecución de un flow ya construido (BuiltFlow).

    Actor Ray async con nombre "engine_{graph_id}". Los nodos acceden a él via
    ExecContext usando ray.get_actor() — misma mecánica que GraphState. Esto
    permite que todos los nodos (tanto @engine_node como @ray_node) puedan hacer
    ctx.fire() bloqueante independientemente de dónde corran.

    Los actores @ray_node se crean en el driver (FlowExecutor) y se pasan como
    handles serializables — así se evita la doble serialización de py_class.
    """

    def __init__(
        self,
        built: BuiltFlow,
        flow_inputs: dict[str, Any],
        graph_id: str,
        actors: dict[str, Any],
    ):
        self._built = built
        self._flow_inputs = flow_inputs or {}
        self._graph_id = graph_id
        self._state: GraphState | None = None
        self._output_refs: dict[str, Any] = {}
        self._actors: dict[str, Any] = actors  # handles pre-creados en el driver
        self._exec_arrivals: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # API pública — llamada por nodos via ExecContext
    # ------------------------------------------------------------------

    async def fire(self, source_node_id: str, pin_name: str) -> None:
        """Dispara los targets del exec output indicado y espera a que completen."""
        rnode = self._built.nodes[source_node_id]
        targets = rnode.exec_targets.get(pin_name, [])
        if len(targets) > 1:
            await asyncio.gather(*[self._run_loop(t, source_node_id) for t in targets])
        elif targets:
            await self._run_loop(targets[0], source_node_id)

    async def set_output(self, node_id: str, pin_name: str, value: Any) -> None:
        """Escribe un data output de un nodo en el GraphState."""
        ray.get(self._state.set_node_outputs.remote(node_id, {pin_name: value}))

    async def get_exec_outputs(self, node_id: str, exclude: list[str]) -> list[str]:
        """Devuelve los exec output pins de un nodo excepto los excluidos."""
        rnode = self._built.nodes[node_id]
        return [p for p in rnode.meta.exec_outputs if p not in exclude]

    # ------------------------------------------------------------------
    # Ejecución principal
    # ------------------------------------------------------------------

    async def execute(self) -> dict[str, Any]:
        """Inicializa estado, ejecuta el flow y devuelve los outputs."""
        var_defaults = {v.name: v.default for v in self._built.flow_def.variables}
        self._state = GraphState.options(
            name=f"gs_{self._graph_id}", namespace="rayflow", lifetime="detached"
        ).remote(var_defaults)

        for node_id, rnode in self._built.nodes.items():
            if rnode.exec_join == "and" and len(rnode.exec_sources) > 1:
                self._exec_arrivals[node_id] = set()

        self._write_node_outputs(self._built.entry_node_id, dict(self._flow_inputs))
        await self._run_loop(self._built.entry_node_id)

        ray.kill(self._state)
        return self._output_refs

    def _get_actor(self, node_id: str) -> Any:
        return self._actors[node_id]

    # ------------------------------------------------------------------
    # Ciclo interno
    # ------------------------------------------------------------------

    async def _run_loop(self, entry_id: str, arrived_from: str | None = None) -> None:
        if not self._is_ready(entry_id, arrived_from):
            return
        next_ids = await self._fire(entry_id)
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

    async def _fire(self, node_id: str) -> list[str]:
        rnode = self._built.nodes[node_id]
        if rnode.node_def.subflow_entry is not None:
            return await self._fire_callflow_node(node_id, rnode)
        if rnode.meta.is_engine_node or rnode.meta.is_parallel:
            return await self._fire_engine_node(node_id, rnode)
        return await self._fire_ray_node(node_id, rnode)

    # ------------------------------------------------------------------
    # CallFlow — subgrafo inline orquestado por el engine
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
    # @engine_node y @parallel_node — ejecutado localmente
    # ------------------------------------------------------------------

    async def _fire_engine_node(self, node_id: str, rnode: ResolvedNode) -> list[str]:
        name = rnode.meta.name
        resolved = self._resolve_inputs(rnode)
        inputs = {k: ray.get(v) for k, v in resolved.items()}

        if name == "FlowOutput":
            if rnode.node_def.subflow_of is None:
                self._output_refs.update({k: ray.get(v) for k, v in resolved.items()})
            return []

        if name in ("FlowInput", "OnEvent") and rnode.node_def.subflow_of is not None:
            self._write_node_outputs(node_id, {k: ray.get(v) for k, v in resolved.items()})
            targets = rnode.exec_targets.get("exec_out", [])
            if len(targets) > 1:
                await asyncio.gather(*[self._run_loop(t, node_id) for t in targets])
            elif targets:
                await self._run_loop(targets[0], node_id)
            return []

        ctx = ExecContext(
            node_id, self._graph_id, rnode.state_path,
            _output_writer=lambda nid, pin, val: self._write_node_outputs(nid, {pin: val}),
        )

        started_at = time.time()
        # Escribir meta inicial antes de run() para que downstream pueda leerla
        # aunque el nodo dispare ctx.fire() durante su ejecución.
        self._write_node_outputs(node_id, {
            "meta": self._build_meta(node_id, rnode, started_at, 0.0)
        })

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
        self._write_node_outputs(node_id, {
            "meta": self._build_meta(node_id, rnode, started_at, duration_ms)
        })
        return []

    # ------------------------------------------------------------------
    # @ray_node — actor Ray, localizado por nombre en el cluster
    # ------------------------------------------------------------------

    async def _fire_ray_node(self, node_id: str, rnode: ResolvedNode) -> list[str]:
        actor = self._get_actor(node_id)
        resolved = self._resolve_inputs(rnode)

        ctx = ExecContext(node_id, self._graph_id, rnode.state_path)
        started_at = time.time()
        # Meta inicial: downstream puede leerla si ctx.fire() ocurre durante run()
        self._write_node_outputs(node_id, {
            "meta": self._build_meta(node_id, rnode, started_at, 0.0)
        })
        await actor.run_with_ctx.remote(ctx, **resolved)
        duration_ms = (time.time() - started_at) * 1000
        self._write_node_outputs(node_id, {
            "meta": self._build_meta(node_id, rnode, started_at, duration_ms)
        })
        return []

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
            ctx = ExecContext(src_id, self._graph_id, src_rnode.state_path)
            result_ref = src_rnode.meta.ray_handle.remote(ctx, **data_inputs)
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

        ctx = ExecContext(rnode.node_def.id, self._graph_id, rnode.state_path)
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
            "flow": rnode.node_def.flow_name or self._built.flow_def.name,
            "started_at": started_at,
            "duration_ms": round(duration_ms, 3),
        }

    def _write_node_outputs(self, node_id: str, outputs: dict[str, Any]) -> None:
        ray.get(self._state.set_node_outputs.remote(node_id, outputs))


# ---------------------------------------------------------------------------
# Wrapper síncrono — crea el engine como actor Ray nombrado
# ---------------------------------------------------------------------------

class FlowExecutor:
    """Wrapper síncrono sobre FlowEngine para compatibilidad con api.py."""

    def __init__(self, built: BuiltFlow, flow_inputs: dict[str, Any] | None = None):
        self._built = built
        self._flow_inputs = flow_inputs or {}

    def execute(self) -> dict[str, Any]:
        graph_id = str(uuid.uuid4())

        # Spawn actores @ray_node en el driver: py_class está disponible aquí
        # directamente (no hay doble serialización). Los handles son serializables
        # y se pasan al FlowEngine actor.
        actors: dict[str, Any] = {}
        for node_id, rnode in self._built.nodes.items():
            if rnode.meta.is_engine_node or rnode.meta.is_parallel:
                continue
            if rnode.meta.is_exec_node and rnode.meta.ray_handle is not None:
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
        ).remote(self._built, self._flow_inputs, graph_id, actors)

        try:
            return ray.get(engine.execute.remote())
        finally:
            for actor in actors.values():
                try:
                    ray.kill(actor)
                except Exception:
                    pass
            try:
                ray.kill(engine)
            except Exception:
                pass
