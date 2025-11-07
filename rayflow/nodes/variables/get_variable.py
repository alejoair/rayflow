"""Get Variable Node - Retrieves values from global variable store"""

import ray
from rayflow import RayflowNode


@ray.remote
class GetVariableNode(RayflowNode):
    """Retrieves a value from the global variable store."""

    # Metadata for UI
    icon = "fa-download"
    category = "variables"
    description = "Get a value from the global variable store"

    # Configuration
    VARIABLE_NAME = ""  # Name of variable to get

    # Type definitions - dynamic based on variable
    inputs = {}  # No inputs needed

    outputs = {
        "value": "any"  # Output type depends on variable
    }

    # Execution flow - Pure node (no side effects, executes when value needed)
    exec_input = False
    exec_output = False

    def process(self, **inputs):
        """
        Retrieve variable from global store

        Returns:
            dict: {"value": variable_value}
        """
        variable_name = self.VARIABLE_NAME

        if not variable_name:
            raise ValueError("VARIABLE_NAME must be configured")

        try:
            # Get the global variable store from the actor
            # The variable store handle will be passed during actor creation
            store = self.get_variable_store()

            # Get the variable value
            value = ray.get(store.get_variable.remote(variable_name))

            return {"value": value}

        except Exception as e:
            raise RuntimeError(f"Failed to get variable '{variable_name}': {e}")

    def get_variable_store(self):
        """Get the variable store handle - to be set by ActorManager"""
        if not hasattr(self, '_variable_store'):
            raise RuntimeError("Variable store not available. This node must be used within the orchestrator.")
        return self._variable_store

    def set_variable_store(self, store_handle):
        """Set the variable store handle - called by ActorManager"""
        self._variable_store = store_handle