"""Rayflow's working-directory convention.

Wherever rayflow is launched from is the working directory. By convention
it contains:

    <cwd>/
    ├── custom_nodes/     ← package of custom nodes (auto-discovered and distributed)
    │   └── __init__.py
    └── flows/            ← flow JSON files, resolved by name

`custom_nodes/` is distributed to Ray workers via runtime_env (py_modules),
so custom nodes work even when Ray runs across multiple machines.
"""
from __future__ import annotations

from pathlib import Path

CUSTOM_NODES_DIR = "custom_nodes"
FLOWS_DIR = "flows"


def workspace_root() -> Path:
    """Workspace root = the current working directory."""
    return Path.cwd()


def custom_nodes_path() -> Path:
    return workspace_root() / CUSTOM_NODES_DIR


def flows_path() -> Path:
    return workspace_root() / FLOWS_DIR


def ensure_workspace() -> None:
    """Creates custom_nodes/ (with __init__.py) and flows/ if they don't exist.

    Zero-friction convention: a new project is ready to use custom nodes and
    flows with no manual configuration.
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
    """runtime_env for ray.init: distributes custom_nodes/ as a py_module.

    Returns None if there are no custom nodes (just __init__.py or empty),
    to avoid starting Ray with an unnecessary runtime_env.
    """
    cn = custom_nodes_path()
    if not cn.exists():
        return None
    # Is there any node .py file besides __init__.py?
    has_nodes = any(
        p.suffix == ".py" and p.name != "__init__.py"
        for p in cn.iterdir()
    )
    if not has_nodes:
        return None
    return {"py_modules": [str(cn)]}


def resolve_flow(name_or_path: str) -> str:
    """Resolves a flow by name or path.

    - If it's an existing path (.json), returns it as-is.
    - If it's a plain name, looks up flows/<name>.json in the workspace.
    """
    p = Path(name_or_path)
    if p.exists():
        return str(p)
    candidate = flows_path() / (name_or_path if name_or_path.endswith(".json")
                                else f"{name_or_path}.json")
    if candidate.exists():
        return str(candidate)
    raise FileNotFoundError(
        f"Flow '{name_or_path}' not found (neither as a path nor in {flows_path()})"
    )
