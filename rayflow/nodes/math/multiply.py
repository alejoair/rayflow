"""Math multiplication node."""

import ray
from rayflow import RayflowNode


@ray.remote
class MathMultiplyNode(RayflowNode):
    """Multiply two numbers together."""

    # Metadata for UI
    icon = "fa-times"
    category = "math"
    description = "Multiplies two numbers together and returns the result."

    # Configurable constants
    MAX_RESULT_VALUE = 1000000  # Maximum allowed result value
    ENABLE_OVERFLOW_PROTECTION = True  # Whether to check for overflow
    RESULT_MULTIPLIER = 1  # Additional multiplier for result
    ENABLE_LOGGING = False  # Whether to log multiplication operations

    inputs = {
        "x": int,
        "y": int
    }

    outputs = {
        "result": int
    }

    # Execution flow configuration
    exec_input = True    # Math nodes need exec input to be triggered
    exec_output = True   # Math nodes provide exec output to continue flow

    def process(self, **inputs):
        """Multiply x and y."""
        x = inputs["x"]
        y = inputs["y"]

        if self.ENABLE_LOGGING:
            print(f"Multiplying {x} * {y}")

        result = x * y * self.RESULT_MULTIPLIER

        # Check for overflow protection
        if self.ENABLE_OVERFLOW_PROTECTION and abs(result) > self.MAX_RESULT_VALUE:
            print(f"Warning: Result {result} exceeds maximum allowed value {self.MAX_RESULT_VALUE}")
            result = self.MAX_RESULT_VALUE if result > 0 else -self.MAX_RESULT_VALUE

        return {
            "result": int(result)
        }
