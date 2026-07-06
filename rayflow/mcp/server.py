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

    mcp = FastMCP(
        "Rayflow",
        instructions=(
            "Rayflow is a workflow orchestration engine: a flow is a JSON "
            "graph of nodes connected by exec edges (sequential control "
            "flow) and data edges (values evaluated in parallel), executed "
            "on Ray actors/tasks.\n\n"
            "Call get_guide FIRST — it explains the flow JSON structure, "
            "wiring rules, and type system. Then list_nodes to see which "
            "node types are available. Typical loop: get_guide -> "
            "list_nodes -> validate_flow (iterate until valid=true) -> "
            "create_flow/update_flow -> run_flow/test_flow."
        ),
    )

    def _unload_if_loaded(name: str) -> bool:
        from rayflow.api import is_flow_loaded, unload as unload_api
        if is_flow_loaded(name):
            unload_api(name)
            return True
        return False

    # ----- Discovery -----

    @mcp.tool
    def get_guide() -> str:
        """START HERE: markdown guide to Rayflow's flow model — read this
        before calling any other tool.

        Covers the flow JSON structure (nodes, exec vs. data wiring),
        dynamic pins (FlowOutput, Parallel branches, CallFlow), the type
        system, and the recommended build loop (get_guide -> list_nodes ->
        validate_flow -> create_flow/update_flow -> run_flow/test_flow)."""
        from rayflow.editor.guide import GUIDE
        return GUIDE

    @mcp.tool
    def list_nodes() -> list[dict[str, Any]]:
        """Full catalog of every node type (built-in and custom) with its
        pins — call this after get_guide, before writing any flow JSON.

        Each entry lists input/output pins with their types, exec outputs,
        category, description, and any dynamic-pin notes. Use get_node
        instead if you already know the type name and just need its spec."""
        return [_node_spec(name, meta) for name, _cls, meta in get_catalog()]

    @mcp.tool
    def get_node(node_type: str) -> dict[str, Any]:
        """Spec (pins, types, defaults, description) of one node type by
        name — a single-entry shortcut for list_nodes when you already know
        which type you want. Example: get_node(node_type="Add") returns its
        `a`/`b` int inputs and `result` int output."""
        entry = get_catalog().get(node_type)
        if entry is None:
            return {"error": f"Node type '{node_type}' not found"}
        _cls, meta = entry
        return _node_spec(node_type, meta)

    @mcp.tool
    def list_types() -> dict[str, Any]:
        """Canonical type names (`int`, `str`, `list[T]`, ...) and Rayflow's
        strict compatibility rule: two pins connect only if they're the
        same type or one of them is `Any`. See type_check to test one
        specific pair instead of reading the whole rule set."""
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
        """Checks whether a pin of type `from_type` can be wired into a pin
        declared `to_type`, without building a whole flow just to find out.
        Example: type_check(from_type="int", to_type="float") returns
        compatible=false — int and float need an explicit ToInt/ToFloat
        cast (see list_types)."""
        try:
            ok = compatible(to_type, from_type)
        except Exception as e:
            return {"error": str(e)}
        return {"compatible": ok, "from_type": from_type, "to_type": to_type}

    # ----- Validation -----

    @mcp.tool
    def validate_flow(flow: dict) -> dict[str, Any]:
        """Validates a flow's full JSON WITHOUT running or saving it — run
        this before create_flow/update_flow/run_flow. Returns every error
        and warning in ONE pass, so you can loop on this tool (fix, re-call)
        until `valid` is true instead of discovering problems one at a time
        during a real run. `flow` is the complete flow JSON object (see
        get_guide for its shape)."""
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
        """Lists every saved flow's name and public interface (version,
        inputs, outputs) — a lightweight index. Use get_flow for one flow's
        full JSON, or flow_catalog for its already-resolved node pins."""
        return [
            {
                "name": f.get("name"),
                "version": f.get("version", "1"),
                "inputs": f.get("inputs", {}),
                "outputs": f.get("outputs", {}),
                "public": f.get("public", False),
            }
            for f in _list_flows()
        ]

    @mcp.tool
    def get_flow(name: str) -> dict[str, Any]:
        """Returns one saved flow's complete JSON, in the same shape
        validate_flow/update_flow expect back. Use list_flows first if you
        don't already know the exact `name`."""
        data = get_flow_dict(name)
        if data is None:
            return {"error": f"Flow '{name}' not found"}
        return data

    @mcp.tool
    def create_flow(flow: dict) -> dict[str, Any]:
        """Saves a brand-new flow — run validate_flow on the same JSON
        first, since this tool only does structural parsing, not the full
        error/warning sweep validate_flow gives you. Fails if
        `flow["name"]` already exists (use update_flow to edit that flow
        instead). Example: create_flow(flow={"name": "suma",
        "outputs": {"resultado": "int"}, "nodes": [...]})."""
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
        """Overwrites (or creates) the saved flow `name` with `flow`'s
        JSON — validate_flow first to avoid saving a broken graph. If
        `name` was already loaded into Ray (e.g. by an earlier
        run_flow/test_flow), it is automatically unloaded here so the NEXT
        run rebuilds from this new JSON instead of silently reusing the
        stale graph — no need to call unload_flow yourself for this. If
        `flow` includes a "name" key, it must match `name`."""
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
        """Permanently deletes a saved flow's JSON (no confirmation step —
        unlike unload_flow, which only frees runtime resources and keeps
        the saved JSON). Unloads it from Ray first if it was loaded,
        otherwise its actors/GraphState would keep running orphaned with no
        saved flow left to reference them."""
        _unload_if_loaded(name)
        ok = _delete_flow(name)
        return {"deleted": ok, "flow": name}

    @mcp.tool
    def unload_flow(name: str) -> dict[str, Any]:
        """Frees a flow's Ray actors/GraphState WITHOUT touching its saved
        JSON — use it to release resources, or to force the next
        run_flow/test_flow to rebuild the graph from scratch (e.g. right
        after editing a custom node the flow uses). Safe to call even if
        the flow isn't currently loaded; check the returned `was_loaded`."""
        was_loaded = _unload_if_loaded(name)
        return {"flow": name, "was_loaded": was_loaded}

    @mcp.tool
    def flow_catalog(name: str) -> dict[str, Any]:
        """Resolved, node-by-node pin list for one SAVED flow — unlike
        list_nodes/get_node (which describe a node type in the abstract),
        this shows the REAL pins in THIS flow's context, including dynamic
        ones not in the static catalog (FlowOutput's per-output inputs,
        Parallel's branch_N branches, CallFlow's subflow inputs). Call this
        right before wiring a new node into an existing flow, to see
        exactly what's available to reference."""
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
        """Lists user-defined custom node .py files under custom_nodes/
        (name, filename, size). Check this before create_custom_node to
        avoid a name collision, or before get_custom_node_source /
        update_custom_node_source to confirm the exact name."""
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
        """Returns one custom node's full Python source — read it before
        editing with update_custom_node_source, or use list_custom_nodes
        first if you don't know the exact name."""
        from rayflow.editor.custom_nodes_routes import _node_file
        path = _node_file(name)
        if not path.exists():
            return {"error": f"Custom node '{name}' not found"}
        return {"name": name, "source": path.read_text(encoding="utf-8")}

    @mcp.tool
    async def create_custom_node(name: str, source: str | None = None) -> dict[str, Any]:
        """Writes a new custom node .py file under custom_nodes/ and
        immediately hot-reloads the catalog — no separate call to
        reload_custom_nodes or server restart needed; list_nodes/
        validate_flow see it right away.

        Delegates directly to the same handler as POST
        /editor/custom-nodes (rayflow/editor/custom_nodes_routes.py)
        instead of reimplementing its write+reload logic, so the response
        matches it exactly: on top of "created" (only means the file was
        written to disk — nothing about whether it actually loaded), it
        includes "registered" (whether `name` shows up in the reloaded
        catalog) and "error" (the real exception message from
        NodeCatalog.load_errors when the module failed to import/register,
        or None otherwise). A node can be "created": true but
        "registered": false if, e.g., the class raises on import (missing
        decorator requirement, bad pin config, etc.) — check "error" for
        why.

        Omit `source` to get a minimal @engine_node template to fill in;
        when supplying your own, decorate the class with @ray_node,
        @engine_node, or @parallel_node (see get_guide). Example:
        create_custom_node(name="DoubleIt", source="<python source
        defining class DoubleIt>")."""
        from fastapi import HTTPException
        from rayflow.editor.custom_nodes_routes import (
            create_custom_node as _create_custom_node,
        )
        try:
            return await _create_custom_node(body={"name": name, "source": source})
        except HTTPException as e:
            return {"error": e.detail}

    @mcp.tool
    async def update_custom_node_source(name: str, source: str) -> dict[str, Any]:
        """Overwrites an existing custom node's source and hot-reloads the
        catalog (same automatic reload as create_custom_node — no separate
        reload_custom_nodes call needed). This is also how to make an
        entry node support a frontend bundle: add a `frontend = "<dir>"`
        class attribute here, then manage its index.html with
        get_entry_frontend/update_entry_frontend.

        Delegates directly to the same handler as PUT
        /editor/custom-nodes/{name}/source instead of reimplementing its
        write+reload logic, so the response includes "registered"/"error"
        exactly like create_custom_node above — "saved": true only means
        the file was written; check "registered"/"error" for whether the
        edited source actually imports and registers under `name`."""
        from fastapi import HTTPException
        from rayflow.editor.custom_nodes_routes import (
            update_custom_node_source as _update_custom_node_source,
        )
        try:
            return await _update_custom_node_source(name=name, body={"source": source})
        except HTTPException as e:
            return {"error": e.detail}

    @mcp.tool
    def delete_custom_node(name: str) -> dict[str, Any]:
        """Deletes a custom node's .py file and hot-reloads the catalog, so
        it disappears from list_nodes immediately. Any saved flow still
        referencing this node type will start failing validate_flow/
        run_flow afterwards."""
        from rayflow.editor.custom_nodes_routes import _node_file, _reload_catalog
        path = _node_file(name)
        if not path.exists():
            return {"error": f"Custom node '{name}' not found"}
        path.unlink()
        return {"name": name, "deleted": True, **_reload_catalog()}

    @mcp.tool
    def reload_custom_nodes() -> dict[str, Any]:
        """Re-scans custom_nodes/ and rebuilds the node catalog from disk —
        rarely needed directly, since create_custom_node/
        update_custom_node_source/delete_custom_node already trigger this
        automatically. Call it manually only if a node file was edited some
        other way (e.g. directly on the filesystem) and list_nodes still
        shows a stale version."""
        from rayflow.editor.custom_nodes_routes import _reload_catalog
        return _reload_catalog()

    # ----- Entry node frontend bundle -----

    @mcp.tool
    def get_entry_frontend(node_type: str) -> dict[str, Any]:
        """Reads the index.html of an entry node's optional static UI
        bundle (served at /flows/{name}/ui when a flow using this entry
        node is served) — pair with update_entry_frontend to write or
        replace it. Only applies to entry nodes (@entry_node) that declare
        a `frontend = "<dir>"` class attribute — e.g. ChatTrigger, whose
        bundle is a single self-contained index.html with inline CSS/JS
        (see rayflow/nodes/builtin/control.py). Only that one file is
        managed here; multi-file bundles aren't supported.

        Returns {"node_type", "bundle_dir", "exists", "html"} —
        `exists=False`/`html=None` means the node declares `frontend` but
        nothing has been written to disk yet (not an error). Returns
        {"error": ...} if node_type doesn't exist, or if it exists but
        doesn't declare `frontend` — in that case, add
        `frontend = "some_dir_name"` as a class attribute first (for a
        custom node, via update_custom_node_source) before calling this."""
        from fastapi import HTTPException
        from rayflow.editor.routes import _resolve_frontend_bundle_dir
        try:
            bundle_dir = _resolve_frontend_bundle_dir(node_type)
        except HTTPException as e:
            return {"error": e.detail}
        index = bundle_dir / "index.html"
        if not index.is_file():
            return {"node_type": node_type, "bundle_dir": str(bundle_dir), "exists": False, "html": None}
        return {
            "node_type": node_type,
            "bundle_dir": str(bundle_dir),
            "exists": True,
            "html": index.read_text(encoding="utf-8"),
        }

    @mcp.tool
    def update_entry_frontend(node_type: str, html: str) -> dict[str, Any]:
        """Creates or overwrites the index.html of an entry node's frontend
        bundle (see get_entry_frontend) — the only way a remote MCP client
        with no filesystem access can author this UI. Only applies to
        entry nodes that declare `frontend = "<dir>"` (see
        get_entry_frontend). Creates the bundle directory
        (sibling to the node's source file, named after its `frontend`
        attribute) if it doesn't exist yet. `html` should be a complete,
        self-contained document (inline CSS/JS) — the same pattern as the
        built-in ChatTrigger's bundle — since only this single file is
        managed here.

        Returns {"error": ...} if node_type doesn't exist, doesn't declare
        `frontend` (add it via update_custom_node_source first), or if
        `html` is empty."""
        from fastapi import HTTPException
        from rayflow.editor.routes import _resolve_frontend_bundle_dir
        try:
            bundle_dir = _resolve_frontend_bundle_dir(node_type)
        except HTTPException as e:
            return {"error": e.detail}
        if not isinstance(html, str) or not html.strip():
            return {"error": "The 'html' field is required and cannot be empty"}
        bundle_dir.mkdir(parents=True, exist_ok=True)
        (bundle_dir / "index.html").write_text(html, encoding="utf-8")
        return {"node_type": node_type, "bundle_dir": str(bundle_dir), "saved": True}

    @mcp.tool
    def delete_entry_frontend(node_type: str) -> dict[str, Any]:
        """Deletes an entry node's index.html, leaving the bundle directory
        itself in place (see get_entry_frontend) — call update_entry_frontend
        afterwards to write a new one. Only applies to entry nodes that
        declare `frontend = "<dir>"`. Returns {"error": ...} if node_type
        doesn't exist, doesn't declare `frontend`, or has no index.html to
        delete."""
        from fastapi import HTTPException
        from rayflow.editor.routes import _resolve_frontend_bundle_dir
        try:
            bundle_dir = _resolve_frontend_bundle_dir(node_type)
        except HTTPException as e:
            return {"error": e.detail}
        index = bundle_dir / "index.html"
        if not index.is_file():
            return {"error": f"Node type '{node_type}' has no index.html to delete"}
        index.unlink()
        return {"node_type": node_type, "deleted": True}

    # ----- Events -----

    @mcp.tool
    def serve_flow_events(name: str) -> dict[str, Any]:
        """Loads a saved flow and keeps it resident, subscribed to the
        event bus, so it reacts whenever one of its declared `events` fires
        (via an EmitEvent node elsewhere) or a watched variable changes
        (OnVariableChange) — unlike run_flow, this doesn't run once and
        return outputs; it registers a standing listener. The flow's own
        JSON must declare its `events` (see get_guide). Save the returned
        `graph_id` to unsubscribe later with stop_flow_events."""
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
        """Unsubscribes a flow previously registered with serve_flow_events
        and unloads it from Ray. Pass the same `graph_id` that
        serve_flow_events returned."""
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
        """Runs a saved flow end-to-end (loading it into Ray first if
        needed) and returns its final outputs — run validate_flow
        beforehand to avoid runtime surprises. `inputs` maps each of the
        flow's declared input names to a value, e.g. {"x": 2, "y": 3}. Set
        `trace=True` to also get the ordered node_start/node_done/
        edge_fire events for every node touched — use it when the final
        output looks wrong and you need to see what an intermediate node
        actually produced. If you already know the expected outputs, use
        test_flow instead to get a pass/fail comparison for free."""
        return await _run_and_collect(name, inputs, trace)

    @mcp.tool
    async def test_flow(
        name: str, inputs: dict | None = None, expected_outputs: dict | None = None,
        trace: bool = False,
    ) -> dict[str, Any]:
        """Like run_flow, but also compares the outputs against
        `expected_outputs` — use this instead of run_flow whenever you
        already know what a flow SHOULD produce (e.g. right after
        update_flow, to confirm the edit did what was intended). Returns
        `passed`/`actual`/`expected`/`mismatches`; omit `expected_outputs`
        to just capture `actual` with `passed=None`. Same `trace=True`
        option as run_flow, for localizing a mismatch to a specific node.
        Example: test_flow(name="suma", inputs={"x": 2, "y": 3},
        expected_outputs={"resultado": 5})."""
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
