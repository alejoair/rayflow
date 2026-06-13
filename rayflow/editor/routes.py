"""Endpoints del editor visual: catálogo, CRUD de flows, validación."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

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
async def delete_editor_flow(name: str) -> None:
    """Elimina un flow del directorio flows/."""
    if not delete_flow(name):
        raise HTTPException(status_code=404, detail=f"Flow '{name}' no encontrado")


# ---------------------------------------------------------------------------
# Ejecución desde el editor
# ---------------------------------------------------------------------------

@router.post("/flows/{name}/run")
async def run_editor_flow(name: str, inputs: Any = Body(default=None)) -> dict[str, Any]:
    """Ejecuta un flow con los inputs dados.

    A diferencia de POST /flows/{name}/run (que usa run_async → worker Ray),
    aquí ejecutamos con run() en un thread pool del driver. Esto garantiza que
    los custom nodes cargados vía --nodes-dir (load_directory) estén disponibles,
    ya que el catálogo singleton del driver ya los tiene registrados.

    Limitación: @ray_node custom nodes siguen requiriendo custom_nodes/ para
    ser distribuibles a los workers Ray (restricción de serialización).
    """
    import asyncio
    from functools import partial
    from rayflow.api import run as run_sync

    data = get_flow_dict(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Flow '{name}' no encontrado")

    if inputs is None:
        inputs = {}
    if not isinstance(inputs, dict):
        raise HTTPException(status_code=400, detail="Body debe ser un objeto JSON de inputs")

    try:
        # run() llama asyncio.run() internamente — no puede usarse directamente
        # desde una corrutina. run_in_executor lo ejecuta en un thread del pool
        # donde no hay event loop activo, así asyncio.run() funciona correctamente.
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(run_sync, data, **inputs))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando el flow: {e}")


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
async def stop_flow_events(name: str, graph_id: str) -> None:
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


# ---------------------------------------------------------------------------
# Custom nodes — edición de archivos .py
# ---------------------------------------------------------------------------

def _safe_filename(filename: str) -> str:
    """Valida que el nombre de archivo sea seguro (solo .py, sin path traversal)."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    if not filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos .py")
    return filename


@router.get("/custom-nodes/files")
async def list_custom_node_files() -> dict[str, Any]:
    """Lista los archivos .py de custom_nodes/ (excluye __init__ y privados)."""
    from rayflow.workspace import custom_nodes_path
    cn = custom_nodes_path()
    if not cn.exists():
        return {"files": []}
    files = [
        {"name": p.name, "size": p.stat().st_size}
        for p in sorted(cn.glob("*.py"))
        if p.name != "__init__.py" and not p.name.startswith("_")
    ]
    return {"files": files}


@router.get("/custom-nodes/files/{filename}")
async def get_custom_node_file(filename: str) -> dict[str, Any]:
    """Devuelve el contenido de un archivo .py de custom_nodes/."""
    from rayflow.workspace import custom_nodes_path
    _safe_filename(filename)
    p = custom_nodes_path() / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Archivo '{filename}' no encontrado")
    return {"filename": filename, "content": p.read_text(encoding="utf-8")}


@router.put("/custom-nodes/files/{filename}", status_code=200)
async def save_custom_node_file(filename: str, body: dict = Body(...)) -> dict[str, Any]:
    """Crea o actualiza un archivo .py en custom_nodes/."""
    from rayflow.workspace import custom_nodes_path
    _safe_filename(filename)
    content = body.get("content", "")
    cn = custom_nodes_path()
    cn.mkdir(parents=True, exist_ok=True)
    init = cn / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")
    (cn / filename).write_text(content, encoding="utf-8")
    return {"filename": filename, "saved": True}


@router.delete("/custom-nodes/files/{filename}", status_code=204)
async def delete_custom_node_file(filename: str) -> None:
    """Elimina un archivo .py de custom_nodes/."""
    from rayflow.workspace import custom_nodes_path
    _safe_filename(filename)
    p = custom_nodes_path() / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Archivo '{filename}' no encontrado")
    p.unlink()


@router.post("/custom-nodes/reload")
async def reload_custom_nodes() -> list[dict[str, Any]]:
    """Recarga el catálogo de nodos custom desde disco.

    Elimina del catálogo los nodos registrados desde custom_nodes/, borra sus
    módulos de sys.modules, y vuelve a importar el paquete. Devuelve el catálogo
    actualizado para que el frontend refresque la paleta.
    """
    import sys
    catalog = get_catalog()

    # Eliminar entradas custom del catálogo
    custom_keys = [
        name for name, (cls, _) in list(catalog._registry.items())
        if cls.__module__.startswith("custom_nodes")
    ]
    for key in custom_keys:
        del catalog._registry[key]

    # Limpiar sys.modules para forzar reimportación
    for mod_key in [k for k in list(sys.modules) if k.startswith("custom_nodes")]:
        del sys.modules[mod_key]

    # Reimportar
    catalog.load_custom_nodes_package()

    return [_node_spec(name, meta) for name, _cls, meta in catalog]
