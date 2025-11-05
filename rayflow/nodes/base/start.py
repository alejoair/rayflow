"""START node - Entry point for all RayFlow workflows."""

import ray
from rayflow import RayflowNode


@ray.remote
class StartNode(RayflowNode):
    """
    START node that serves as the entry point for RayFlow workflows.

    This node:
    - Defines the input schema for the entire workflow
    - Acts as the starting point for execution flow
    - Can be configured with API schema for HTTP server mode
    """

    # Metadata for UI
    icon = "fa-play"
    category = "base"
    description = "Entry point that starts workflow execution and defines input schema."

    # START nodes have dynamic inputs based on configuration
    inputs = {}

    # START nodes always output what they receive
    outputs = {
        "exec": "execution_flow"  # Execution flow output
    }

    def __init__(self, config=None):
        super().__init__(config)

        # Configure inputs from api_schema if provided
        if config and "api_schema" in config:
            schema = config["api_schema"]
            for field_name, field_def in schema.items():
                # Convert schema type to Python type
                field_type = self._schema_type_to_python(field_def.get("type", "str"))
                self.inputs[field_name] = field_type

    def _schema_type_to_python(self, schema_type):
        """Convert schema type string to Python type"""
        type_mapping = {
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "dict": dict,
            "list": list
        }
        return type_mapping.get(schema_type, str)

    def process(self, **inputs):
        """
        Process START node - simply passes through all inputs.

        Args:
            **inputs: All inputs defined in the configuration

        Returns:
            dict: All inputs plus execution flow signal
        """
        # Pass through all inputs and add execution flow
        result = dict(inputs)
        result["exec"] = True

        return result

    def validate_config(self, config):
        """
        Validate START node configuration.

        Args:
            config (dict): Node configuration

        Returns:
            bool: True if valid

        Raises:
            ValueError: If configuration is invalid
        """
        if not config:
            return True

        if "api_schema" in config:
            schema = config["api_schema"]
            if not isinstance(schema, dict):
                raise ValueError("api_schema must be a dictionary")

            for field_name, field_def in schema.items():
                if not isinstance(field_def, dict):
                    raise ValueError(f"Field definition for '{field_name}' must be a dictionary")

                if "type" not in field_def:
                    raise ValueError(f"Field '{field_name}' must have a 'type' specification")

                valid_types = ["int", "float", "str", "bool", "dict", "list"]
                if field_def["type"] not in valid_types:
                    raise ValueError(f"Invalid type '{field_def['type']}' for field '{field_name}'. Must be one of: {valid_types}")

        return True