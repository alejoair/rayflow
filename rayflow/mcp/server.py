"""Curated set of MCP tools built with FastMCP.

Reuses the same logic as the editor's REST API (catalog, validation, CRUD,
execution) instead of reimplementing it, exposing it as tools designed for
an LLM: clear names, descriptions of when to use them, and input formats.

An agent's typical loop:
    get_guide -> list_nodes -> validate_flow (iterate) ->
    create_flow/update_flow -> test_flow / run_flow.

update_flow/delete_flow unload the flow from Ray if it was already loaded
(e.g. by a prior run_flow/test_flow call) — otherwise the next execution
would silently run the OLD graph, since run_flow/test_flow skip reloading
a flow that's already loaded as a performance shortcut.
"""
from __future__ import annotations

from typing import Any


def create_mcp():
    """Builds the FastMCP server with Rayflow's curated tools.

    The tools operate against rayflow.api (which uses rayflow.registry
    internally) — no `served` parameter is needed anymore.
    """
    from fastmcp import FastMCP

    from rayflow.nodes.registry import get_catalog
    from rayflow.schema.loader import load_flow, unknown_keys
    from rayflow.build.validator import validate_all
    from rayflow.types import compatible
    from rayflow.editor.routes import _node_spec
    from rayflow.editor.storage import (
        delete_flow as _delete_flow,
        get_flow_dict,
        list_flows as _list_flows,
        save_flow,
        flow_to_dict,
    )

    mcp = FastMCP("Rayflow")

    def _unload_if_loaded(name: str) -> bool:
        from rayflow.api import is_flow_loaded, unload as unload_api
        if is_flow_loaded(name):
            unload_api(name)
            return True
        return False

    # ----- Discovery -----

    @mcp.tool
    def get_guide() -> str:
        """Guide to Rayflow's model (flow JSON structure, wiring rules,
        dynamic pins, types). CALL THIS FIRST to learn how a flow is
        built."""
        from rayflow.editor.guide import GUIDE
        return GUIDE

    @mcp.tool
    def list_nodes() -> list[dict[str, Any]]:
        """Full catalog of node types with their input/output pins, exec
        outputs, category, description, and dynamic pins. Use it to learn
        which nodes exist and how they connect."""
        return [_node_spec(name, meta) for name, _cls, meta in get_catalog()]

    @mcp.tool
    def get_node(node_type: str) -> dict[str, Any]:
        """Spec of a specific node type (pins, types, defaults, description)."""
        entry = get_catalog().get(node_type)
        if entry is None:
            return {"error": f"Node type '{node_type}' not found"}
        _cls, meta = entry
        return _node_spec(node_type, meta)

    @mcp.tool
    def list_types() -> dict[str, Any]:
        """Available canonical types and strict compatibility rules."""
        from rayflow.types import PRIMITIVES
        return {
            "primitives": sorted(PRIMITIVES),
            "generics": ["list[T]", "dict[str, V]"],
            "notes": [
                "Strict compatibility: same type, or one of the two is Any.",
                "int and float are incompatible — use ToInt / ToFloat to cast.",
            ],
        }

    @mcp.tool
    def type_check(from_type: str, to_type: str) -> dict[str, Any]:
        """Checks whether a pin of type from_type can connect to one of type to_type."""
        try:
            ok = compatible(to_type, from_type)
        except Exception as e:
            return {"error": str(e)}
        return {"compatible": ok, "from_type": from_type, "to_type": to_type}

    # ----- Validation -----

    @mcp.tool
    def validate_flow(flow: dict) -> dict[str, Any]:
        """Validates a FlowDef WITHOUT running it. Returns ALL errors and
        warnings in a single pass. Use it in a loop until valid=true before
        saving the flow. `flow` is the flow's full JSON object."""
        if not isinstance(flow, dict):
            return {"valid": False, "errors": ["The flow must be a JSON object"], "warnings": []}
        warnings = unknown_keys(flow)
        try:
            flow_def = load_flow(flow)
            errors = validate_all(flow_def, get_catalog())
        except Exception as e:
            return {"valid": False, "errors": [f"Parse error: {e}"], "warnings": warnings}
        return {"valid": not errors, "errors": errors, "warnings": warnings}

    # ----- Flow CRUD -----

    @mcp.tool
    def list_flows() -> list[dict[str, Any]]:
        """Lists saved flows with their public interface (inputs/outputs)."""
        return [
            {
                "name": f.get("name"),
                "version": f.get("version", "1"),
                "inputs": f.get("inputs", {}),
                "outputs": f.get("outputs", {}),
            }
            for f in _list_flows()
        ]

    @mcp.tool
    def get_flow(name: str) -> dict[str, Any]:
        """Returns the full JSON FlowDef of a saved flow."""
        data = get_flow_dict(name)
        if data is None:
            return {"error": f"Flow '{name}' not found"}
        return data

    @mcp.tool
    def create_flow(flow: dict) -> dict[str, Any]:
        """Creates and saves a new flow. Validate first with validate_flow.
        Fails if a flow with that name already exists (use update_flow to edit)."""
        if not isinstance(flow, dict):
            return {"error": "The flow must be a JSON object"}
        try:
            flow_def = load_flow(flow)
        except Exception as e:
            return {"error": f"Invalid FlowDef: {e}"}
        if get_flow_dict(flow_def.name) is not None:
            return {"error": f"A flow named '{flow_def.name}' already exists"}
        save_flow(flow_def)
        return flow_to_dict(flow_def)

    @mcp.tool
    def update_flow(name: str, flow: dict) -> dict[str, Any]:
        """Updates (or creates) the flow `name` with the given FlowDef.
        If the flow was already loaded (e.g. by a prior run_flow/test_flow
        call), it's unloaded so the next run picks up this change instead
        of silently reusing the old graph."""
        if not isinstance(flow, dict):
            return {"error": "The flow must be a JSON object"}
        if "name" not in flow:
            flow = {**flow, "name": name}
        if flow.get("name") != name:
            return {"error": f"The body's name ('{flow.get('name')}') doesn't match '{name}'"}
        try:
            flow_def = load_flow(flow)
        except Exception as e:
            return {"error": f"Invalid FlowDef: {e}"}
        save_flow(flow_def)
        _unload_if_loaded(name)
        return flow_to_dict(flow_def)

    @mcp.tool
    def delete_flow(name: str) -> dict[str, Any]:
        """Deletes a saved flow, unloading it from Ray first if it was
        loaded (otherwise its actors/GraphState would keep running,
        orphaned, with no saved flow left to reference them)."""
        _unload_if_loaded(name)
        ok = _delete_flow(name)
        return {"deleted": ok, "flow": name}

    @mcp.tool
    def unload_flow(name: str) -> dict[str, Any]:
        """Unloads a flow from Ray (destroys its actors/GraphState) without
        touching the saved JSON. Use it to free resources, or to force the
        next run_flow/test_flow to rebuild the graph from scratch."""
        was_loaded = _unload_if_loaded(name)
        return {"flow": name, "was_loaded": was_loaded}

    @mcp.tool
    def flow_catalog(name: str) -> dict[str, Any]:
        """Resolved catalog of a flow: each node with its REAL pins in this
        context, including the dynamic ones (OnStart's outputs = the
        flow's inputs, Parallel's branch_N branches, etc.). Use it to know
        exactly what you can wire up."""
        from rayflow.build.validator import flatten, _with_dynamic_pins
        from rayflow.editor.routes import _pin_spec

        data = get_flow_dict(name)
        if data is None:
            return {"error": f"Flow '{name}' not found"}
        catalog = get_catalog()
        try:
            flat = flatten(load_flow(data), catalog)
        except Exception as e:
            return {"error": f"Could not flatten the flow: {e}"}
        nodes_out = []
        for nd in flat.nodes:
            entry = catalog.get(nd.type)
            if entry is None:
                nodes_out.append({"id": nd.id, "type": nd.type, "error": "unknown type"})
                continue
            _cls, meta = entry
            meta = _with_dynamic_pins(meta, flat, nd)
            nodes_out.append({
                "id": nd.id,
                "type": nd.type,
                "inputs": [_pin_spec(p) for p in meta.inputs],
                "outputs": [{"name": p.name, "type": p.type or "Any"} for p in meta.outputs],
                "exec_outputs": meta.exec_outputs,
            })
        return {"flow": name, "nodes": nodes_out}

    # ----- Custom nodes -----

    @mcp.tool
    def list_custom_nodes() -> list[dict[str, Any]]:
        """Lists the custom node .py files in custom_nodes/ (name, filename,
        size). Use it before creating a node to check one doesn't already
        exist under that name."""
        from rayflow.editor.custom_nodes_routes import custom_nodes_path
        cn = custom_nodes_path()
        if not cn.exists():
            return []
        return [
            {"name": p.stem, "filename": p.name, "size": p.stat().st_size}
            for p in sorted(cn.glob("*.py"))
            if p.name != "__init__.py" and not p.name.startswith("_")
        ]

    @mcp.tool
    def get_custom_node_source(name: str) -> dict[str, Any]:
        """Returns the source code of a custom node file."""
        from rayflow.editor.custom_nodes_routes import _node_file
        path = _node_file(name)
        if not path.exists():
            return {"error": f"Custom node '{name}' not found"}
        return {"name": name, "source": path.read_text(encoding="utf-8")}

    @mcp.tool
    def create_custom_node(name: str, source: str | None = None) -> dict[str, Any]:
        """Creates a new custom node .py file under custom_nodes/ and
        hot-reloads the catalog so list_nodes/validate_flow see it
        immediately — no server restart needed. If `source` is omitted, a
        minimal @engine_node template is used. The node must be decorated
        with @ray_node, @engine_node, or @parallel_node (see get_guide)."""
        from rayflow.editor.custom_nodes_routes import (
            NODE_TEMPLATE, _ensure_package, _node_file, _reload_catalog, _validate_syntax,
        )
        name = name.strip()
        if not name:
            return {"error": "The 'name' field is required"}
        if not name.isidentifier():
            return {"error": f"'{name}' is not a valid Python identifier"}
        _ensure_package()
        path = _node_file(name)
        if path.exists():
            return {"error": f"A custom node named '{name}' already exists"}
        code = source or NODE_TEMPLATE.format(name=name)
        err = _validate_syntax(code)
        if err:
            return {"error": err}
        path.write_text(code, encoding="utf-8")
        return {"name": name, "created": True, **_reload_catalog()}

    @mcp.tool
    def update_custom_node_source(name: str, source: str) -> dict[str, Any]:
        """Saves edited source for an existing custom node and hot-reloads
        the catalog."""
        from rayflow.editor.custom_nodes_routes import _node_file, _reload_catalog, _validate_syntax
        path = _node_file(name)
        if not path.exists():
            return {"error": f"Custom node '{name}' not found"}
        if not source.strip():
            return {"error": "The 'source' field cannot be empty"}
        err = _validate_syntax(source)
        if err:
            return {"error": err}
        path.write_text(source, encoding="utf-8")
        return {"name": name, "saved": True, **_reload_catalog()}

    @mcp.tool
    def delete_custom_node(name: str) -> dict[str, Any]:
        """Deletes a custom node's .py file and hot-reloads the catalog."""
        from rayflow.editor.custom_nodes_routes import _node_file, _reload_catalog
        path = _node_file(name)
        if not path.exists():
            return {"error": f"Custom node '{name}' not found"}
        path.unlink()
        return {"name": name, "deleted": True, **_reload_catalog()}

    @mcp.tool
    def reload_custom_nodes() -> dict[str, Any]:
        """Re-scans custom_nodes/ and rebuilds the node catalog from disk.
        Call this if a custom node file was edited by some means other
        than create_custom_node/update_custom_node_source (e.g. directly
        on the filesystem) and list_nodes still shows the old version."""
        from rayflow.editor.custom_nodes_routes import _reload_catalog
        return _reload_catalog()

    # ----- Events -----

    @mcp.tool
    def serve_flow_events(name: str) -> dict[str, Any]:
        """Loads a saved flow and subscribes it to the event bus so it
        stays resident and reacts whenever one of its declared `events` is
        emitted (via an OnEvent node) or a watched variable changes (via
        OnVariableChange). The flow must declare its events in its `events`
        field — see get_guide. Returns graph_id; save it to unsubscribe
        later with stop_flow_events."""
        from rayflow.api import serve_events
        data = get_flow_dict(name)
        if data is None:
            return {"error": f"Flow '{name}' not found"}
        try:
            graph_id = serve_events(data)
        except Exception as e:
            return {"error": f"Error registering the flow: {e}"}
        return {"graph_id": graph_id, "flow": name}

    @mcp.tool
    def stop_flow_events(name: str, graph_id: str) -> dict[str, Any]:
        """Unsubscribes a resident flow (registered via serve_flow_events)
        from the event bus and unloads it."""
        from rayflow.api import stop
        data = get_flow_dict(name)
        if data is None:
            return {"error": f"Flow '{name}' not found"}
        try:
            flow_def = load_flow(data)
            stop(graph_id, flow_def.events)
        except Exception as e:
            return {"error": f"Error unsubscribing the flow: {e}"}
        return {"flow": name, "graph_id": graph_id, "stopped": True}

    # ----- Execution / verification -----

    async def _run_and_collect(name: str, inputs: dict | None, trace: bool) -> dict[str, Any]:
        """Shared execution loop for run_flow/test_flow. `trace=True` keeps
        every node_start/node_done/edge_fire event (in order) so a caller
        can see which node produced what — the flow_done event alone only
        carries the FINAL outputs, which isn't enough to localize a bug in
        the middle of a chain."""
        from rayflow.api import execute_async, load as load_api, is_flow_loaded

        data = get_flow_dict(name)
        if data is None:
            return {"error": f"Flow '{name}' not found"}
        if not is_flow_loaded(name):
            try:
                load_api(data)
            except Exception as e:
                return {"error": f"Error loading the flow: {e}"}
        result: dict[str, Any] = {}
        events: list[dict[str, Any]] = []
        async for evt in execute_async(name, inputs or {}):
            if trace and evt.get("event") in ("node_start", "node_done", "edge_fire"):
                events.append(evt)
            if evt.get("event") == "flow_done":
                result = evt.get("result", {}) or {}
            elif evt.get("event") == "flow_error":
                out = {"error": evt.get("error", "Unknown error")}
                if trace:
                    out["trace"] = events
                return out
        out = {"outputs": result}
        if trace:
            out["trace"] = events
        return out

    @mcp.tool
    async def run_flow(name: str, inputs: dict | None = None, trace: bool = False) -> dict[str, Any]:
        """Runs a saved flow (loading it if needed) and returns its
        outputs. `inputs` maps each declared input of the flow to its
        value. Set `trace=True` to also get the ordered node_start/
        node_done/edge_fire events — use it when the final output is wrong
        and you need to see what each node along the way actually produced."""
        return await _run_and_collect(name, inputs, trace)

    @mcp.tool
    async def test_flow(
        name: str, inputs: dict | None = None, expected_outputs: dict | None = None,
        trace: bool = False,
    ) -> dict[str, Any]:
        """Runs a flow and compares its outputs against expected_outputs.
        Use it to verify the flow DOES what was asked (not just that it's
        valid). Returns passed, actual, expected, and the mismatches. Set
        `trace=True` to also get per-node events when a mismatch needs
        localizing."""
        out = await _run_and_collect(name, inputs, trace)
        if "error" in out:
            return {"passed": False, "actual": {}, "expected": expected_outputs,
                     "error": out["error"], **({"trace": out["trace"]} if trace else {})}
        actual = out["outputs"]
        if expected_outputs is None:
            result = {"passed": None, "actual": actual, "expected": None}
        else:
            mismatches = {
                k: {"expected": v, "actual": actual.get(k)}
                for k, v in expected_outputs.items()
                if actual.get(k) != v
            }
            result = {"passed": not mismatches, "actual": actual,
                      "expected": expected_outputs, "mismatches": mismatches}
        if trace:
            result["trace"] = out["trace"]
        return result

    return mcp
