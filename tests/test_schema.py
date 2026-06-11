"""Tests de deserialización del schema."""
import pytest
from rayflow.schema.loader import load_flow
from rayflow.schema.models import FlowDef, NodeDef


def _simple_flow_dict():
    return {
        "name": "test_flow",
        "version": "1",
        "inputs": {"x": "int"},
        "outputs": {"result": "int"},
        "variables": [{"name": "counter", "type": "int", "default": 0}],
        "nodes": [
            {"id": "start", "type": "FlowInput"},
            {"id": "out", "type": "FlowOutput", "exec_in": "start"},
        ],
    }


def test_load_flow_from_dict():
    flow = load_flow(_simple_flow_dict())
    assert isinstance(flow, FlowDef)
    assert flow.name == "test_flow"
    assert flow.inputs == {"x": "int"}
    assert flow.outputs == {"result": "int"}
    assert len(flow.variables) == 1
    assert flow.variables[0].name == "counter"
    assert flow.variables[0].default == 0


def test_load_flow_nodes():
    flow = load_flow(_simple_flow_dict())
    assert len(flow.nodes) == 2
    assert flow.nodes[0].id == "start"
    assert flow.nodes[0].type == "FlowInput"
    assert flow.nodes[1].exec_in == "start"


def test_load_flow_missing_name():
    with pytest.raises(KeyError):
        load_flow({"version": "1", "nodes": []})
