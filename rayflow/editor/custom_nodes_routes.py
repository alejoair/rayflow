"""Endpoints CRUD para nodos custom: leer/crear/editar/eliminar archivos .py
y recargar el catálogo en caliente sin reiniciar el servidor."""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response

from rayflow.nodes.registry import get_catalog, reset_catalog
from rayflow.workspace import custom_nodes_path

router = APIRouter(prefix="/editor/custom-nodes", tags=["custom-nodes"])

_BUILTIN_TYPES = frozenset([
    'OnStart', 'FlowInput', 'FlowOutput', 'Branch', 'Sequence', 'Parallel',
    'ForEach', 'Map', 'Get', 'Set', 'CallFlow', 'OnEvent', 'EmitEvent',
    'Add', 'GreaterThan', 'LessThan', 'GreaterThanOrEqual', 'LessThanOrEqual',
    'Equal', 'NotEqual', 'Not', 'And', 'Or', 'ToInt', 'ToFloat', 'ToStr', 'ToBool',
    'While',
])

NODE_TEMPLATE = '''\
from rayflow.nodes.decorators import engine_node, ray_node, ExecContext, ExecInput, ExecOutput, Input, Output


@engine_node
class {name}:
    exec_in = ExecInput()
    # value = Input("str", default="")
    # result = Output("str")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext) -> None:
        await ctx.fire("exec_out")
'''


def _node_file(name: str) -> Path:
    return custom_nodes_path() / f"{name}.py"


def _ensure_package() -> None:
    """Garantiza que custom_nodes/ existe como paquete Python."""
    cn = custom_nodes_path()
    cn.mkdir(parents=True, exist_ok=True)
    init = cn / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")


def _validate_syntax(code: str) -> str | None:
    """Devuelve mensaje de error o None si la sintaxis es válida."""
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        return f"SyntaxError en línea {e.lineno}: {e.msg}"


def _reload_catalog() -> dict[str, Any]:
    """Descarta el catálogo singleton y lo reconstruye desde disco."""
    # Eliminar módulos custom_nodes.* cacheados para forzar reimportación
    to_remove = [k for k in sys.modules if k.startswith("custom_nodes")]
    for k in to_remove:
        del sys.modules[k]

    reset_catalog()
    catalog = get_catalog()

    custom_names = [
        name for name, _cls, _meta in catalog
        if name not in _BUILTIN_TYPES
    ]
    return {"reloaded": True, "custom_nodes": custom_names}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_custom_nodes() -> list[dict[str, Any]]:
    """Lista los archivos .py de custom_nodes/ con nombre y tamaño."""
    cn = custom_nodes_path()
    if not cn.exists():
        return []
    files = []
    for p in sorted(cn.glob("*.py")):
        if p.name == "__init__.py" or p.name.startswith("_"):
            continue
        files.append({
            "name": p.stem,
            "filename": p.name,
            "size": p.stat().st_size,
        })
    return files


@router.get("/{name}/source")
async def get_custom_node_source(name: str) -> dict[str, Any]:
    """Devuelve el código fuente de un nodo custom."""
    path = _node_file(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Nodo custom '{name}' no encontrado")
    return {"name": name, "source": path.read_text(encoding="utf-8")}


@router.post("", status_code=201)
async def create_custom_node(body: dict = Body(...)) -> dict[str, Any]:
    """Crea un nuevo archivo de nodo custom.

    Body: { "name": "MiNodo", "source": "..." (opcional) }
    Si no se provee source, se usa la plantilla por defecto.
    """
    name: str = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="El campo 'name' es requerido")
    if not name.isidentifier():
        raise HTTPException(status_code=422, detail=f"'{name}' no es un identificador Python válido")

    _ensure_package()
    path = _node_file(name)
    if path.exists():
        raise HTTPException(status_code=409, detail=f"Ya existe un nodo custom llamado '{name}'")

    source: str = body.get("source") or NODE_TEMPLATE.format(name=name)

    err = _validate_syntax(source)
    if err:
        raise HTTPException(status_code=422, detail=err)

    path.write_text(source, encoding="utf-8")
    reload_result = _reload_catalog()
    return {"name": name, "created": True, **reload_result}


@router.put("/{name}/source")
async def update_custom_node_source(name: str, body: dict = Body(...)) -> dict[str, Any]:
    """Guarda el código fuente editado y recarga el catálogo."""
    path = _node_file(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Nodo custom '{name}' no encontrado")

    source: str = body.get("source", "")
    if not source.strip():
        raise HTTPException(status_code=422, detail="El campo 'source' no puede estar vacío")

    err = _validate_syntax(source)
    if err:
        raise HTTPException(status_code=422, detail=err)

    path.write_text(source, encoding="utf-8")
    reload_result = _reload_catalog()
    return {"name": name, "saved": True, **reload_result}


@router.delete("/{name}", status_code=204)
async def delete_custom_node(name: str) -> Response:
    """Elimina el archivo .py y recarga el catálogo."""
    path = _node_file(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Nodo custom '{name}' no encontrado")
    path.unlink()
    _reload_catalog()
    return Response(status_code=204)


@router.post("/reload")
async def reload_custom_nodes() -> dict[str, Any]:
    """Recarga todos los nodos custom desde disco sin reiniciar el servidor."""
    return _reload_catalog()
