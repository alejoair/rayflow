"""Tests for GraphBuilder module"""

import pytest
from rayflow.orchestrator.graph_builder import GraphBuilder
from rayflow.orchestrator.exceptions import GraphBuildError


class TestGraphBuilder:
    """Test GraphBuilder functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        # Mock node metadata
        self.metadata_map = {
            "rayflow.nodes.base.start.StartNode": {
                "name": "START",
                "inputs": {},
                "outputs": {},
                "exec_input": False,
                "exec_output": True
            },
            "rayflow.nodes.math.add.AddNode": {
                "name": "Add",
                "inputs": {"x": "int", "y": "int"},
                "outputs": {"result": "int"},
                "exec_input": True,
                "exec_output": True
            },
            "rayflow.nodes.math.multiply.MultiplyNode": {
                "name": "Multiply",
                "inputs": {"x": "int"},
                "outputs": {"result": "int"},
                "exec_input": True,
                "exec_output": True
            },
            "rayflow.nodes.base.return_node.ReturnNode": {
                "name": "RETURN",
                "inputs": {},
                "outputs": {},
                "exec_input": True,
                "exec_output": False
            }
        }
        self.builder = GraphBuilder(self.metadata_map)

    def test_simple_linear_flow(self):
        """Test building a simple linear flow"""
        flow_data = {
            "nodes": [
                {
                    "id": "start_1",
                    "type": "rayflow.nodes.base.start.StartNode",
                    "data": {"label": "START", "constantValues": {}}
                },
                {
                    "id": "add_1",
                    "type": "rayflow.nodes.math.add.AddNode",
                    "data": {"label": "Add", "constantValues": {"OFFSET": 10}}
                },
                {
                    "id": "return_1",
                    "type": "rayflow.nodes.base.return_node.ReturnNode",
                    "data": {"label": "RETURN", "constantValues": {}}
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

        graph = self.builder.build_graph(flow_data)

        # Check graph structure
        assert "nodes" in graph
        assert "edges" in graph
        assert "start_node" in graph
        assert "return_nodes" in graph
        assert "execution_order" in graph

        # Check nodes
        assert len(graph["nodes"]) == 3
        assert "start_1" in graph["nodes"]
        assert "add_1" in graph["nodes"]
        assert "return_1" in graph["nodes"]

        # Check START node
        assert graph["start_node"] == "start_1"

        # Check RETURN nodes
        assert "return_1" in graph["return_nodes"]

        # Check execution order
        assert graph["execution_order"] == ["start_1", "add_1", "return_1"]

        # Check dependencies
        assert graph["nodes"]["start_1"]["dependencies"] == []
        assert graph["nodes"]["add_1"]["dependencies"] == ["start_1"]
        assert graph["nodes"]["return_1"]["dependencies"] == ["add_1"]

        # Check constants
        assert graph["nodes"]["add_1"]["constants"]["OFFSET"] == 10

    def test_parallel_branches(self):
        """Test building a flow with parallel branches"""
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
                # START branches to both Add nodes
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
                    "target": "add_2",
                    "sourceHandle": "exec",
                    "targetHandle": "exec",
                    "type": "exec"
                },
                # Both join at RETURN
                {
                    "id": "e3",
                    "source": "add_1",
                    "target": "return_1",
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

        graph = self.builder.build_graph(flow_data)

        # Check that parallel nodes have same dependency (START)
        assert graph["nodes"]["add_1"]["dependencies"] == ["start_1"]
        assert graph["nodes"]["add_2"]["dependencies"] == ["start_1"]

        # Check that RETURN depends on both
        assert set(graph["nodes"]["return_1"]["dependencies"]) == {"add_1", "add_2"}

        # Check execution order (START first, then Add nodes, then RETURN)
        order = graph["execution_order"]
        assert order[0] == "start_1"
        assert set(order[1:3]) == {"add_1", "add_2"}  # Can be in any order
        assert order[3] == "return_1"

    def test_data_and_exec_dependencies(self):
        """Test that both exec and data connections create dependencies"""
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
                    "id": "multiply_1",
                    "type": "rayflow.nodes.math.multiply.MultiplyNode",
                    "data": {"label": "Multiply"}
                },
                {
                    "id": "return_1",
                    "type": "rayflow.nodes.base.return_node.ReturnNode",
                    "data": {"label": "RETURN"}
                }
            ],
            "edges": [
                # Exec flow: START -> Add -> RETURN
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
                },
                # Data flow: START -> Multiply (no exec connection!)
                {
                    "id": "e3",
                    "source": "start_1",
                    "target": "multiply_1",
                    "sourceHandle": "x",
                    "targetHandle": "x",
                    "type": "data"
                },
                # Data flow: Multiply -> Return
                {
                    "id": "e4",
                    "source": "multiply_1",
                    "target": "return_1",
                    "sourceHandle": "result",
                    "targetHandle": "value",
                    "type": "data"
                }
            ]
        }

        graph = self.builder.build_graph(flow_data)

        # Multiply should depend on START (data dependency)
        assert "start_1" in graph["nodes"]["multiply_1"]["dependencies"]

        # RETURN should depend on both Add (exec) and Multiply (data)
        assert set(graph["nodes"]["return_1"]["dependencies"]) == {"add_1", "multiply_1"}

    def test_get_exec_successors(self):
        """Test getting exec successors of a node"""
        flow_data = {
            "nodes": [
                {"id": "start_1", "type": "rayflow.nodes.base.start.StartNode", "data": {}},
                {"id": "add_1", "type": "rayflow.nodes.math.add.AddNode", "data": {}},
                {"id": "add_2", "type": "rayflow.nodes.math.add.AddNode", "data": {}},
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
                    "target": "add_2",
                    "sourceHandle": "exec_alt",
                    "targetHandle": "exec",
                    "type": "exec"
                }
            ]
        }

        graph = self.builder.build_graph(flow_data)
        successors = self.builder.get_exec_successors(graph, "start_1")

        # Should have two exec successors
        assert len(successors) == 2

        # Extract targets
        targets = [s[0] for s in successors]
        assert set(targets) == {"add_1", "add_2"}

    def test_get_data_sources(self):
        """Test getting data sources for a node"""
        flow_data = {
            "nodes": [
                {"id": "start_1", "type": "rayflow.nodes.base.start.StartNode", "data": {}},
                {"id": "add_1", "type": "rayflow.nodes.math.add.AddNode", "data": {}},
                {"id": "multiply_1", "type": "rayflow.nodes.math.multiply.MultiplyNode", "data": {}},
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "start_1",
                    "target": "multiply_1",
                    "sourceHandle": "x",
                    "targetHandle": "x",
                    "type": "data"
                },
                {
                    "id": "e2",
                    "source": "add_1",
                    "target": "multiply_1",
                    "sourceHandle": "result",
                    "targetHandle": "factor",
                    "type": "data"
                }
            ]
        }

        graph = self.builder.build_graph(flow_data)
        sources = self.builder.get_data_sources(graph, "multiply_1")

        # Should have two data sources
        assert len(sources) == 2
        assert sources["x"] == ("start_1", "x")
        assert sources["factor"] == ("add_1", "result")

    def test_multiple_return_nodes(self):
        """Test flow with multiple RETURN nodes"""
        flow_data = {
            "nodes": [
                {"id": "start_1", "type": "rayflow.nodes.base.start.StartNode", "data": {}},
                {"id": "add_1", "type": "rayflow.nodes.math.add.AddNode", "data": {}},
                {"id": "return_1", "type": "rayflow.nodes.base.return_node.ReturnNode", "data": {}},
                {"id": "return_2", "type": "rayflow.nodes.base.return_node.ReturnNode", "data": {}},
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "start_1",
                    "target": "add_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec"
                },
                {
                    "id": "e2",
                    "source": "add_1",
                    "target": "return_1",
                    "sourceHandle": "exec",
                    "targetHandle": "exec"
                },
                {
                    "id": "e3",
                    "source": "add_1",
                    "target": "return_2",
                    "sourceHandle": "exec_alt",
                    "targetHandle": "exec"
                }
            ]
        }

        graph = self.builder.build_graph(flow_data)

        # Should identify both RETURN nodes
        assert len(graph["return_nodes"]) == 2
        assert set(graph["return_nodes"]) == {"return_1", "return_2"}
