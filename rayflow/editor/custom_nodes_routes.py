"""CRUD endpoints for custom nodes: read/create/edit/delete .py files
and hot-reload the catalog without restarting the server."""
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
    """Ensures custom_nodes/ exists as a Python package."""
    cn = custom_nodes_path()
    cn.mkdir(parents=True, exist_ok=True)
    init = cn / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")


def _validate_syntax(code: str) -> str | None:
    """Returns an error message, or None if the syntax is valid."""
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        return f"SyntaxError on line {e.lineno}: {e.msg}"


def _reload_catalog() -> dict[str, Any]:
    """Discards the singleton catalog and rebuilds it from disk."""
    # Remove cached custom_nodes.* modules to force re-import.
    to_remove = [k for k in sys.modules if k.startswith("custom_nodes")]
    for k in to_remove:
        del sys.modules[k]

    reset_catalog()
    catalog = get_catalog()

    custom_names = [
        name for name, _cls, _meta in catalog
        if name not in _BUILTIN_TYPES
    ]
    return {
        "reloaded": True,
        "custom_nodes": custom_names,
        "errors": catalog.load_errors,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_custom_nodes() -> list[dict[str, Any]]:
    """Lists the .py files in custom_nodes/ with name and size."""
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
    """Returns the source code of a custom node."""
    path = _node_file(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Custom node '{name}' not found")
    return {"name": name, "source": path.read_text(encoding="utf-8")}


@router.post("", status_code=201)
async def create_custom_node(body: dict = Body(...)) -> dict[str, Any]:
    """Creates a new custom node file.

    Body: { "name": "MyNode", "source": "..." (optional) }
    If source isn't provided, the default template is used.

    The response includes "registered": whether `name` shows up in the
    reloaded catalog after writing the file to disk. "created" only means
    the file was written successfully to disk — it says nothing about
    whether the module loaded and its class got registered in the node
    catalog. A file can be "created" but not "registered" if, e.g., the
    module raises on import (missing decorator requirement, bad pin
    config, etc.).

    The response also includes "error": the real exception message from
    NodeCatalog.load_errors (rayflow/nodes/loader.py) when the module
    failed to import or register, or None otherwise. load_errors is keyed
    by `path.stem` (the filename without ".py"), which is exactly `name`
    here since `_node_file()` writes the file as f"{name}.py" — so
    `reload_result["errors"].get(name)` is a direct, untransformed lookup.

    Known remaining gap: "registered" is derived by checking
    `name in reload_result["custom_nodes"]`, and the catalog is keyed by
    `cls.__name__` — not necessarily the same string as the file/API `name`
    used to create it. A custom node file that loads without error but
    declares a class with a different name than the one passed here will
    show "registered": false with "error": None (the import genuinely
    succeeded, just under another name) — a false negative that "error"
    does not resolve, since there was no exception to record.
    """
    name: str = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="The 'name' field is required")
    if not name.isidentifier():
        raise HTTPException(status_code=422, detail=f"'{name}' is not a valid Python identifier")

    _ensure_package()
    path = _node_file(name)
    if path.exists():
        raise HTTPException(status_code=409, detail=f"A custom node named '{name}' already exists")

    source: str = body.get("source") or NODE_TEMPLATE.format(name=name)

    err = _validate_syntax(source)
    if err:
        raise HTTPException(status_code=422, detail=err)

    path.write_text(source, encoding="utf-8")
    reload_result = _reload_catalog()
    return {
        "name": name,
        "created": True,
        "registered": name in reload_result["custom_nodes"],
        "error": reload_result["errors"].get(name),
        **reload_result,
    }


@router.put("/{name}/source")
async def update_custom_node_source(name: str, body: dict = Body(...)) -> dict[str, Any]:
    """Saves the edited source code and reloads the catalog.

    The response includes "registered": whether `name` shows up in the
    reloaded catalog after writing the file to disk. "saved" only means
    the file was written successfully to disk — it says nothing about
    whether the module loaded and its class got registered in the node
    catalog. A file can be "saved" but not "registered" if the edited
    source raises on import (e.g. a decoration error).

    The response also includes "error": the real exception message from
    NodeCatalog.load_errors (rayflow/nodes/loader.py) when the module
    failed to import or register, or None otherwise. load_errors is keyed
    by `path.stem` (the filename without ".py"), which is exactly `name`
    here since `_node_file()` reads/writes the file as f"{name}.py" — so
    `reload_result["errors"].get(name)` is a direct, untransformed lookup.

    Known remaining gap (same as create_custom_node above): "registered"
    is derived from `name in reload_result["custom_nodes"]`, and the
    catalog is keyed by `cls.__name__`, not necessarily the file/API
    `name`. A node whose class got renamed in the edited source (but still
    loads fine) will report "registered": false with "error": None here —
    a false negative that "error" does not resolve, since there was no
    exception: the module imported successfully, just under another name.
    """
    path = _node_file(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Custom node '{name}' not found")

    source: str = body.get("source", "")
    if not source.strip():
        raise HTTPException(status_code=422, detail="The 'source' field cannot be empty")

    err = _validate_syntax(source)
    if err:
        raise HTTPException(status_code=422, detail=err)

    path.write_text(source, encoding="utf-8")
    reload_result = _reload_catalog()
    return {
        "name": name,
        "saved": True,
        "registered": name in reload_result["custom_nodes"],
        "error": reload_result["errors"].get(name),
        **reload_result,
    }


@router.delete("/{name}", status_code=204)
async def delete_custom_node(name: str) -> Response:
    """Deletes the .py file and reloads the catalog."""
    path = _node_file(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Custom node '{name}' not found")
    path.unlink()
    _reload_catalog()
    return Response(status_code=204)


@router.post("/reload")
async def reload_custom_nodes() -> dict[str, Any]:
    """Reloads every custom node from disk without restarting the server."""
    return _reload_catalog()
