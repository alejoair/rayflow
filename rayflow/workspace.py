"""Convención del working directory de Rayflow.

Donde se lanza rayflow es la carpeta de trabajo. Por convención contiene:

    <cwd>/
    ├── custom_nodes/     ← paquete de nodos custom (auto-descubierto y distribuido)
    │   └── __init__.py
    └── flows/            ← flows JSON, resueltos por nombre

`custom_nodes/` se distribuye a los workers Ray vía runtime_env (py_modules),
así los nodos custom funcionan aunque Ray ejecute en varias máquinas.
"""
from __future__ import annotations

from pathlib import Path

CUSTOM_NODES_DIR = "custom_nodes"
FLOWS_DIR = "flows"


def workspace_root() -> Path:
    """Raíz del workspace = directorio de trabajo actual."""
    return Path.cwd()


def custom_nodes_path() -> Path:
    return workspace_root() / CUSTOM_NODES_DIR


def flows_path() -> Path:
    return workspace_root() / FLOWS_DIR


def ensure_workspace() -> None:
    """Crea custom_nodes/ (con __init__.py) y flows/ si no existen.

    Convención sin fricción: un proyecto nuevo queda listo para usar nodos
    custom y flows sin configuración manual.
    """
    cn = custom_nodes_path()
    if not cn.exists():
        cn.mkdir(parents=True, exist_ok=True)
    init = cn / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")

    fl = flows_path()
    if not fl.exists():
        fl.mkdir(parents=True, exist_ok=True)


def runtime_env() -> dict | None:
    """runtime_env para ray.init: distribuye custom_nodes/ como py_module.

    Devuelve None si no hay nodos custom (solo el __init__.py o vacío), para no
    arrancar Ray con un runtime_env innecesario.
    """
    cn = custom_nodes_path()
    if not cn.exists():
        return None
    # ¿Hay algún .py de nodo además del __init__.py?
    has_nodes = any(
        p.suffix == ".py" and p.name != "__init__.py"
        for p in cn.iterdir()
    )
    if not has_nodes:
        return None
    return {"py_modules": [str(cn)]}


def resolve_flow(name_or_path: str) -> str:
    """Resuelve un flow por nombre o ruta.

    - Si es una ruta existente (.json), la devuelve tal cual.
    - Si es un nombre simple, busca flows/<name>.json en el workspace.
    """
    p = Path(name_or_path)
    if p.exists():
        return str(p)
    candidate = flows_path() / (name_or_path if name_or_path.endswith(".json")
                                else f"{name_or_path}.json")
    if candidate.exists():
        return str(candidate)
    raise FileNotFoundError(
        f"Flow '{name_or_path}' no encontrado (ni como ruta ni en {flows_path()})"
    )
