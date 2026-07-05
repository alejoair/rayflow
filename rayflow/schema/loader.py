from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rayflow.schema.models import FlowDef, NodeDef, VariableDef


_FLOW_KEYS = {"name", "version", "outputs", "variables", "events", "nodes", "public"}
_NODE_KEYS = {"id", "type", "inputs", "exec_in", "ui", "state_path"}
_VAR_KEYS = {"name", "type", "default"}


def unknown_keys(data: dict) -> list[str]:
    """Detects unrecognized keys in a FlowDef already parsed into a dict.

    The parser (`_parse_flow`) is tolerant and silently drops any key it
    doesn't understand. That hides typos typical of an LLM ('input' instead
    of 'inputs', 'exec' instead of 'exec_in'): the field gets ignored and
    the error later surfaces as a confusing 'pin required but has no
    value'. This function reports them as warnings to close that gap
    without breaking the parser's tolerance.
    """
    warnings: list[str] = []
    if not isinstance(data, dict):
        return warnings
    for k in data:
        if k not in _FLOW_KEYS:
            warnings.append(f"flow: unknown key '{k}' (ignored)")
    for v in data.get("variables", []) or []:
        if isinstance(v, dict):
            for k in v:
                if k not in _VAR_KEYS:
                    warnings.append(f"variable '{v.get('name', '?')}': unknown key '{k}' (ignored)")
    for n in data.get("nodes", []) or []:
        if isinstance(n, dict):
            nid = n.get("id", "?")
            for k in n:
                if k not in _NODE_KEYS:
                    warnings.append(f"node '{nid}': unknown key '{k}' (ignored)")
    return warnings


def load_flow(source: str | Path | dict) -> FlowDef:
    """Loads a FlowDef from a JSON file, a path, or an already-parsed dict."""
    if isinstance(source, dict):
        data = source
    else:
        path = Path(source)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

    return _parse_flow(data)


def _parse_flow(data: dict[str, Any]) -> FlowDef:
    variables = [
        VariableDef(
            name=v["name"],
            type=v.get("type", "Any"),
            default=v.get("default"),
        )
        for v in data.get("variables", [])
    ]

    nodes = [_parse_node(n) for n in data.get("nodes", [])]

    return FlowDef(
        name=data["name"],
        version=str(data.get("version", "1")),
        outputs=data.get("outputs", {}),
        variables=variables,
        events=data.get("events", []),
        nodes=nodes,
        public=bool(data.get("public", False)),
    )


def _parse_node(data: dict[str, Any]) -> NodeDef:
    return NodeDef(
        id=data["id"],
        type=data["type"],
        inputs=data.get("inputs", {}),
        exec_in=data.get("exec_in"),
        ui=data.get("ui"),
    )
