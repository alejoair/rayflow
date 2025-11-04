"""Example node: Math addition."""

import ray
from rayflow import RayflowNode


@ray.remote
class MathAddNode(RayflowNode):
    """Add two numbers together."""

    inputs = {
        "x": int,
        "y": int
    }

    outputs = {
        "result": int
    }

    def process(self, **inputs):
        """Add x and y."""
        result = inputs["x"] + inputs["y"]
        return {
            "result": result
        }
