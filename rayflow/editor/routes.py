"""Visual editor endpoints: catalog, flow CRUD, validation."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from rayflow.build.validator import validate_all
from rayflow.nodes.registry import get_catalog
from rayflow.schema.loader import load_flow, unknown_keys
from rayflow.types import PRIMITIVES, compatible

from .storage import delete_flow, get_flow_dict, list_flows, save_flow

router = APIRouter(prefix="/editor", tags=["editor"])


# ---------------------------------------------------------------------------
# Node catalog
# ---------------------------------------------------------------------------

def _pin_spec(p) -> dict[str, Any]:
    from rayflow.nodes.decorators import _MISSING
    d: dict[str, Any] = {"name": p.name, "kind": p.kind, "type": p.type or "Any", "required": p.required}
    if p.default is not _MISSING:
        d["default"] = p.default
    return d


# Pins the build generates dynamically and that do NOT appear in the
# catalog's static metadata. Documenting them here lets a client (the editor
# or an LLM agent) know they exist and how they're named, without having to
# memorize the convention. See `_with_dynamic_pins` in build/validator.py.
_DYNAMIC_PINS: dict[str, dict[str, Any]] = {
    "OnStart": {"outputs_from": "flow.inputs",
                "note": "Exposes one data output per declared input of the flow (e.g. 'entry.x')."},
    "FlowInput": {"outputs_from": "flow.inputs",
                  "note": "Alias of OnStart. Exposes one data output per input of the flow."},
    "OnEvent": {"outputs_from": "flow.inputs",
                "note": "Exposes one data output per declared input of the flow (the event's payload)."},
    "FlowOutput": {"inputs_from": "flow.outputs",
                   "note": "Receives one required data input per declared output of the flow."},
    "Parallel": {"exec_outputs_pattern": "branch_N",
                 "note": "Branches branch_0, branch_1, … are discovered from the wiring; 'joined' fires once they're all done."},
    "CallFlow": {"inputs_pattern": "arbitrary",
                 "note": "Accepts arbitrary inputs that get mapped to the invoked subflow's inputs."},
}


def _node_spec(node_type: str, meta) -> dict[str, Any]:
    if meta.is_parallel:
        decorator = "parallel_node"
    elif meta.is_engine_node:
        decorator = "engine_node"
    else:
        decorator = "ray_node"

    spec = {
        "type": node_type,
        "decorator": decorator,
        "has_exec_in": meta.has_exec_in,
        "has_exec_out": meta.has_exec_out,
        "is_exec_node": meta.is_exec_node,
        "is_parallel": meta.is_parallel,
        "inputs": [_pin_spec(p) for p in meta.inputs],
        "outputs": [{"name": p.name, "kind": p.kind, "type": p.type or "Any"} for p in meta.outputs],
        "exec_outputs": meta.exec_outputs,
        # Newer fields:
        "is_builtin": meta.is_builtin,           # True for builtin, False for custom
        "category": meta.category,                # "Control", "Math", etc.
        "description": meta.description,          # Docstring, or None
    }
    if node_type in _DYNAMIC_PINS:
        spec["dynamic"] = _DYNAMIC_PINS[node_type]
    return spec


@router.get("/info")
async def editor_info() -> dict[str, Any]:
    """Active workspace info: cwd and version."""
    import os
    return {"cwd": os.getcwd()}


@router.get("/nodes")
async def list_nodes() -> list[dict[str, Any]]:
    """Returns the full catalog of node types with their pins."""
    catalog = get_catalog()
    return [_node_spec(name, meta) for name, _cls, meta in catalog]


@router.get("/nodes/{node_type}")
async def get_node(node_type: str) -> dict[str, Any]:
    """Returns the spec of a specific node type."""
    catalog = get_catalog()
    entry = catalog.get(node_type)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Node type '{node_type}' not found")
    _cls, meta = entry
    return _node_spec(node_type, meta)


@router.get("/flows/{name}/catalog")
async def flow_catalog(name: str) -> dict[str, Any]:
    """Resolved catalog for a specific flow: each node with its real pins.

    Unlike `/editor/nodes` (static metadata), here the dynamic pins are
    applied in the context of THIS flow: OnStart's outputs are already the
    flow's inputs, FlowOutput's inputs are its outputs, Parallel's branch_N
    branches, etc. Meant to let an agent see exactly what it can wire up.
    """
    from rayflow.build.validator import flatten, _with_dynamic_pins

    data = get_flow_dict(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Flow '{name}' not found")
    catalog = get_catalog()
    try:
        flat = flatten(load_flow(data), catalog)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not flatten the flow: {e}")

    nodes_out: list[dict[str, Any]] = []
    for nd in flat.nodes:
        entry = catalog.get(nd.type)
        if entry is None:
            nodes_out.append({"id": nd.id, "type": nd.type, "error": "type is not in the catalog"})
            continue
        _cls, meta = entry
        meta = _with_dynamic_pins(meta, flat, nd)
        nodes_out.append({
            "id": nd.id,
            "type": nd.type,
            "inputs": [_pin_spec(p) for p in meta.inputs],
            "outputs": [{"name": p.name, "kind": p.kind, "type": p.type or "Any"} for p in meta.outputs],
            "exec_outputs": meta.exec_outputs,
        })
    return {"flow": name, "nodes": nodes_out}


@router.get("/guide")
async def get_guide() -> dict[str, Any]:
    """Curated guide to Rayflow's model (markdown) for building flows."""
    from .guide import GUIDE
    return {"guide": GUIDE}


