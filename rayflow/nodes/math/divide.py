"""Math division node with error handling."""

import ray
from rayflow import RayflowNode


@ray.remote
class MathDivideNode(RayflowNode):
    """Divide two numbers with error handling."""

    # Metadata for UI
    icon = "fa-divide"
    category = "math"
    description = "Divides two numbers with error handling for division by zero."

    # Configurable constants
    PRECISION_DECIMALS = 4  # Number of decimal places in result
    ENABLE_ERROR_LOGGING = True  # Whether to log division errors
    DEFAULT_ERROR_VALUE = 0.0  # Default value when division by zero
    ERROR_MESSAGE_PREFIX = "Error"  # Prefix for error messages
    ENABLE_RANGE_VALIDATION = False  # Whether to validate input ranges
    MIN_DIVISOR_VALUE = 0.001  # Minimum allowed divisor (prevents near-zero division)
    MAX_RESULT_VALUE = 1000000.0  # Maximum allowed result value
    RETURN_INFINITY_ON_OVERFLOW = False  # Whether to return infinity instead of capping result
    ENABLE_SUCCESS_LOGGING = False  # Whether to log successful operations

    inputs = {
        "x": float,
        "y": float
    }

    outputs = {
        "result": float,
        "message": str
    }

    # Execution flow configuration
    exec_input = True    # Math nodes need exec input to be triggered
    exec_output = True   # Math nodes provide exec output to continue flow

    def process(self, **inputs):
        """Divide x by y."""
        x = inputs["x"]
        y = inputs["y"]

        if y == 0:
            if self.ENABLE_ERROR_LOGGING:
                print(f"{self.ERROR_MESSAGE_PREFIX}: Division by zero attempted")
            return {
                "result": self.DEFAULT_ERROR_VALUE,
                "message": f"{self.ERROR_MESSAGE_PREFIX}: Division by zero"
            }

        result = x / y
        # Apply precision formatting
        result = round(result, self.PRECISION_DECIMALS)
        return {
            "result": result,
            "message": f"Successfully divided {x} by {y}"
        }
