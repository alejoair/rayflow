"""Base class for RayFlow nodes."""

import ray


@ray.remote
class RayflowNode:
    """
    Base class for all RayFlow nodes.

    Users must:
    - Define `inputs` dict (name: type)
    - Define `outputs` dict (name: type)
    - Define `exec_input` bool (default: True) - whether node needs exec input
    - Define `exec_output` bool (default: True) - whether node provides exec output
    - Implement `process(**inputs)` method that returns dict of outputs
    """

    inputs = {}
    outputs = {}

    # Execution flow configuration
    exec_input = True    # Whether this node needs execution signal input
    exec_output = True   # Whether this node provides execution signal output

    def __init__(self, store_ref=None, config=None):
        """
        Constructor base.

        Args:
            store_ref: Reference to GlobalVariableStore (all nodes receive this)
            config: Node-specific configuration from JSON
        """
        self.store = store_ref
        self.config = config or {}

    def process(self, **inputs):
        """
        Process inputs and return outputs.
        User MUST implement this method.

        Args:
            **inputs: Input values matching the `inputs` dict

        Returns:
            dict: Output values matching the `outputs` dict
        """
        raise NotImplementedError("Subclasses must implement process()")