def _examples_dir():
    from pathlib import Path
    return Path(__file__).parent / "examples"


@router.get("/examples")
async def list_examples() -> dict[str, Any]:
    """Lists the bundled example flows (few-shot templates)."""
    import json
    examples = []
    d = _examples_dir()
    if d.exists():
        for path in sorted(d.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            examples.append({
                "name": path.stem,
                "flow_name": data.get("name"),
                "inputs": data.get("inputs", {}),
                "outputs": data.get("outputs", {}),
            })
    return {"examples": examples}


@router.get("/examples/{name}")
async def get_example(name: str) -> dict[str, Any]:
    """Returns the full JSON of an example flow by its file name."""
    import json
    path = _examples_dir() / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Example '{name}' not found")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading the example: {e}")


@router.get("/types")
async def get_types() -> dict[str, Any]:
    """Available canonical types and compatibility rules."""
    return {
        "primitives": sorted(PRIMITIVES),
        "generics": [
            {"base": "list", "example": "list[str]", "description": "list[T]"},
            {"base": "dict", "example": "dict[str, Any]", "description": "dict[str, V]"},
        ],
        "notes": [
            "Strict compatibility: same type, or one of the two is Any",
            "int and float are incompatible — use ToInt / ToFloat to cast",
        ],
    }


@router.post("/type-check")
async def type_check(body: dict = Body(...)) -> dict[str, Any]:
    """Checks whether from_type can connect to to_type.

    Body: {"from_type": "int", "to_type": "str"}
    """
    from_type = body.get("from_type")
    to_type = body.get("to_type")
    if from_type is None or to_type is None:
        raise HTTPException(status_code=400, detail="'from_type' and 'to_type' are required")
    try:
        result = compatible(to_type, from_type)  # compatible(consumer, producer)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"compatible": result, "from_type": from_type, "to_type": to_type}


# ---------------------------------------------------------------------------
# Flow validation
# ---------------------------------------------------------------------------

