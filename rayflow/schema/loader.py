from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rayflow.schema.models import FlowDef, NodeDef, VariableDef


def load_flow(source: str | Path | dict) -> FlowDef:
    """Carga un FlowDef desde un archivo JSON, path o dict ya parseado."""
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
        inputs=data.get("inputs", {}),
        outputs=data.get("outputs", {}),
        variables=variables,
        events=data.get("events", []),
        nodes=nodes,
    )


def _parse_node(data: dict[str, Any]) -> NodeDef:
    return NodeDef(
        id=data["id"],
        type=data["type"],
        inputs=data.get("inputs", {}),
        exec_in=data.get("exec_in"),
        ui=data.get("ui"),
    )
