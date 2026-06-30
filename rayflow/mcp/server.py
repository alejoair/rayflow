"""Set curado de tools MCP construido con FastMCP.

Reusa la misma lógica que la API REST del editor (catálogo, validación, CRUD,
ejecución) en vez de reimplementarla, exponiéndola como tools pensadas para un
LLM: nombres claros, descripciones de cuándo usarlas y formatos de entrada.

El loop típico de un agente:
    get_guide -> list_nodes -> [get_example] -> validate_flow (itera) ->
    create_flow/update_flow -> test_flow / run_flow.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def create_mcp(served: dict | None = None):
    """Construye el servidor FastMCP con las tools curadas de Rayflow."""
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

    # ----- Descubrimiento -----

    @mcp.tool
    def get_guide() -> str:
        """Guía del modelo de Rayflow (estructura del flow JSON, reglas de
        cableado, pins dinámicos, tipos). LLAMA ESTO PRIMERO para saber cómo se
        construye un flow."""
        from rayflow.editor.guide import GUIDE
        return GUIDE

    @mcp.tool
    def list_nodes() -> list[dict[str, Any]]:
        """Catálogo completo de tipos de nodo con sus pins de entrada/salida,
        exec outputs, categoría, descripción y pins dinámicos. Úsalo para saber
        qué nodos existen y cómo se conectan."""
        return [_node_spec(name, meta) for name, _cls, meta in get_catalog()]

    @mcp.tool
    def get_node(node_type: str) -> dict[str, Any]:
        """Spec de un tipo de nodo concreto (pins, tipos, defaults, descripción)."""
        entry = get_catalog().get(node_type)
        if entry is None:
            return {"error": f"Tipo de nodo '{node_type}' no encontrado"}
        _cls, meta = entry
        return _node_spec(node_type, meta)

    @mcp.tool
    def list_types() -> dict[str, Any]:
        """Tipos canónicos disponibles y reglas de compatibilidad estricta."""
        from rayflow.types import PRIMITIVES
        return {
            "primitives": sorted(PRIMITIVES),
            "generics": ["list[T]", "dict[str, V]"],
            "notes": [
                "Compatibilidad estricta: mismo tipo o uno de los dos es Any.",
                "int y float son incompatibles — usar ToInt / ToFloat para castear.",
            ],
        }

    @mcp.tool
    def type_check(from_type: str, to_type: str) -> dict[str, Any]:
        """Comprueba si un pin de tipo from_type puede conectarse a uno to_type."""
        try:
            ok = compatible(to_type, from_type)
        except Exception as e:
            return {"error": str(e)}
        return {"compatible": ok, "from_type": from_type, "to_type": to_type}

    # ----- Validación -----

    @mcp.tool
    def validate_flow(flow: dict) -> dict[str, Any]:
        """Valida un FlowDef SIN ejecutarlo. Devuelve TODOS los errores y
        warnings de una sola pasada. Úsalo en bucle hasta valid=true antes de
        guardar el flow. `flow` es el objeto JSON completo del flow."""
        if not isinstance(flow, dict):
            return {"valid": False, "errors": ["El flow debe ser un objeto JSON"], "warnings": []}
        warnings = unknown_keys(flow)
        try:
            flow_def = load_flow(flow)
            errors = validate_all(flow_def, get_catalog())
        except Exception as e:
            return {"valid": False, "errors": [f"Error de parseo: {e}"], "warnings": warnings}
        return {"valid": not errors, "errors": errors, "warnings": warnings}

    # ----- CRUD de flows -----

    @mcp.tool
    def list_flows() -> list[dict[str, Any]]:
        """Lista los flows guardados con su interfaz pública (inputs/outputs)."""
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
        """Devuelve el FlowDef JSON completo de un flow guardado."""
        data = get_flow_dict(name)
        if data is None:
            return {"error": f"Flow '{name}' no encontrado"}
        return data

    @mcp.tool
    def create_flow(flow: dict) -> dict[str, Any]:
        """Crea y guarda un flow nuevo. Valida primero con validate_flow.
        Falla si ya existe un flow con ese nombre (usa update_flow para editar)."""
        if not isinstance(flow, dict):
            return {"error": "El flow debe ser un objeto JSON"}
        try:
            flow_def = load_flow(flow)
        except Exception as e:
            return {"error": f"FlowDef inválido: {e}"}
        if get_flow_dict(flow_def.name) is not None:
            return {"error": f"Ya existe un flow con el nombre '{flow_def.name}'"}
        save_flow(flow_def)
        return flow_to_dict(flow_def)

    @mcp.tool
    def update_flow(name: str, flow: dict) -> dict[str, Any]:
        """Actualiza (o crea) el flow `name` con el FlowDef dado."""
        if not isinstance(flow, dict):
            return {"error": "El flow debe ser un objeto JSON"}
        if "name" not in flow:
            flow = {**flow, "name": name}
        if flow.get("name") != name:
            return {"error": f"El nombre del body ('{flow.get('name')}') no coincide con '{name}'"}
        try:
            flow_def = load_flow(flow)
        except Exception as e:
            return {"error": f"FlowDef inválido: {e}"}
        save_flow(flow_def)
        return flow_to_dict(flow_def)

    @mcp.tool
    def delete_flow(name: str) -> dict[str, Any]:
        """Elimina un flow guardado."""
        ok = _delete_flow(name)
        return {"deleted": ok, "flow": name}

    @mcp.tool
    def flow_catalog(name: str) -> dict[str, Any]:
        """Catálogo resuelto de un flow: cada nodo con sus pins REALES en este
        contexto, incluyendo los dinámicos (outputs de OnStart = inputs del flow,
        ramas branch_N de Parallel, etc.). Úsalo para saber exactamente qué cablear."""
        from rayflow.build.validator import flatten, _with_dynamic_pins
        from rayflow.editor.routes import _pin_spec

        data = get_flow_dict(name)
        if data is None:
            return {"error": f"Flow '{name}' no encontrado"}
        catalog = get_catalog()
        try:
            flat = flatten(load_flow(data), catalog)
        except Exception as e:
            return {"error": f"No se pudo aplanar el flow: {e}"}
        nodes_out = []
        for nd in flat.nodes:
            entry = catalog.get(nd.type)
            if entry is None:
                nodes_out.append({"id": nd.id, "type": nd.type, "error": "tipo desconocido"})
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

    # ----- Ejecución / verificación -----

    @mcp.tool
    async def run_flow(name: str, inputs: dict | None = None) -> dict[str, Any]:
        """Ejecuta un flow guardado (cargándolo si hace falta) y devuelve sus
        outputs. `inputs` mapea cada input declarado del flow a su valor."""
        from rayflow.api import execute_async, load as load_api, is_flow_loaded

        if get_flow_dict(name) is None:
            return {"error": f"Flow '{name}' no encontrado"}
        data = get_flow_dict(name)
        if not is_flow_loaded(name):
            try:
                load_api(data)
            except Exception as e:
                return {"error": f"Error cargando el flow: {e}"}
        result: dict[str, Any] = {}
        async for evt in execute_async(name, inputs or {}):
            if evt.get("event") == "flow_done":
                result = evt.get("result", {}) or {}
            elif evt.get("event") == "flow_error":
                return {"error": evt.get("error", "Error desconocido")}
        return {"outputs": result}

    @mcp.tool
    async def test_flow(
        name: str, inputs: dict | None = None, expected_outputs: dict | None = None
    ) -> dict[str, Any]:
        """Ejecuta un flow y compara sus outputs con expected_outputs. Úsalo para
        verificar que el flow HACE lo que se pidió (no solo que es válido).
        Devuelve passed, actual, expected y los mismatches."""
        from rayflow.api import execute_async, load as load_api, is_flow_loaded

        data = get_flow_dict(name)
        if data is None:
            return {"error": f"Flow '{name}' no encontrado"}
        if not is_flow_loaded(name):
            try:
                load_api(data)
            except Exception as e:
                return {"error": f"Error cargando el flow: {e}"}
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

    # ----- Ejemplos -----

    def _examples_dir() -> Path:
        return Path(__file__).parent.parent / "editor" / "examples"

    @mcp.tool
    def list_examples() -> list[dict[str, Any]]:
        """Lista los flows de ejemplo incluidos (plantillas few-shot)."""
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
        """Devuelve el JSON completo de un flow de ejemplo (úsalo como plantilla)."""
        path = _examples_dir() / f"{name}.json"
        if not path.exists():
            return {"error": f"Ejemplo '{name}' no encontrado"}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            return {"error": str(e)}

    return mcp