@router.post("/validate")
async def validate_flow(flow_data: Any = Body(...)) -> dict[str, Any]:
    """Validates a FlowDef without running it.

    Returns ALL build errors in a single pass (not just the first one) so an
    iterating client — the editor or an LLM agent — can fix the flow in
    fewer round-trips. `warnings` lists unknown schema keys.
    """
    if not isinstance(flow_data, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object of a FlowDef")
    warnings = unknown_keys(flow_data)
    try:
        flow_def = load_flow(flow_data)
        catalog = get_catalog()
        errors = validate_all(flow_def, catalog)
        return {"valid": not errors, "errors": errors, "warnings": warnings}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse error: {e}")


# ---------------------------------------------------------------------------
# Flow CRUD
# ---------------------------------------------------------------------------

@router.get("/flows")
async def list_editor_flows() -> dict[str, Any]:
    """Lists every flow in the flows/ directory."""
    flows = list_flows()
    return {
        "flows": [
            {
                "name": f.get("name"),
                "version": f.get("version", "1"),
                "inputs": f.get("inputs", {}),
                "outputs": f.get("outputs", {}),
            }
            for f in flows
        ]
    }


@router.get("/flows/loaded")
async def list_loaded_flows() -> dict[str, Any]:
    """Lists every flow currently loaded into Ray, with its public interface."""
    from rayflow.engine.executor import _loaded_flows
    result = []
    for name, lf in _loaded_flows.items():
        entry: dict[str, Any] = {"flow": name}
        if lf.flow_def is not None:
            entry["inputs"] = {
                k: {"type": v} for k, v in lf.flow_def.inputs.items()
            }
            entry["outputs"] = {
                k: {"type": v} for k, v in lf.flow_def.outputs.items()
            }
        result.append(entry)
    return {"loaded": result, "count": len(result)}


@router.get("/flows/{name}")
async def get_editor_flow(name: str) -> dict[str, Any]:
    """Returns the full FlowDef of a flow by name."""
    data = get_flow_dict(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Flow '{name}' not found")
    return data


@router.post("/flows", status_code=201)
async def create_flow(flow_data: Any = Body(...)) -> dict[str, Any]:
    """Creates a new flow and saves it to flows/{name}.json."""
    if not isinstance(flow_data, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object of a FlowDef")
    try:
        flow_def = load_flow(flow_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid FlowDef: {e}")

    if get_flow_dict(flow_def.name) is not None:
        raise HTTPException(status_code=409, detail=f"A flow named '{flow_def.name}' already exists")

    save_flow(flow_def)
    from .storage import flow_to_dict
    return flow_to_dict(flow_def)


@router.put("/flows/{name}")
async def update_flow(name: str, flow_data: Any = Body(...)) -> dict[str, Any]:
    """Updates an existing flow. Creates the file if it doesn't exist."""
    if not isinstance(flow_data, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object of a FlowDef")

    # Lets the frontend omit the name in the body and take it from the path.
    if "name" not in flow_data:
        flow_data = {**flow_data, "name": name}

    if flow_data.get("name") != name:
        raise HTTPException(
            status_code=400,
            detail=f"The body's name ('{flow_data['name']}') doesn't match the path ('{name}')"
        )

    try:
        flow_def = load_flow(flow_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid FlowDef: {e}")

    save_flow(flow_def)
    from .storage import flow_to_dict
    return flow_to_dict(flow_def)


@router.delete("/flows/{name}", status_code=204)
async def delete_editor_flow(name: str) -> Response:
    """Deletes a flow from the flows/ directory."""
    if not delete_flow(name):
        raise HTTPException(status_code=404, detail=f"Flow '{name}' not found")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Execution from the editor
# ---------------------------------------------------------------------------

@router.post("/flows/{name}/load", status_code=200)
async def load_editor_flow(name: str) -> dict[str, Any]:
    """Loads a flow into Ray: initializes actors and persistent GraphState.

    Idempotent — if already loaded, reloads it (resets state).
    """
    import asyncio
    from functools import partial
    from rayflow.api import load as load_flow_api

    data = get_flow_dict(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Flow '{name}' not found")
    try:
        loop = asyncio.get_event_loop()
        graph_id = await loop.run_in_executor(None, partial(load_flow_api, data))
        return {"graph_id": graph_id, "flow": name, "loaded": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading the flow: {e}")


@router.delete("/flows/{name}/load", status_code=200)
async def unload_editor_flow(name: str) -> dict[str, Any]:
    """Unloads a flow from Ray, destroying its actors and GraphState."""
    from rayflow.api import unload as unload_flow_api
    unload_flow_api(name)
    return {"flow": name, "loaded": False}


@router.get("/flows/{name}/loaded")
async def flow_loaded_status(name: str) -> dict[str, Any]:
    """Returns whether the flow is currently loaded into Ray."""
    from rayflow.api import is_flow_loaded
    return {"flow": name, "loaded": is_flow_loaded(name)}


def wants_stream(request: Request) -> bool:
    """True if the caller asked for SSE via `Accept: text/event-stream`.

    Same header a plain `curl`/`fetch` caller would set to opt into
    streaming — no bespoke header or body flag, and no different code path
    for the editor frontend vs. any other API consumer.
    """
    return "text/event-stream" in request.headers.get("accept", "")


async def run_flow_response(name: str, flow_inputs: dict[str, Any], *, stream: bool) -> Response:
    """Runs a flow and renders the result as SSE or a single JSON response.

    Shared by `/editor/flows/{name}/run` (editor flows, loads on demand) and
    `/flows/{name}/run` in server.py (pre-loaded served flows) — the only
    difference between those two callers is how `flow_inputs` is assembled
    and whether the flow needs loading first; the execute-and-render logic
    lives here once.
    """
    import json
    from rayflow.api import execute_async

    if stream:
        async def event_generator():
            try:
                async for evt in execute_async(name, flow_inputs):
                    yield f"data: {json.dumps(evt)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'event': 'flow_error', 'error': str(e)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    result: dict[str, Any] = {}
    response_status = 200
    response_headers: dict[str, str] = {}
    try:
        async for evt in execute_async(name, flow_inputs):
            if evt.get("event") == "flow_done":
                result = evt.get("result", {}) or {}
                response_status = evt.get("response_status", 200)
                response_headers = evt.get("response_headers", {}) or {}
            elif evt.get("event") == "flow_error":
                raise HTTPException(
                    status_code=500, detail=f"Error running the flow: {evt.get('error')}"
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running the flow: {e}")
    return JSONResponse(content=result, status_code=response_status, headers=response_headers)


@router.post("/flows/{name}/run")
async def run_editor_flow(request: Request, name: str, inputs: Any = Body(default=None)):
    """Runs a flow (loading it if needed).

    Set `Accept: text/event-stream` to get a stream of events (node_start,
    node_done, edge_fire, flow_done, flow_error); otherwise returns a single
    JSON response with the flow's outputs once it finishes.
    """
    import asyncio
    from functools import partial
    from rayflow.api import load as load_flow_api, is_flow_loaded

    if inputs is None:
        inputs = {}
    if not isinstance(inputs, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object of inputs")

    data = get_flow_dict(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Flow '{name}' not found")

    # Load if not already loaded.
    if not is_flow_loaded(name):
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, partial(load_flow_api, data))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error loading the flow: {e}")

    return await run_flow_response(name, inputs, stream=wants_stream(request))


@router.post("/flows/{name}/test")
async def test_editor_flow(name: str, body: Any = Body(default=None)) -> dict[str, Any]:
    """Runs a flow and compares its outputs against the expected ones.

    Closes an agent's self-verification loop: `/validate` confirms the graph
    is valid; `/test` confirms it DOES what was asked.

    Body: {"inputs": {...}, "expected_outputs": {...}}. If expected_outputs
    is omitted, returns the actual outputs without comparing (passed=null).
    """
    import asyncio
    from functools import partial
    from rayflow.api import execute_async, load as load_flow_api, is_flow_loaded

    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    inputs = body.get("inputs", {})
    expected = body.get("expected_outputs")
    if not isinstance(inputs, dict):
        raise HTTPException(status_code=400, detail="'inputs' must be a JSON object")

    data = get_flow_dict(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Flow '{name}' not found")

    if not is_flow_loaded(name):
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, partial(load_flow_api, data))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error loading the flow: {e}")

    actual: dict[str, Any] = {}
    error: str | None = None
    async for evt in execute_async(name, inputs):
        if evt.get("event") == "flow_done":
            actual = evt.get("result", {}) or {}
        elif evt.get("event") == "flow_error":
            error = evt.get("error", "Unknown error")

    if error is not None:
        return {"passed": False, "actual": actual, "expected": expected, "error": error}

    if expected is None:
        return {"passed": None, "actual": actual, "expected": None}

    mismatches = {
        k: {"expected": v, "actual": actual.get(k)}
        for k, v in expected.items()
        if actual.get(k) != v
    }
    return {
        "passed": not mismatches,
        "actual": actual,
        "expected": expected,
        "mismatches": mismatches,
    }


@router.get("/flows/{name}/run/{run_id}/stream")
async def reconnect_flow_run(name: str, run_id: str):
    """Reconnects to an active SSE run without relaunching execution.

    Useful when the client loses connection while the flow is still
    running. Returns the pending events from the moment of reconnection.
    """
    import json
    from fastapi.responses import StreamingResponse
    from rayflow.api import reconnect_async, is_flow_loaded

    if not is_flow_loaded(name):
        raise HTTPException(status_code=404, detail=f"Flow '{name}' is not loaded")

    async def event_generator():
        try:
            async for evt in reconnect_async(name, run_id):
                yield f"data: {json.dumps(evt)}\n\n"
        except Exception as e:
            import json as _json
            yield f"data: {_json.dumps({'event': 'flow_error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Events — subscribe and unsubscribe
# ---------------------------------------------------------------------------

@router.post("/flows/{name}/serve-events", status_code=201)
async def serve_flow_events(name: str) -> dict[str, Any]:
    """Registers a flow as an event listener (serve_events).

    The flow must have an OnEvent node with event_name configured, and must
    declare that event in its `events` field. Returns the assigned graph_id;
    use it to unsubscribe later.
    """
    from rayflow.api import serve_events

    data = get_flow_dict(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Flow '{name}' not found")
    try:
        graph_id = serve_events(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error registering the flow: {e}")
    return {"graph_id": graph_id, "flow": name}


@router.delete("/flows/{name}/serve-events/{graph_id}", status_code=204)
async def stop_flow_events(name: str, graph_id: str) -> Response:
    """Unsubscribes a resident flow from the event bus."""
    from rayflow.api import stop

    data = get_flow_dict(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Flow '{name}' not found")
    try:
        flow_def = load_flow(data)
        stop(graph_id, flow_def.events)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error unsubscribing the flow: {e}")
    return Response(status_code=204)
