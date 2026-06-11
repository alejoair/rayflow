from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import ray

from rayflow.schema.loader import load_flow
from rayflow.nodes.registry import get_catalog
from rayflow.build.validator import build
from rayflow.engine.executor import FlowExecutor


def run(source: str | Path | dict, **inputs: Any) -> dict[str, Any]:
    """Carga, valida y ejecuta un flow de forma síncrona.

    Args:
        source: Ruta a un .json, dict ya parseado, o FlowDef.
        **inputs: Valores de los data inputs declarados en `FlowInput`.

    Returns:
        Dict con los outputs declarados en `FlowOutput`, ya materializados.
    """
    _ensure_ray()
    flow_def = load_flow(source)
    catalog = get_catalog()
    built = build(flow_def, catalog)
    return FlowExecutor(built, inputs).execute()


def run_async(source: str | Path | dict, **inputs: Any):
    """Lanza la ejecución en un task de Ray y devuelve un ObjectRef awaitable.

    `await rayflow.run_async(...)` o `ray.get(rayflow.run_async(...))` entregan
    los mismos outputs que run().
    """
    _ensure_ray()
    # _run_flow_task es picklable y reconstruye el flow dentro del worker.
    return _run_flow_task.remote(source, inputs)


def serve(source: str | Path, extra_node_dirs: list[str | Path] | None = None) -> str:
    """Registra un flow por evento en el bus global y lo deja residente.

    Returns:
        graph_id único asignado a este flow residente.
    """
    _ensure_ray()
    from rayflow.events.bus import get_event_bus

    flow_def = load_flow(source)
    catalog = get_catalog(extra_node_dirs)
    build(flow_def, catalog)  # validación temprana

    graph_id = str(uuid.uuid4())
    bus = get_event_bus()
    for event_name in flow_def.events:
        ray.get(bus.subscribe.remote(event_name, str(source), graph_id))
    return graph_id


def stop(graph_id: str, event_names: list[str]) -> None:
    """Desuscribe un flow residente del bus de eventos."""
    from rayflow.events.bus import get_event_bus
    bus = get_event_bus()
    for event_name in event_names:
        ray.get(bus.unsubscribe.remote(event_name, graph_id))


@ray.remote
def _run_flow_task(source: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Task de Ray que ejecuta un flow (usado por run_async y por eventos)."""
    flow_def = load_flow(source)
    catalog = get_catalog()
    built = build(flow_def, catalog)
    return FlowExecutor(built, inputs).execute()


@ray.remote
def _run_event_flow(flow_path: str, event_name: str, payload: Any) -> None:
    """Ejecuta un flow disparado por evento (fire-and-forget, sección 4)."""
    flow_def = load_flow(flow_path)
    catalog = get_catalog()
    built = build(flow_def, catalog)
    FlowExecutor(built, {"_event_name": event_name, "_payload": payload}).execute()


def _ensure_ray() -> None:
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, namespace="rayflow")
