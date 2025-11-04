import os
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter()


class NodeFile(BaseModel):
    name: str
    path: str
    type: str  # "builtin" or "user"


def get_working_directory() -> Path:
    """Get the working directory where rayflow was called"""
    cwd = os.environ.get("RAYFLOW_CWD")
    if cwd:
        return Path(cwd)
    return Path.cwd()


@router.get("/nodes", response_model=List[NodeFile])
def list_nodes():
    """List all built-in and user nodes"""
    nodes = []

    # 1. Built-in nodes from the installed package
    builtin_nodes_dir = Path(__file__).parent.parent / "nodes"
    if builtin_nodes_dir.exists():
        for category_dir in builtin_nodes_dir.iterdir():
            if category_dir.is_dir() and category_dir.name != "__pycache__":
                for py_file in category_dir.glob("*.py"):
                    if py_file.name != "__init__.py":
                        nodes.append(NodeFile(
                            name=f"{category_dir.name}/{py_file.stem}",
                            path=str(py_file),
                            type="builtin"
                        ))

    # 2. User nodes from the working directory
    cwd = get_working_directory()
    user_nodes_dir = cwd / "nodes"
    if user_nodes_dir.exists():
        for py_file in user_nodes_dir.glob("*.py"):
            if py_file.name != "__init__.py":
                nodes.append(NodeFile(
                    name=py_file.stem,
                    path=str(py_file.relative_to(cwd)),
                    type="user"
                ))
    else:
        # Create nodes directory if it doesn't exist
        user_nodes_dir.mkdir(parents=True, exist_ok=True)

    return nodes
