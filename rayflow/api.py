from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Generator

import ray

from rayflow.schema.loader import load_flow
from rayflow.nodes.registry import get_catalog
from rayflow.build.validator import build
from rayflow.engine.executor import (
    load_flow_into_ray,
    unload_flow_from_ray,
    get_loaded_flow,
    is_flow_loaded,
)


def load(source: str | Path | dict) -> str:
    """Carga un flow en Ray: crea actores y GraphState persistente.

    Idempotente: si el flow ya está cargado, lo recarga (destruye y recrea).

    Returns:
        graph_id del flow cargado (= nombre del flow).
    """
    flow_def = load_flow(source)
    catalog = get_catalog()
    built = build(flow_def, catalog)
    lf = load_flow_into_ray(built)
    return lf.graph_id


def unload(name: str) -> None:
    """Descarga un flow de Ray, destruyendo sus actores y GraphState."""
    unload_flow_from_ray(name)


def execute(name: str, flow_inputs: dict[str, Any] | None = None) -> Generator[dict, None, None]:
    """Ejecuta un flow ya cargado y hace streaming de eventos.

    Yields dicts con eventos: node_start, node_done, edge_fire, flow_done, flow_error.
    Si el flow no está cargado, lo carga automáticamente primero.
    """
    import time

    if not is_flow_loaded(name):
        load(name)

    lf = get_loaded_flow(name)

    from rayflow.state.queue import RunQueue
    queue = RunQueue.options(
        name=f"queue_{uuid.uuid4().hex[:8]}",
        namespace="rayflow",
        lifetime="detached",
    ).remote()

    ref = lf.execute(flow_inputs or {}, queue)

    # Drain la queue mientras el engine corre
    done = False
    while not done:
        events = ray.get(queue.drain.remote())
        for evt in events:
            yield evt
            if evt.get("event") in ("flow_done", "flow_error"):
                done = True
                break
        if not done:
            time.sleep(0.05)

    try:
        ray.kill(queue)
    except Exception:
        pass

    # Propagar excepción si el engine falló
    if not done:
        ray.get(ref)


def run(source: str | Path | dict, **inputs: Any) -> dict[str, Any]:
    """Carga, ejecuta y descarga un flow. Wrapper de compatibilidad one-shot.

    Para flows stateful usar load() + execute() + unload().
    """
    flow_def = load_flow(source)
    name = flow_def.name
    load(source)
    try:
        result: dict[str, Any] = {}
        for evt in execute(name, inputs):
            if evt.get("event") == "flow_done":
                result = evt.get("result", {})
            elif evt.get("event") == "flow_error":
                raise RuntimeError(evt.get("error", "Error desconocido"))
        return result
    finally:
        unload(name)


def serve_events(source: str | Path, extra_node_dirs: list[str | Path] | None = None) -> str:
    """Carga un flow en Ray y lo suscribe al bus de eventos.

    El flow queda residente: cada vez que se emita uno de sus eventos
    declarados, el engine existente recibe execute() con el payload.

    Returns:
        graph_id asignado (= nombre del flow).
    """
    flow_def = load_flow(source)
    catalog = get_catalog(extra_node_dirs)
    built = build(flow_def, catalog)

    graph_id = load_flow_into_ray(built).graph_id

    from rayflow.events.bus import get_event_broker
    broker = get_event_broker()
    for event_name in flow_def.events:
        ray.get(broker.subscribe.remote(event_name, flow_def.name, graph_id))

    return graph_id


def stop(graph_id: str, event_names: list[str]) -> None:
    """Desuscribe un flow del bus de eventos y lo descarga de Ray."""
    from rayflow.events.bus import get_event_broker
    broker = get_event_broker()
    for event_name in event_names:
        ray.get(broker.unsubscribe.remote(event_name, graph_id))
    unload_flow_from_ray(graph_id)


@ray.remote
def _run_event_flow(flow_name: str, event_name: str, payload: Any) -> None:
    """Task de Ray que ejecuta un flow residente al recibir un evento."""
    import uuid as _uuid
    from rayflow.state.queue import RunQueue

    lf = get_loaded_flow(flow_name)
    if lf is None:
        return

    queue = RunQueue.options(
        name=f"queue_{_uuid.uuid4().hex[:8]}",
        namespace="rayflow",
        lifetime="detached",
    ).remote()

    try:
        ray.get(lf.execute({"payload": payload}, queue))
    finally:
        try:
            ray.kill(queue)
        except Exception:
            pass


def _ensure_ray() -> None:
    if not ray.is_initialized():
        from rayflow.workspace import ensure_workspace, runtime_env
        ensure_workspace()
        kwargs: dict[str, Any] = {"ignore_reinit_error": True, "namespace": "rayflow"}
        env = runtime_env()
        if env is not None:
            kwargs["runtime_env"] = env
        ray.init(**kwargs)
        from rayflow.events.bus import get_event_broker
        get_event_broker()
