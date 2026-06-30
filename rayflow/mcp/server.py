"""Curated set of MCP tools built with FastMCP.

Reuses the same logic as the editor's REST API (catalog, validation, CRUD,
execution) instead of reimplementing it, exposing it as tools designed for
an LLM: clear names, descriptions of when to use them, and input formats.

An agent's typical loop:
    get_guide -> list_nodes -> [get_example] -> validate_flow (iterate) ->
    create_flow/update_flow -> test_flow / run_flow.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def create_mcp(served: dict | None = None):
    """Builds the FastMCP server with Rayflow's curated tools."""
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
        """Updates (or creates) the flow `name` with the given FlowDef."""
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
        return flow_to_dict(flow_def)

    @mcp.tool
    def delete_flow(name: str) -> dict[str, Any]:
        """Deletes a saved flow."""
        ok = _delete_flow(name)
        return {"deleted": ok, "flow": name}

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

    # ----- Execution / verification -----

    @mcp.tool
    async def run_flow(name: str, inputs: dict | None = None) -> dict[str, Any]:
        """Runs a saved flow (loading it if needed) and returns its
        outputs. `inputs` maps each declared input of the flow to its value."""
        from rayflow.api import execute_async, load as load_api, is_flow_loaded

        if get_flow_dict(name) is None:
            return {"error": f"Flow '{name}' not found"}
        data = get_flow_dict(name)
        if not is_flow_loaded(name):
            try:
                load_api(data)
            except Exception as e:
                return {"error": f"Error loading the flow: {e}"}
        result: dict[str, Any] = {}
        async for evt in execute_async(name, inputs or {}):
            if evt.get("event") == "flow_done":
                result = evt.get("result", {}) or {}
            elif evt.get("event") == "flow_error":
                return {"error": evt.get("error", "Unknown error")}
        return {"outputs": result}

    @mcp.tool
    async def test_flow(
        name: str, inputs: dict | None = None, expected_outputs: dict | None = None
    ) -> dict[str, Any]:
        """Runs a flow and compares its outputs against expected_outputs.
        Use it to verify the flow DOES what was asked (not just that it's
        valid). Returns passed, actual, expected, and the mismatches."""
        from rayflow.api import execute_async, load as load_api, is_flow_loaded

        data = get_flow_dict(name)
        if data is None:
            return {"error": f"Flow '{name}' not found"}
        if not is_flow_loaded(name):
            try:
                load_api(data)
            except Exception as e:
                return {"error": f"Error loading the flow: {e}"}
        actual: dict[str, Any] = {}
        async for evt in execute_async(name, inputs or {}):
            if evt.get("event") == "flow_done":
                actual = evt.get("result", {}) or {}
            elif evt.get("event") == "flow_error":
                return {"passed": False, "actual": actual,
                        "expected": expected_outputs, "error": evt.get("error")}
        if expected_outputs is None:
            return {"passed": None, "actual": actual, "expected": None}
        mismatches = {
            k: {"expected": v, "actual": actual.get(k)}
            for k, v in expected_outputs.items()
            if actual.get(k) != v
        }
        return {"passed": not mismatches, "actual": actual,
                "expected": expected_outputs, "mismatches": mismatches}

    # ----- Examples -----

    def _examples_dir() -> Path:
        return Path(__file__).parent.parent / "editor" / "examples"

    @mcp.tool
    def list_examples() -> list[dict[str, Any]]:
        """Lists the bundled example flows (few-shot templates)."""
        out = []
        d = _examples_dir()
        if d.exists():
            for path in sorted(d.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                out.append({"name": path.stem, "flow_name": data.get("name"),
                            "inputs": data.get("inputs", {}), "outputs": data.get("outputs", {})})
        return out

    @mcp.tool
    def get_example(name: str) -> dict[str, Any]:
        """Returns the full JSON of an example flow (use it as a template)."""
        path = _examples_dir() / f"{name}.json"
        if not path.exists():
            return {"error": f"Example '{name}' not found"}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            return {"error": str(e)}

    return mcp
