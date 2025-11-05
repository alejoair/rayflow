"""RETURN node - Exit points for RayFlow workflows."""

import ray
from rayflow import RayflowNode


@ray.remote
class ReturnNode(RayflowNode):
    """
    RETURN node that serves as an exit point for RayFlow workflows.

    This node:
    - Terminates workflow execution at specific points
    - Can define HTTP response codes and schemas for API mode
    - Allows multiple exit points with different outcomes
    - Returns final results to the orchestrator
    """

    # Metadata for UI
    icon = "fa-flag-checkered"
    category = "base"
    description = "Exit point that terminates workflow execution and returns results."

    # RETURN nodes accept any inputs (dynamic based on config)
    inputs = {}

    # RETURN nodes don't output to other nodes (they terminate the flow)
    outputs = {}

    # Execution flow configuration
    exec_input = True    # RETURN nodes need exec input to be triggered
    exec_output = False  # RETURN nodes don't provide exec output (they terminate)

    def __init__(self, config=None):
        super().__init__(config)

        # Configure dynamic inputs based on response_schema if provided
        if config and "response_schema" in config:
            schema = config["response_schema"]
            for field_name, field_def in schema.items():
                if isinstance(field_def, dict) and "type" in field_def:
                    field_type = self._schema_type_to_python(field_def["type"])
                else:
                    # Simple type string
                    field_type = self._schema_type_to_python(field_def)
                self.inputs[field_name] = field_type

    def _schema_type_to_python(self, schema_type):
        """Convert schema type string to Python type"""
        type_mapping = {
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "dict": dict,
            "list": list,
            "any": object
        }
        return type_mapping.get(schema_type, str)

    def process(self, **inputs):
        """
        Process RETURN node - formats and returns final results.

        Args:
            **inputs: All inputs received

        Returns:
            dict: Formatted response with metadata
        """
        config = self.config or {}

        # Remove execution flow from inputs for clean output
        clean_inputs = {k: v for k, v in inputs.items() if k != "exec"}

        # Build response
        response = {
            "status": "success",
            "data": clean_inputs
        }

        # Add configured metadata
        if "name" in config:
            response["return_point"] = config["name"]

        if "status_code" in config:
            response["status_code"] = config["status_code"]
        else:
            response["status_code"] = 200

        if "message" in config:
            response["message"] = config["message"]

        # If response_schema is defined, validate and format output
        if "response_schema" in config:
            schema = config["response_schema"]
            formatted_data = {}

            for field_name, field_def in schema.items():
                if field_name in clean_inputs:
                    formatted_data[field_name] = clean_inputs[field_name]
                elif isinstance(field_def, dict) and "default" in field_def:
                    formatted_data[field_name] = field_def["default"]

            response["data"] = formatted_data

        return response

    def validate_config(self, config):
        """
        Validate RETURN node configuration.

        Args:
            config (dict): Node configuration

        Returns:
            bool: True if valid

        Raises:
            ValueError: If configuration is invalid
        """
        if not config:
            return True

        # Validate status_code if provided
        if "status_code" in config:
            status_code = config["status_code"]
            if not isinstance(status_code, int) or status_code < 100 or status_code > 599:
                raise ValueError(f"status_code must be a valid HTTP status code (100-599), got: {status_code}")

        # Validate response_schema if provided
        if "response_schema" in config:
            schema = config["response_schema"]
            if not isinstance(schema, dict):
                raise ValueError("response_schema must be a dictionary")

            for field_name, field_def in schema.items():
                if isinstance(field_def, dict):
                    if "type" not in field_def:
                        raise ValueError(f"Field '{field_name}' must have a 'type' specification")

                    valid_types = ["int", "float", "str", "bool", "dict", "list", "any"]
                    if field_def["type"] not in valid_types:
                        raise ValueError(f"Invalid type '{field_def['type']}' for field '{field_name}'. Must be one of: {valid_types}")
                else:
                    # Simple type string
                    valid_types = ["int", "float", "str", "bool", "dict", "list", "any"]
                    if field_def not in valid_types:
                        raise ValueError(f"Invalid type '{field_def}' for field '{field_name}'. Must be one of: {valid_types}")

        return True

    def is_terminal(self):
        """
        Indicates that this node terminates workflow execution.

        Returns:
            bool: Always True for RETURN nodes
        """
        return True