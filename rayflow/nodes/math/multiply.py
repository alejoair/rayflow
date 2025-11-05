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

    inputs = {
        "x": int,
        "y": int
    }

    outputs = {
        "result": int
    }

    def process(self, **inputs):
        """Multiply x and y."""
        result = inputs["x"] * inputs["y"]
        return {
            "result": result
        }
