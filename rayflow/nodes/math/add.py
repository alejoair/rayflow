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
        result = inputs["x"] + inputs["y"]
        return {
            "result": result
        }
