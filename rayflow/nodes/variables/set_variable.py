"""Set Variable Node - Stores values in global variable store"""

import ray
from rayflow import RayflowNode


@ray.remote
class SetVariableNode(RayflowNode):
    """Stores a value in the global variable store."""

    # Metadata for UI
    icon = "fa-upload"
    category = "variables"
    description = "Set a value in the global variable store"

    # Configuration
    VARIABLE_NAME = ""  # Name of variable to set

    # Type definitions
    inputs = {
        "value": "any"  # Input type depends on variable
    }

    outputs = {
        "success": "bool"  # Whether operation succeeded
    }

    # Execution flow
    exec_input = True
    exec_output = True

    def process(self, **inputs):
        """
        Store variable in global store

        Args:
            value: Value to store

        Returns:
            dict: {"success": bool}
        """
        variable_name = self.VARIABLE_NAME
        value = inputs.get("value")

        if not variable_name:
            raise ValueError("VARIABLE_NAME must be configured")

        try:
            # Get the global variable store from the actor
            store = self.get_variable_store()

            # Set the variable value
            success = ray.get(store.set_variable.remote(variable_name, value))

            return {"success": success}

        except Exception as e:
            raise RuntimeError(f"Failed to set variable '{variable_name}': {e}")

    def get_variable_store(self):
        """Get the variable store handle - to be set by ActorManager"""
        if not hasattr(self, '_variable_store'):
            raise RuntimeError("Variable store not available. This node must be used within the orchestrator.")
        return self._variable_store

    def set_variable_store(self, store_handle):
        """Set the variable store handle - called by ActorManager"""
        self._variable_store = store_handle