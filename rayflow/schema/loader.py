from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rayflow.schema.models import FlowDef, NodeDef, VariableDef


_FLOW_KEYS = {"name", "version", "inputs", "outputs", "variables", "events", "nodes"}
_NODE_KEYS = {"id", "type", "inputs", "exec_in", "ui", "state_path"}
_VAR_KEYS = {"name", "type", "default"}


def unknown_keys(data: dict) -> list[str]:
    """Detecta claves no reconocidas en un FlowDef ya parseado a dict.

    El parser (`_parse_flow`) es tolerante y descarta en silencio cualquier
    clave que no entienda. Eso oculta erratas típicas de un LLM ('input' por
    'inputs', 'exec' por 'exec_in'): el campo se ignora y el error aflora más
    tarde como un confuso 'pin requerido sin valor'. Esta función las reporta
    como warnings para cerrar ese hueco sin romper la tolerancia del parser.
    """
    warnings: list[str] = []
    if not isinstance(data, dict):
        return warnings
    for k in data:
        if k not in _FLOW_KEYS:
            warnings.append(f"flow: clave desconocida '{k}' (ignorada)")
    for v in data.get("variables", []) or []:
        if isinstance(v, dict):
            for k in v:
                if k not in _VAR_KEYS:
                    warnings.append(f"variable '{v.get('name', '?')}': clave desconocida '{k}' (ignorada)")
    for n in data.get("nodes", []) or []:
        if isinstance(n, dict):
            nid = n.get("id", "?")
            for k in n:
                if k not in _NODE_KEYS:
                    warnings.append(f"nodo '{nid}': clave desconocida '{k}' (ignorada)")
    return warnings


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
