"""Tests for NodeLoader module"""

import pytest
from rayflow.orchestrator.node_loader import NodeLoader
from rayflow.orchestrator.exceptions import NodeLoadError


class TestNodeLoader:
    """Test NodeLoader functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.loader = NodeLoader()

    def test_get_node_metadata_add(self):
        """Test extracting metadata from AddNode using AST"""
        class_path = "rayflow.nodes.math.add.MathAddNode"

        metadata = self.loader.get_node_metadata(class_path)

        assert metadata is not None
        assert metadata['class_name'] == 'MathAddNode'
        assert 'inputs' in metadata
        assert 'outputs' in metadata
        assert metadata['icon'] == 'fa-plus'
        assert metadata['category'] == 'math'

    def test_get_metadata_with_constants(self):
        """Test extracting constants from node metadata"""
        class_path = "rayflow.nodes.math.add.MathAddNode"

        metadata = self.loader.get_node_metadata(class_path)

        # AddNode has constants like OFFSET_VALUE
        assert 'constants' in metadata
        assert 'OFFSET_VALUE' in metadata['constants']
        assert metadata['constants']['OFFSET_VALUE']['type'] == 'int'
        assert metadata['constants']['OFFSET_VALUE']['value'] == 0

    def test_get_metadata_cached(self):
        """Test that metadata is cached"""
        class_path = "rayflow.nodes.math.add.MathAddNode"

        # Get twice
        metadata1 = self.loader.get_node_metadata(class_path)
        metadata2 = self.loader.get_node_metadata(class_path)

        # Should be the same object (cached)
        assert metadata1 is metadata2

    def test_get_metadata_invalid_class(self):
        """Test getting metadata for non-existent node"""
        class_path = "rayflow.nodes.invalid.nonexistent.FakeNode"

        with pytest.raises(NodeLoadError) as exc_info:
            self.loader.get_node_metadata(class_path)

        assert "Could not find file" in str(exc_info.value)

    def test_load_all_metadata_from_flow(self):
        """Test loading metadata for all nodes in a flow"""
        flow_data = {
            "nodes": [
                {
                    "id": "start_1",
                    "type": "rayflow.nodes.base.start.StartNode"
                },
                {
                    "id": "add_1",
                    "type": "rayflow.nodes.math.add.MathAddNode"
                },
                {
                    "id": "multiply_1",
                    "type": "rayflow.nodes.math.multiply.MultiplyNode"
                },
                {
                    "id": "return_1",
                    "type": "rayflow.nodes.base.return.ReturnNode"
                }
            ]
        }

        metadata_map = self.loader.load_all_metadata(flow_data)

        # Should have metadata for all node types
        assert len(metadata_map) == 4
        assert "rayflow.nodes.base.start.StartNode" in metadata_map
        assert "rayflow.nodes.math.add.MathAddNode" in metadata_map
        assert "rayflow.nodes.math.multiply.MultiplyNode" in metadata_map
        assert "rayflow.nodes.base.return.ReturnNode" in metadata_map

    def test_load_all_metadata_deduplicates(self):
        """Test that duplicate node types are not loaded twice"""
        flow_data = {
            "nodes": [
                {"id": "add_1", "type": "rayflow.nodes.math.add.MathAddNode"},
                {"id": "add_2", "type": "rayflow.nodes.math.add.MathAddNode"},
                {"id": "add_3", "type": "rayflow.nodes.math.add.MathAddNode"},
            ]
        }

        metadata_map = self.loader.load_all_metadata(flow_data)

        # Should only have one entry for AddNode
        assert len(metadata_map) == 1
        assert "rayflow.nodes.math.add.MathAddNode" in metadata_map

    def test_clear_cache(self):
        """Test clearing the cache"""
        class_path = "rayflow.nodes.math.add.MathAddNode"

        # Load and cache
        self.loader.get_node_metadata(class_path)

        assert len(self.loader._metadata_cache) > 0

        # Clear cache
        self.loader.clear_cache()

        assert len(self.loader._metadata_cache) == 0

    def test_load_start_node(self):
        """Test loading START node (special case with no exec_input)"""
        class_path = "rayflow.nodes.base.start.StartNode"

        metadata = self.loader.get_node_metadata(class_path)

        # START node should have exec_input = False
        assert metadata['exec_input'] is False
        assert metadata['exec_output'] is True

    def test_load_return_node(self):
        """Test loading RETURN node (special case with no exec_output)"""
        class_path = "rayflow.nodes.base.return.ReturnNode"

        metadata = self.loader.get_node_metadata(class_path)

        # RETURN node should have exec_output = False
        assert metadata['exec_input'] is True
        assert metadata['exec_output'] is False

    def test_metadata_has_inputs_outputs(self):
        """Test that metadata includes inputs and outputs"""
        class_path = "rayflow.nodes.math.add.MathAddNode"

        metadata = self.loader.get_node_metadata(class_path)

        # Check inputs
        assert 'inputs' in metadata
        assert 'x' in metadata['inputs']
        assert 'y' in metadata['inputs']
        assert metadata['inputs']['x'] == 'int'
        assert metadata['inputs']['y'] == 'int'

        # Check outputs
        assert 'outputs' in metadata
        assert 'result' in metadata['outputs']
        assert metadata['outputs']['result'] == 'int'

    # NOTE: load_node_class will be tested in ActorManager tests
    # It can't be tested standalone because Ray actors can't be imported
    # without triggering the full Ray setup
