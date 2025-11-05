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

    inputs = {
        "x": float,
        "y": float
    }

    outputs = {
        "result": float,
        "message": str
    }

    def process(self, **inputs):
        """Divide x by y."""
        x = inputs["x"]
        y = inputs["y"]

        if y == 0:
            return {
                "result": 0.0,
                "message": "Error: Division by zero"
            }

        result = x / y
        return {
            "result": result,
            "message": f"Successfully divided {x} by {y}"
        }
