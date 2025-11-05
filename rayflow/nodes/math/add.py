"""Math addition node."""

import ray
from rayflow import RayflowNode


@ray.remote
class MathAddNode(RayflowNode):
    """Add two numbers together."""

    # Metadata for UI
    icon = "fa-plus"
    category = "math"
    description = "Adds two numbers together and returns the result."

    # Configurable constants
    OFFSET_VALUE = 0  # Additional value to add to result
    ENABLE_VALIDATION = True  # Whether to validate input ranges
    MIN_INPUT_VALUE = -1000  # Minimum allowed input value
    MAX_INPUT_VALUE = 1000  # Maximum allowed input value

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
        """Add x and y."""
        x = inputs["x"]
        y = inputs["y"]

        # Validate inputs if enabled
        if self.ENABLE_VALIDATION:
            if x < self.MIN_INPUT_VALUE or x > self.MAX_INPUT_VALUE:
                print(f"Warning: Input x={x} is outside valid range [{self.MIN_INPUT_VALUE}, {self.MAX_INPUT_VALUE}]")
            if y < self.MIN_INPUT_VALUE or y > self.MAX_INPUT_VALUE:
                print(f"Warning: Input y={y} is outside valid range [{self.MIN_INPUT_VALUE}, {self.MAX_INPUT_VALUE}]")

        result = x + y + self.OFFSET_VALUE
        return {
            "result": result
        }
