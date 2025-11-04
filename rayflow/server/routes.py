import os
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter()


class NodeFile(BaseModel):
    name: str
    path: str


def get_working_directory() -> Path:
    """Get the working directory where rayflow was called"""
    cwd = os.environ.get("RAYFLOW_CWD")
    if cwd:
        return Path(cwd)
    return Path.cwd()


@router.get("/nodes", response_model=List[NodeFile])
def list_nodes():
    """List all .py files in the nodes/ directory of the working directory"""

    cwd = get_working_directory()
    nodes_dir = cwd / "nodes"

    if not nodes_dir.exists():
        # Create nodes directory if it doesn't exist
        nodes_dir.mkdir(parents=True, exist_ok=True)
        return []

    nodes = []
    for py_file in nodes_dir.glob("*.py"):
        if py_file.name != "__init__.py":
            nodes.append(NodeFile(
                name=py_file.stem,
                path=str(py_file.relative_to(cwd))
            ))

    return nodes
