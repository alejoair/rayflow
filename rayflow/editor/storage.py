"""Persistencia de flows en el directorio flows/ del workspace."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rayflow.schema.models import FlowDef, NodeDef
from rayflow.workspace import flows_path


def flow_to_dict(flow: FlowDef) -> dict[str, Any]:
    """Serializa un FlowDef a dict JSON-serializable.

    Solo escribe los campos del usuario (no los generados por flatten como
    state_path, subflow_of, etc.). El campo `ui` se preserva si está presente.
    """
    return {
        "name": flow.name,
        "version": flow.version,
        "inputs": flow.inputs,
        "outputs": flow.outputs,
        "variables": [
            {"name": v.name, "type": v.type, "default": v.default}
            for v in flow.variables
        ],
        "events": flow.events,
        "nodes": [_node_to_dict(n) for n in flow.nodes],
    }


def _node_to_dict(n: NodeDef) -> dict[str, Any]:
    d: dict[str, Any] = {"id": n.id, "type": n.type}
    if n.inputs:
        d["inputs"] = n.inputs
    if n.exec_in is not None:
        d["exec_in"] = n.exec_in
    if n.ui is not None:
        d["ui"] = n.ui
    return d


def _flow_path(name: str) -> Path:
    return flows_path() / f"{name}.json"


def list_flows() -> list[dict[str, Any]]:
    """Devuelve todos los flows del directorio flows/ como dicts."""
    base = flows_path()
    if not base.exists():
        return []
    result = []
    for p in sorted(base.glob("*.json")):
        try:
            result.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return result


def get_flow_dict(name: str) -> dict[str, Any] | None:
    """Lee un flow por nombre. Devuelve None si no existe."""
    p = _flow_path(name)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_flow(flow: FlowDef) -> None:
    """Guarda un FlowDef en flows/{name}.json, creando el directorio si no existe."""
    base = flows_path()
    base.mkdir(parents=True, exist_ok=True)
    p = _flow_path(flow.name)
    p.write_text(json.dumps(flow_to_dict(flow), indent=2, ensure_ascii=False), encoding="utf-8")


def delete_flow(name: str) -> bool:
    """Elimina flows/{name}.json. Devuelve True si existía."""
    p = _flow_path(name)
    if not p.exists():
        return False
    p.unlink()
    return True
