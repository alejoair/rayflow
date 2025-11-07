"""Flow-related API endpoints."""

from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from pydantic import BaseModel

# Import orchestrator modules
from rayflow.orchestrator.validator import FlowValidator
from rayflow.orchestrator.node_loader import NodeLoader


class FlowValidationRequest(BaseModel):
    """Request model for flow validation."""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class FlowValidationResponse(BaseModel):
    """Response model for flow validation."""
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    nodes_validated: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


def validate_flow(request: FlowValidationRequest, working_dir: Path) -> FlowValidationResponse:
    """
    Validate a flow without executing it.

    This endpoint validates:
    - Flow structure (single START node, reachable nodes, no cycles)
    - Node type compatibility
    - That all referenced node classes exist and can be loaded

    Args:
        request: Flow data with nodes and edges
        working_dir: Working directory for resolving custom nodes

    Returns:
        FlowValidationResponse with validation results
    """
    try:
        # Convert request to flow_data format expected by validator
        flow_data = {
            "nodes": request.nodes,
            "edges": request.edges
        }

        # COMPREHENSIVE DEBUG: Log everything received from frontend
        print(f"[DEBUG] BACKEND RECEIVED REQUEST:")
        print(f"  Summary: {len(request.nodes)} nodes, {len(request.edges)} edges")

        print(f"[DEBUG] DETAILED NODE DATA:")
        for i, node in enumerate(request.nodes):
            print(f"  Node {i+1}:")
            print(f"    - id: '{node['id']}'")
            print(f"    - type: '{node['type']}'")
            print(f"    - data: {node['data']}")
            print(f"    - position: {node.get('position', 'N/A')}")

        print(f"[DEBUG] DETAILED EDGE DATA:")
        for i, edge in enumerate(request.edges):
            print(f"  Edge {i+1}:")
            print(f"    - id: '{edge['id']}'")
            print(f"    - source: '{edge['source']}' -> target: '{edge['target']}'")
            print(f"    - handles: '{edge.get('sourceHandle', 'N/A')}' -> '{edge.get('targetHandle', 'N/A')}'")

        # 1. Validate flow structure
        validator = FlowValidator()
        valid, errors, warnings = validator.validate(flow_data)

        if not valid:
            response = FlowValidationResponse(
                valid=False,
                errors=errors,
                warnings=warnings,
                nodes_validated=0
            )
            print(f"[DEBUG] BACKEND SENDING (validation failed): {response.dict()}")
            return response

        # 2. Validate that all node classes exist and can be loaded
        node_loader = NodeLoader()
        try:
            metadata_map = node_loader.load_all_metadata(flow_data)

            response = FlowValidationResponse(
                valid=True,
                errors=[],
                warnings=warnings,
                nodes_validated=len(metadata_map),
                metadata=metadata_map
            )
            print(f"[DEBUG] BACKEND SENDING (success): {response.dict()}")
            return response

        except Exception as e:
            # If node loading fails, it's a validation error
            error_msg = f"Node loading error: {str(e)}"
            response = FlowValidationResponse(
                valid=False,
                errors=[error_msg],
                warnings=warnings,
                nodes_validated=0
            )
            print(f"[DEBUG] BACKEND SENDING (node loading failed): {response.dict()}")
            return response

    except Exception as e:
        # Unexpected server error
        raise HTTPException(
            status_code=500,
            detail=f"Flow validation failed: {str(e)}"
        )