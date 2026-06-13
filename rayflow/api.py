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


def serve_events(source: str | Path, extra_node_dirs: list[str | Path] | None = None) -> str:
    """Registra un flow por evento en el bus global y lo deja residente.

    Distinto de la API REST (`rayflow serve` en el CLI): esto suscribe el flow
    al bus de eventos interno para que se dispare al emitirse uno de sus eventos.

    Returns:
        graph_id único asignado a este flow residente.
    """
    _ensure_ray()
    from rayflow.events.bus import get_event_broker

    flow_def = load_flow(source)
    catalog = get_catalog(extra_node_dirs)
    build(flow_def, catalog)  # validación temprana

    graph_id = str(uuid.uuid4())
    broker = get_event_broker()
    # source tal cual (ruta o dict) — str() perdería un dict inline.
    for event_name in flow_def.events:
        ray.get(broker.subscribe.remote(event_name, source, graph_id))
    return graph_id


def stop(graph_id: str, event_names: list[str]) -> None:
    """Desuscribe un flow residente del broker de eventos."""
    from rayflow.events.bus import get_event_broker
    broker = get_event_broker()
    for event_name in event_names:
        ray.get(broker.unsubscribe.remote(event_name, graph_id))


@ray.remote
def _run_flow_task(source: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Task de Ray que ejecuta un flow (usado por run_async y por eventos)."""
    flow_def = load_flow(source)
    catalog = get_catalog()
    built = build(flow_def, catalog)
    return FlowExecutor(built, inputs).execute()


@ray.remote
def _run_event_flow(source: Any, event_name: str, payload: Any) -> None:
    """Ejecuta un flow disparado por evento (fire-and-forget).

    El engine escribe los flow_inputs como outputs del entry node; al pasar
    'payload' con ese nombre, el output `payload` del OnEvent queda poblado y
    el subgrafo del flow receptor puede consumirlo como "on.payload".
    """
    flow_def = load_flow(source)
    catalog = get_catalog()
    built = build(flow_def, catalog)
    FlowExecutor(built, {"payload": payload}).execute()


def _ensure_ray() -> None:
    if not ray.is_initialized():
        from rayflow.workspace import ensure_workspace, runtime_env
        ensure_workspace()
        kwargs: dict[str, Any] = {"ignore_reinit_error": True, "namespace": "rayflow"}
        env = runtime_env()
        if env is not None:
            # Distribuye custom_nodes/ a todos los workers Ray (py_modules), así
            # los nodos custom son importables en cualquier proceso del cluster.
            kwargs["runtime_env"] = env
        ray.init(**kwargs)
        # Garantiza que el broker de eventos existe en el cluster desde el inicio.
        # Sin esto, el broker se crearía la primera vez que alguien llame
        # get_event_broker(), con el riesgo de que suscripciones hechas antes
        # de ray.init se pierdan silenciosamente tras un reinicio de Ray.
        from rayflow.events.bus import get_event_broker
        get_event_broker()
