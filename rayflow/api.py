from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Generator

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
    if not is_flow_loaded(name):
        load(name)

    lf = get_loaded_flow(name)
    run_id = uuid.uuid4().hex[:8]
    queue = lf._queue

    ray.get(queue.create_run.remote(run_id))
    lf.execute(flow_inputs or {}, run_id)

    # get() bloquea en el actor hasta que llega cada evento — sin polling ni sleep
    try:
        while True:
            evt = ray.get(queue.get.remote(run_id, timeout=300.0))
            yield evt
            if evt.get("event") in ("flow_done", "flow_error"):
                break
    finally:
        ray.get(queue.close_run.remote(run_id))


async def execute_async(name: str, flow_inputs: dict[str, Any] | None = None) -> AsyncGenerator[dict, None]:
    """Versión async de execute() — usa await en lugar de ray.get bloqueante.

    Designed para usarse desde un async context (FastAPI async generator),
    evitando el overhead de run_in_executor del generador síncrono.
    """
    import time as _time

    def _ts(label: str, t0: float) -> None:
        print(f"[timing] {label}: +{(_time.perf_counter() - t0)*1000:.1f}ms")

    t0 = _time.perf_counter()
    _ts("execute_async start", t0)

    if not is_flow_loaded(name):
        load(name)
        _ts("load", t0)

    lf = get_loaded_flow(name)
    run_id = uuid.uuid4().hex[:8]
    queue = lf._queue
    _ts("queue handle obtained", t0)

    await queue.create_run.remote(run_id)
    _ts("create_run", t0)

    yield {"event": "run_start", "run_id": run_id, "ts": 0}

    lf.execute(flow_inputs or {}, run_id)
    _ts("execute dispatched", t0)

    try:
        while True:
            evt = await queue.get.remote(run_id, timeout=300.0)
            _ts(f"got event: {evt.get('event')} node={evt.get('node_id','')}", t0)
            yield evt
            if evt.get("event") in ("flow_done", "flow_error"):
                break
    finally:
        await queue.close_run.remote(run_id)


async def reconnect_async(name: str, run_id: str) -> AsyncGenerator[dict, None]:
    """Reconecta a un run activo ya iniciado por execute_async().

    No crea ni cierra la sub-queue — solo consume eventos desde donde se quedó.
    Termina cuando llega flow_done/flow_error o timeout.
    """
    lf = get_loaded_flow(name)
    if lf is None:
        yield {"event": "flow_error", "error": f"Flow '{name}' no está cargado", "ts": 0}
        return

    queue = lf._queue
    try:
        while True:
            evt = await queue.get.remote(run_id, timeout=300.0)
            yield evt
            if evt.get("event") in ("flow_done", "flow_error"):
                break
    except Exception as e:
        yield {"event": "flow_error", "error": str(e), "ts": 0}


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
    """Task de Ray que ejecuta un flow residente al recibir un evento.

    Resuelve el flow por sus actores con nombre (engine_/queue_), no por el
    registro _loaded_flows: esta task corre en un worker de Ray distinto del
    proceso driver, donde _loaded_flows está vacío. Los actores detached del
    flow cargado sí son alcanzables por nombre desde cualquier proceso.
    """
    import uuid as _uuid

    try:
        engine = ray.get_actor(f"engine_{flow_name}", namespace="rayflow")
        queue = ray.get_actor(f"queue_{flow_name}", namespace="rayflow")
    except ValueError:
        return  # el flow no está cargado (sus actores no existen)

    run_id = _uuid.uuid4().hex[:8]

    ray.get(queue.create_run.remote(run_id))
    try:
        ray.get(engine.execute.remote({"payload": payload}, queue, run_id))
    finally:
        ray.get(queue.close_run.remote(run_id))


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
