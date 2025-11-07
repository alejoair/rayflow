"""Tests for FlowValidator module"""

import pytest
from rayflow.orchestrator.validator import FlowValidator


class TestFlowValidator:
    """Test FlowValidator functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.validator = FlowValidator()

    def test_valid_simple_flow(self):
        """Test validation of a simple valid flow"""
        flow_data = {
            "nodes": [
                {
                    "id": "start_1",
                    "type": "rayflow.nodes.base.start.StartNode",
                    "data": {"label": "START"}
                },
                {
                    "id": "add_1",
                    "type": "rayflow.nodes.math.add.AddNode",
                    "data": {
                        "label": "Add",
                        "inputs": {"x": {"type": "int"}, "y": {"type": "int"}},
                        "outputs": {"result": {"type": "int"}}
                    }
                },
                {
                    "id": "return_1",
                    "type": "rayflow.nodes.base.return_node.ReturnNode",
                    "data": {"label": "RETURN"}
                }
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "start_1",
                    "target": "add_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                },
                {
                    "id": "e2",
                    "source": "add_1",
                    "target": "return_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                }
            ]
        }

        is_valid, errors = self.validator.validate(flow_data)
        assert is_valid is True
        assert len(errors) == 0

    def test_missing_start_node(self):
        """Test validation fails without START node"""
        flow_data = {
            "nodes": [
                {
                    "id": "add_1",
                    "type": "rayflow.nodes.math.add.AddNode",
                    "data": {"label": "Add"}
                },
                {
                    "id": "return_1",
                    "type": "rayflow.nodes.base.return_node.ReturnNode",
                    "data": {"label": "RETURN"}
                }
            ],
            "edges": []
        }

        is_valid, errors = self.validator.validate(flow_data)
        assert is_valid is False
        assert any("START" in error for error in errors)

    def test_multiple_start_nodes(self):
        """Test validation fails with multiple START nodes"""
        flow_data = {
            "nodes": [
                {
                    "id": "start_1",
                    "type": "rayflow.nodes.base.start.StartNode",
                    "data": {"label": "START 1"}
                },
                {
                    "id": "start_2",
                    "type": "rayflow.nodes.base.start.StartNode",
                    "data": {"label": "START 2"}
                },
                {
                    "id": "return_1",
                    "type": "rayflow.nodes.base.return_node.ReturnNode",
                    "data": {"label": "RETURN"}
                }
            ],
            "edges": []
        }

        is_valid, errors = self.validator.validate(flow_data)
        assert is_valid is False
        assert any("exactly one START" in error for error in errors)

    def test_missing_return_node(self):
        """Test validation fails without RETURN node"""
        flow_data = {
            "nodes": [
                {
                    "id": "start_1",
                    "type": "rayflow.nodes.base.start.StartNode",
                    "data": {"label": "START"}
                },
                {
                    "id": "add_1",
                    "type": "rayflow.nodes.math.add.AddNode",
                    "data": {"label": "Add"}
                }
            ],
            "edges": []
        }

        is_valid, errors = self.validator.validate(flow_data)
        assert is_valid is False
        assert any("RETURN" in error for error in errors)

    def test_unreachable_nodes(self):
        """Test validation detects unreachable nodes"""
        flow_data = {
            "nodes": [
                {
                    "id": "start_1",
                    "type": "rayflow.nodes.base.start.StartNode",
                    "data": {"label": "START"}
                },
                {
                    "id": "add_1",
                    "type": "rayflow.nodes.math.add.AddNode",
                    "data": {"label": "Add 1"}
                },
                {
                    "id": "add_2",
                    "type": "rayflow.nodes.math.add.AddNode",
                    "data": {"label": "Add 2"}  # This one is not connected
                },
                {
                    "id": "return_1",
                    "type": "rayflow.nodes.base.return_node.ReturnNode",
                    "data": {"label": "RETURN"}
                }
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "start_1",
                    "target": "add_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                },
                {
                    "id": "e2",
                    "source": "add_1",
                    "target": "return_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                }
            ]
        }

        is_valid, errors = self.validator.validate(flow_data)
        assert is_valid is False
        assert any("not reachable" in error for error in errors)

    def test_no_return_reachable(self):
        """Test validation detects when no RETURN is reachable"""
        flow_data = {
            "nodes": [
                {
                    "id": "start_1",
                    "type": "rayflow.nodes.base.start.StartNode",
                    "data": {"label": "START"}
                },
                {
                    "id": "add_1",
                    "type": "rayflow.nodes.math.add.AddNode",
                    "data": {"label": "Add"}
                },
                {
                    "id": "return_1",
                    "type": "rayflow.nodes.base.return_node.ReturnNode",
                    "data": {"label": "RETURN"}  # Not connected
                }
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "start_1",
                    "target": "add_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                }
            ]
        }

        is_valid, errors = self.validator.validate(flow_data)
        assert is_valid is False
        assert any("No RETURN node is reachable" in error for error in errors)

    def test_cycle_detection(self):
        """Test validation detects cycles"""
        flow_data = {
            "nodes": [
                {
                    "id": "start_1",
                    "type": "rayflow.nodes.base.start.StartNode",
                    "data": {"label": "START"}
                },
                {
                    "id": "add_1",
                    "type": "rayflow.nodes.math.add.AddNode",
                    "data": {"label": "Add 1"}
                },
                {
                    "id": "add_2",
                    "type": "rayflow.nodes.math.add.AddNode",
                    "data": {"label": "Add 2"}
                },
                {
                    "id": "return_1",
                    "type": "rayflow.nodes.base.return_node.ReturnNode",
                    "data": {"label": "RETURN"}
                }
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "start_1",
                    "target": "add_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                },
                {
                    "id": "e2",
                    "source": "add_1",
                    "target": "add_2",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                },
                {
                    "id": "e3",
                    "source": "add_2",
                    "target": "add_1",  # Cycle!
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                },
                {
                    "id": "e4",
                    "source": "add_2",
                    "target": "return_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                }
            ]
        }

        is_valid, errors = self.validator.validate(flow_data)
        assert is_valid is False
        assert any("cycle" in error.lower() for error in errors)

    def test_type_compatibility_valid(self):
        """Test type compatibility validation with valid connections"""
        flow_data = {
            "nodes": [
                {
                    "id": "start_1",
                    "type": "rayflow.nodes.base.start.StartNode",
                    "data": {
                        "label": "START",
                        "outputs": {"x": {"type": "int"}}
                    }
                },
                {
                    "id": "add_1",
                    "type": "rayflow.nodes.math.add.AddNode",
                    "data": {
                        "label": "Add",
                        "inputs": {"x": {"type": "int"}, "y": {"type": "int"}},
                        "outputs": {"result": {"type": "int"}}
                    }
                },
                {
                    "id": "return_1",
                    "type": "rayflow.nodes.base.return_node.ReturnNode",
                    "data": {"label": "RETURN"}
                }
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "start_1",
                    "target": "add_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                },
                {
                    "id": "e2",
                    "source": "start_1",
                    "target": "add_1",
                    "sourceHandle": "x",
                    "targetHandle": "x",
                    "type": "data"
                },
                {
                    "id": "e3",
                    "source": "add_1",
                    "target": "return_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                }
            ]
        }

        is_valid, errors = self.validator.validate(flow_data)
        assert is_valid is True
        assert len(errors) == 0

    def test_type_compatibility_invalid(self):
        """Test type compatibility validation with invalid connections"""
        flow_data = {
            "nodes": [
                {
                    "id": "start_1",
                    "type": "rayflow.nodes.base.start.StartNode",
                    "data": {
                        "label": "START",
                        "outputs": {"x": {"type": "str"}}  # String output
                    }
                },
                {
                    "id": "add_1",
                    "type": "rayflow.nodes.math.add.AddNode",
                    "data": {
                        "label": "Add",
                        "inputs": {"x": {"type": "int"}},  # Int input
                        "outputs": {"result": {"type": "int"}}
                    }
                },
                {
                    "id": "return_1",
                    "type": "rayflow.nodes.base.return_node.ReturnNode",
                    "data": {"label": "RETURN"}
                }
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "start_1",
                    "target": "add_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                },
                {
                    "id": "e2",
                    "source": "start_1",
                    "target": "add_1",
                    "sourceHandle": "x",
                    "targetHandle": "x",
                    "type": "data"
                }
            ]
        }

        is_valid, errors = self.validator.validate(flow_data)
        assert is_valid is False
        assert any("Type mismatch" in error for error in errors)

    def test_any_type_compatibility(self):
        """Test that 'any' type is compatible with everything"""
        flow_data = {
            "nodes": [
                {
                    "id": "start_1",
                    "type": "rayflow.nodes.base.start.StartNode",
                    "data": {
                        "label": "START",
                        "outputs": {"x": {"type": "any"}}
                    }
                },
                {
                    "id": "add_1",
                    "type": "rayflow.nodes.math.add.AddNode",
                    "data": {
                        "label": "Add",
                        "inputs": {"x": {"type": "int"}},
                        "outputs": {"result": {"type": "int"}}
                    }
                },
                {
                    "id": "return_1",
                    "type": "rayflow.nodes.base.return_node.ReturnNode",
                    "data": {"label": "RETURN"}
                }
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "start_1",
                    "target": "add_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                },
                {
                    "id": "e2",
                    "source": "start_1",
                    "target": "add_1",
                    "sourceHandle": "x",
                    "targetHandle": "x",
                    "type": "data"
                },
                {
                    "id": "e3",
                    "source": "add_1",
                    "target": "return_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                }
            ]
        }

        is_valid, errors = self.validator.validate(flow_data)
        assert is_valid is True
        assert len(errors) == 0
