"""Tests for schema deserialization."""
import pytest
from rayflow.schema.loader import load_flow, unknown_keys
from rayflow.schema.models import FlowDef, NodeDef


def _simple_flow_dict():
    return {
        "name": "test_flow",
        "version": "1",
        "outputs": {"result": "int"},
        "variables": [{"name": "counter", "type": "int", "default": 0}],
        "nodes": [
            {"id": "start", "type": "OnStart"},
            {"id": "out", "type": "FlowOutput", "exec_in": "start"},
        ],
    }


def test_load_flow_from_dict():
    flow = load_flow(_simple_flow_dict())
    assert isinstance(flow, FlowDef)
    assert flow.name == "test_flow"
    # inputs were removed from FlowDef — they live on the entry node now.
    assert not hasattr(flow, "inputs") or getattr(flow, "inputs", None) in (None, {}, {"inputs": {}})
    assert flow.outputs == {"result": "int"}
    assert len(flow.variables) == 1
    assert flow.variables[0].name == "counter"
    assert flow.variables[0].default == 0


def test_load_flow_nodes():
    flow = load_flow(_simple_flow_dict())
    assert len(flow.nodes) == 2
    assert flow.nodes[0].id == "start"
    assert flow.nodes[0].type == "OnStart"
    assert flow.nodes[1].exec_in == "start"


def test_load_flow_missing_name():
    with pytest.raises(KeyError):
        load_flow({"version": "1", "nodes": []})


def test_flow_public_defaults_false_when_absent():
    """An old flow JSON saved before `public` existed must stay private."""
    flow = load_flow(_simple_flow_dict())
    assert flow.public is False


def test_flow_public_roundtrip_true():
    data = _simple_flow_dict()
    data["public"] = True
    flow = load_flow(data)
    assert flow.public is True

    # Roundtrip: dump back to a dict (as save_flow would) and reload.
    dumped = dict(data)
    dumped["public"] = flow.public
    reloaded = load_flow(dumped)
    assert reloaded.public is True


def test_flow_public_false_explicit():
    data = _simple_flow_dict()
    data["public"] = False
    flow = load_flow(data)
    assert flow.public is False


def test_flow_public_key_is_not_unknown():
    data = _simple_flow_dict()
    data["public"] = True
    warnings = unknown_keys(data)
    assert not any("public" in w for w in warnings)
    assert warnings == []
