"""API routes for RayFlow server."""

import os
from pathlib import Path
from fastapi import APIRouter, Depends
from .nodes import router as nodes_router, NodeSourceUpdateRequest
from .variables import router as variables_router, CreateVariableRequest
from .flows import FlowValidationRequest


# Create main router that combines all sub-routers
router = APIRouter()


def get_working_directory() -> Path:
    """Get the working directory where rayflow was called."""
    cwd = os.environ.get("RAYFLOW_CWD")
    if cwd:
        return Path(cwd)
    return Path.cwd()


# Include sub-routers with dependency injection for working_dir
@router.get("/nodes")
def list_nodes_endpoint(working_dir: Path = Depends(get_working_directory)):
    """List all built-in and user nodes with metadata."""
    from .nodes import list_nodes
    return list_nodes(working_dir)


@router.get("/variables")
def list_variables_endpoint(working_dir: Path = Depends(get_working_directory)):
    """List all variables from the variables directory with metadata."""
    from .variables import list_variables
    return list_variables(working_dir)


@router.post("/variables/create")
def create_variable_endpoint(
    request: CreateVariableRequest,
    working_dir: Path = Depends(get_working_directory)
):
    """Create a new variable file in the variables directory."""
    from .variables import create_variable
    return create_variable(request, working_dir)


@router.get("/nodes/source")
def get_node_source_endpoint(
    file_path: str,
    working_dir: Path = Depends(get_working_directory)
):
    """Get the source code of a node file."""
    from .nodes import get_node_source
    return get_node_source(file_path, working_dir)


@router.post("/nodes/source")
def update_node_source_endpoint(
    request: NodeSourceUpdateRequest,
    working_dir: Path = Depends(get_working_directory)
):
    """Update the source code of a custom (user) node file."""
    from .nodes import update_node_source
    return update_node_source(request, working_dir)


@router.post("/flows/validate")
def validate_flow_endpoint(
    request: FlowValidationRequest,
    working_dir: Path = Depends(get_working_directory)
):
    """Validate a flow without executing it."""
    from .flows import validate_flow
    return validate_flow(request, working_dir)


__all__ = ["router", "get_working_directory"]
