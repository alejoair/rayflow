"""Endpoints del editor visual: catálogo, CRUD de flows, validación."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response

from rayflow.build.validator import BuildError, build
from rayflow.nodes.registry import get_catalog
from rayflow.schema.loader import load_flow
from rayflow.types import PRIMITIVES, compatible

from .storage import delete_flow, get_flow_dict, list_flows, save_flow

router = APIRouter(prefix="/editor", tags=["editor"])


# ---------------------------------------------------------------------------
# Catálogo de nodos
# ---------------------------------------------------------------------------

def _pin_spec(p) -> dict[str, Any]:
    from rayflow.nodes.decorators import _MISSING
    d: dict[str, Any] = {"name": p.name, "kind": p.kind, "type": p.type or "Any", "required": p.required}
    if p.default is not _MISSING:
        d["default"] = p.default
    return d


def _node_spec(node_type: str, meta) -> dict[str, Any]:
    if meta.is_parallel:
        decorator = "parallel_node"
    elif meta.is_engine_node:
        decorator = "engine_node"
    else:
        decorator = "ray_node"

    return {
        "type": node_type,
        "decorator": decorator,
        "has_exec_in": meta.has_exec_in,
        "has_exec_out": meta.has_exec_out,
        "is_exec_node": meta.is_exec_node,
        "is_parallel": meta.is_parallel,
        "inputs": [_pin_spec(p) for p in meta.inputs],
        "outputs": [{"name": p.name, "kind": p.kind, "type": p.type or "Any"} for p in meta.outputs],
        "exec_outputs": meta.exec_outputs,
    }


@router.get("/info")
async def editor_info() -> dict[str, Any]:
    """Información del workspace activo: cwd y versión."""
    import os
    return {"cwd": os.getcwd()}


@router.get("/nodes")
async def list_nodes() -> list[dict[str, Any]]:
    """Devuelve el catálogo completo de tipos de nodo con sus pines."""
    catalog = get_catalog()
    return [_node_spec(name, meta) for name, _cls, meta in catalog]


@router.get("/nodes/{node_type}")
async def get_node(node_type: str) -> dict[str, Any]:
    """Devuelve la spec de un tipo de nodo específico."""
    catalog = get_catalog()
    entry = catalog.get(node_type)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Tipo de nodo '{node_type}' no encontrado")
    _cls, meta = entry
    return _node_spec(node_type, meta)


@router.get("/types")
async def get_types() -> dict[str, Any]:
    """Tipos canónicos disponibles y reglas de compatibilidad."""
    return {
        "primitives": sorted(PRIMITIVES),
        "generics": [
            {"base": "list", "example": "list[str]", "description": "list[T]"},
            {"base": "dict", "example": "dict[str, Any]", "description": "dict[str, V]"},
        ],
        "notes": [
            "Compatibilidad estricta: mismo tipo o uno de los dos es Any",
            "int y float son incompatibles — usar ToInt / ToFloat para castear",
        ],
    }


@router.post("/type-check")
async def type_check(body: dict = Body(...)) -> dict[str, Any]:
    """Comprueba si from_type puede conectarse a to_type.

    Body: {"from_type": "int", "to_type": "str"}
    """
    from_type = body.get("from_type")
    to_type = body.get("to_type")
    if from_type is None or to_type is None:
        raise HTTPException(status_code=400, detail="Se requieren 'from_type' y 'to_type'")
    try:
        result = compatible(to_type, from_type)  # compatible(consumer, producer)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"compatible": result, "from_type": from_type, "to_type": to_type}


# ---------------------------------------------------------------------------
# Validación de flows
# ---------------------------------------------------------------------------

@router.post("/validate")
async def validate_flow(flow_data: Any = Body(...)) -> dict[str, Any]:
    """Valida un FlowDef sin ejecutarlo. Devuelve errores de build si los hay."""
    if not isinstance(flow_data, dict):
        raise HTTPException(status_code=400, detail="Body debe ser un objeto JSON de FlowDef")
    try:
        flow_def = load_flow(flow_data)
        catalog = get_catalog()
        build(flow_def, catalog)
        return {"valid": True, "errors": []}
    except BuildError as e:
        return {"valid": False, "errors": [str(e)]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error de parseo: {e}")


# ---------------------------------------------------------------------------
# CRUD de flows
# ---------------------------------------------------------------------------

@router.get("/flows")
async def list_editor_flows() -> dict[str, Any]:
    """Lista todos los flows en el directorio flows/."""
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
    """Lista todos los flows actualmente cargados en Ray con su interfaz pública."""
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
    """Devuelve el FlowDef completo de un flow por nombre."""
    data = get_flow_dict(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Flow '{name}' no encontrado")
    return data


@router.post("/flows", status_code=201)
async def create_flow(flow_data: Any = Body(...)) -> dict[str, Any]:
    """Crea un flow nuevo y lo guarda en flows/{name}.json."""
    if not isinstance(flow_data, dict):
        raise HTTPException(status_code=400, detail="Body debe ser un objeto JSON de FlowDef")
    try:
        flow_def = load_flow(flow_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"FlowDef inválido: {e}")

    if get_flow_dict(flow_def.name) is not None:
        raise HTTPException(status_code=409, detail=f"Ya existe un flow con el nombre '{flow_def.name}'")

    save_flow(flow_def)
    from .storage import flow_to_dict
    return flow_to_dict(flow_def)


@router.put("/flows/{name}")
async def update_flow(name: str, flow_data: Any = Body(...)) -> dict[str, Any]:
    """Actualiza un flow existente. Crea el archivo si no existe."""
    if not isinstance(flow_data, dict):
        raise HTTPException(status_code=400, detail="Body debe ser un objeto JSON de FlowDef")

    # Permite que el frontend omita el nombre en el body y se tome del path
    if "name" not in flow_data:
        flow_data = {**flow_data, "name": name}

    if flow_data.get("name") != name:
        raise HTTPException(
            status_code=400,
            detail=f"El nombre del body ('{flow_data['name']}') no coincide con la ruta ('{name}')"
        )

    try:
        flow_def = load_flow(flow_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"FlowDef inválido: {e}")

    save_flow(flow_def)
    from .storage import flow_to_dict
    return flow_to_dict(flow_def)


@router.delete("/flows/{name}", status_code=204)
async def delete_editor_flow(name: str) -> Response:
    """Elimina un flow del directorio flows/."""
    if not delete_flow(name):
        raise HTTPException(status_code=404, detail=f"Flow '{name}' no encontrado")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Ejecución desde el editor
# ---------------------------------------------------------------------------

@router.post("/flows/{name}/load", status_code=200)
async def load_editor_flow(name: str) -> dict[str, Any]:
    """Carga un flow en Ray: inicializa actores y GraphState persistente.

    Idempotente — si ya está cargado lo recarga (resetea el estado).
    """
    import asyncio
    from functools import partial
    from rayflow.api import load as load_flow_api

    data = get_flow_dict(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Flow '{name}' no encontrado")
    try:
        loop = asyncio.get_event_loop()
        graph_id = await loop.run_in_executor(None, partial(load_flow_api, data))
        return {"graph_id": graph_id, "flow": name, "loaded": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cargando el flow: {e}")


@router.delete("/flows/{name}/load", status_code=200)
async def unload_editor_flow(name: str) -> dict[str, Any]:
    """Descarga un flow de Ray, destruyendo sus actores y GraphState."""
    from rayflow.api import unload as unload_flow_api
    unload_flow_api(name)
    return {"flow": name, "loaded": False}


@router.get("/flows/{name}/loaded")
async def flow_loaded_status(name: str) -> dict[str, Any]:
    """Devuelve si el flow está actualmente cargado en Ray."""
    from rayflow.api import is_flow_loaded
    return {"flow": name, "loaded": is_flow_loaded(name)}


@router.post("/flows/{name}/run")
async def run_editor_flow(name: str, inputs: Any = Body(default=None)):
    """Ejecuta un flow (cargándolo si es necesario) con streaming SSE.

    Devuelve un stream de eventos: node_start, node_done, edge_fire, flow_done, flow_error.
    """
    import asyncio
    import json
    from functools import partial
    from fastapi.responses import StreamingResponse
    from rayflow.api import execute_async, load as load_flow_api, is_flow_loaded  # noqa: F401

    if inputs is None:
        inputs = {}
    if not isinstance(inputs, dict):
        raise HTTPException(status_code=400, detail="Body debe ser un objeto JSON de inputs")

    data = get_flow_dict(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Flow '{name}' no encontrado")

    # Cargar si no está cargado
    if not is_flow_loaded(name):
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, partial(load_flow_api, data))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error cargando el flow: {e}")

    async def event_generator():
        try:
            async for evt in execute_async(name, inputs):
                yield f"data: {json.dumps(evt)}\n\n"
        except Exception as e:
            import json as _json
            yield f"data: {_json.dumps({'event': 'flow_error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/flows/{name}/run/{run_id}/stream")
async def reconnect_flow_run(name: str, run_id: str):
    """Reconecta a un run SSE activo sin relanzar la ejecución.

    Útil cuando el cliente pierde la conexión mientras el flow todavía corre.
    Devuelve los eventos pendientes desde el momento de reconexión.
    """
    import json
    from fastapi.responses import StreamingResponse
    from rayflow.api import reconnect_async, is_flow_loaded

    if not is_flow_loaded(name):
        raise HTTPException(status_code=404, detail=f"Flow '{name}' no está cargado")

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
# Eventos — suscripción y desuscripción
# ---------------------------------------------------------------------------

@router.post("/flows/{name}/serve-events", status_code=201)
async def serve_flow_events(name: str) -> dict[str, Any]:
    """Registra un flow como oyente de eventos (serve_events).

    El flow debe tener un nodo OnEvent con el event_name configurado, y
    declarar ese evento en su campo `events`. Devuelve el graph_id asignado;
    úsalo para desuscribir después.
    """
    from rayflow.api import serve_events

    data = get_flow_dict(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Flow '{name}' no encontrado")
    try:
        graph_id = serve_events(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error registrando el flow: {e}")
    return {"graph_id": graph_id, "flow": name}


@router.delete("/flows/{name}/serve-events/{graph_id}", status_code=204)
async def stop_flow_events(name: str, graph_id: str) -> Response:
    """Desuscribe un flow residente del bus de eventos."""
    from rayflow.api import stop

    data = get_flow_dict(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Flow '{name}' no encontrado")
    try:
        flow_def = load_flow(data)
        stop(graph_id, flow_def.events)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error desuscribiendo el flow: {e}")
    return Response(status_code=204)
