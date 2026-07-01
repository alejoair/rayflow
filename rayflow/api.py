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
    """Loads a flow into Ray: creates actors and a persistent GraphState.

    Idempotent: if the flow is already loaded, it reloads it (destroys and recreates).

    Returns:
        graph_id of the loaded flow (= the flow's name).
    """
    flow_def = load_flow(source)
    catalog = get_catalog()
    built = build(flow_def, catalog)
    lf = load_flow_into_ray(built)
    return lf.graph_id


def unload(name: str) -> None:
    """Unloads a flow from Ray, destroying its actors and GraphState."""
    unload_flow_from_ray(name)


def execute(name: str, flow_inputs: dict[str, Any] | None = None) -> Generator[dict, None, None]:
    """Executes an already-loaded flow and streams its events.

    Yields event dicts: node_start, node_done, edge_fire, flow_done, flow_error.
    If the flow isn't loaded, it's loaded automatically first.
    """
    if not is_flow_loaded(name):
        load(name)

    lf = get_loaded_flow(name)
    run_id = uuid.uuid4().hex[:8]
    queue = lf._queue

    ray.get(queue.create_run.remote(run_id))
    lf.execute(flow_inputs or {}, run_id)

    # get() blocks on the actor until each event arrives — no polling, no sleep.
    try:
        while True:
            evt = ray.get(queue.get.remote(run_id, timeout=300.0))
            yield evt
            if evt.get("event") in ("flow_done", "flow_error"):
                break
    finally:
        ray.get(queue.close_run.remote(run_id))


async def execute_async(name: str, flow_inputs: dict[str, Any] | None = None) -> AsyncGenerator[dict, None]:
    """Async version of execute() — uses await instead of a blocking ray.get.

    Designed to be used from an async context (a FastAPI async generator),
    avoiding the run_in_executor overhead of the sync generator.
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
    """Reconnects to an active run already started by execute_async().

    Doesn't create or close the sub-queue — just consumes events from where
    it left off. Ends when flow_done/flow_error arrives, or on timeout.
    """
    lf = get_loaded_flow(name)
    if lf is None:
        yield {"event": "flow_error", "error": f"Flow '{name}' is not loaded", "ts": 0}
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
    """Loads, executes, and unloads a flow. One-shot compatibility wrapper.

    For stateful flows use load() + execute() + unload().
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
                raise RuntimeError(evt.get("error", "Unknown error"))
        return result
    finally:
        unload(name)


def serve_events(source: str | Path | dict, extra_node_dirs: list[str | Path] | None = None) -> str:
    """Loads a flow into Ray and subscribes it to the event bus.

    The flow stays resident: every time one of its declared events is
    emitted, the existing engine receives execute() with the payload.

    Returns:
        the assigned graph_id (= the flow's name).
    """
    flow_def = load_flow(source)
    catalog = get_catalog(extra_node_dirs)
    built = build(flow_def, catalog)

    graph_id = load_flow_into_ray(built).graph_id

    from rayflow.events.bus import get_event_broker
    broker = get_event_broker()
    for event_name in flow_def.events:
        ray.get(broker.subscribe.remote(event_name, flow_def.name, graph_id))

    # Register variable watches (OnVariableChange nodes): subscribes this
    # flow to the synthetic event var:{source}/{variable} and marks the
    # variable as watched in the source flow's GraphState (which must
    # already be loaded).
    for rnode in built.nodes.values():
        if rnode.meta.name != "OnVariableChange" or rnode.node_def.subflow_of is not None:
            continue
        cfg = rnode.node_def.inputs
        var = cfg.get("variable", "")
        if not var:
            continue
        src = cfg.get("source") or flow_def.name
        event_name = f"var:{src}/{var}"
        ray.get(broker.subscribe.remote(event_name, flow_def.name, graph_id))
        try:
            src_gs = ray.get_actor(f"gs_{src}", namespace="rayflow")
            ray.get(src_gs.watch_variable.remote(var, event_name))
        except ValueError:
            pass  # the source flow isn't loaded yet; load it before the watcher

    return graph_id


def stop(graph_id: str, event_names: list[str]) -> None:
    """Unsubscribes a flow from the event bus and unloads it from Ray."""
    from rayflow.events.bus import get_event_broker
    broker = get_event_broker()
    for event_name in event_names:
        ray.get(broker.unsubscribe.remote(event_name, graph_id))
    unload_flow_from_ray(graph_id)


@ray.remote
def _run_event_flow(flow_name: str, event_name: str, payload: Any) -> None:
    """Ray task that runs a resident flow when an event arrives.

    Resolves the flow via its named actors (engine_/queue_), not via the
    _loaded_flows registry: this task runs on a Ray worker distinct from
    the driver process, where _loaded_flows is empty. The loaded flow's
    detached actors ARE reachable by name from any process, though.
    """
    import uuid as _uuid

    try:
        engine = ray.get_actor(f"engine_{flow_name}", namespace="rayflow")
        queue = ray.get_actor(f"queue_{flow_name}", namespace="rayflow")
    except ValueError:
        return  # the flow isn't loaded (its actors don't exist)

    run_id = _uuid.uuid4().hex[:8]

    # Variable-change events (var:{flow}/{var}) carry a payload dict that IS
    # directly the set of flow_inputs (value/old/variable) consumed by the
    # OnVariableChange node. Every other event is wrapped in
    # {"payload": ...} for the OnEvent node.
    if isinstance(payload, dict) and event_name.startswith("var:"):
        flow_inputs = payload
    else:
        flow_inputs = {"payload": payload}

    ray.get(queue.create_run.remote(run_id))
    try:
        ray.get(engine.execute.remote(flow_inputs, queue, run_id))
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
