"""
Custom exceptions for the RayFlow orchestrator
"""


class ValidationError(Exception):
    """Flow structure validation failed"""
    pass


class GraphBuildError(Exception):
    """Failed to build execution graph"""
    pass


class NodeLoadError(Exception):
    """Failed to load node class"""
    pass


class DataNotAvailableError(Exception):
    """Required input data not available"""
    pass


class NodeExecutionError(Exception):
    """Node execution failed"""

    def __init__(self, node_id: str, original_error: Exception):
        self.node_id = node_id
        self.original_error = original_error
        super().__init__(f"Node {node_id} failed: {original_error}")
