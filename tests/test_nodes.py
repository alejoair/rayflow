"""Tests for the node definition and discovery system."""
import pytest
from rayflow.nodes.decorators import ray_node, engine_node, ExecContext, Input, Output, ExecInput, ExecOutput, get_node_meta
from rayflow.nodes.loader import NodeCatalog
from rayflow.nodes.registry import get_catalog, reset_catalog


def test_ray_node_decorator_extracts_meta():
    @ray_node
    class AddNode:
        exec_in = ExecInput()
        a = Input("int", default=0)
        b = Input("int", default=0)
        result = Output("int")
        exec_out = ExecOutput()

        def run(self, ctx: ExecContext, a: int, b: int) -> dict:
            ctx.fire("exec_out")
            return {"result": a + b}

    meta = get_node_meta(AddNode)
    assert meta is not None
    assert meta.name == "AddNode"
    assert meta.has_exec_in
    assert meta.has_exec_out
    assert meta.is_exec_node
    assert not meta.is_engine_node
    assert len(meta.inputs) == 2
    assert len(meta.outputs) == 1
    input_names = [p.name for p in meta.inputs]
    assert "a" in input_names
    assert "b" in input_names


def test_engine_node_decorator_extracts_meta():
    @engine_node
    class MyBranch:
        exec_in = ExecInput()
        condition = Input("bool", default=False)
        true = ExecOutput()
        false = ExecOutput()

        def run(self, ctx: ExecContext, condition: bool) -> dict:
            ctx.fire("true" if condition else "false")
            return {}

    meta = get_node_meta(MyBranch)
    assert meta is not None
    assert meta.is_engine_node
    assert meta.has_exec_in
    assert len(meta.exec_outputs) == 2


def test_engine_node_is_entry_defaults_false():
    @engine_node
    class PlainNode:
        exec_in = ExecInput()
        exec_out = ExecOutput()

        def run(self, ctx: ExecContext) -> dict:
            ctx.fire("exec_out")
            return {}

    meta = get_node_meta(PlainNode)
    assert meta is not None
    assert meta.is_entry is False
    assert meta.exposes_flow_inputs is False


def test_engine_node_is_entry_extracted():
    @engine_node
    class MyTrigger:
        is_entry = True
        exposes_flow_inputs = True
        exec_out = ExecOutput()

    meta = get_node_meta(MyTrigger)
    assert meta is not None
    assert meta.is_entry is True
    assert meta.exposes_flow_inputs is True


def test_data_node_has_no_exec():
    @ray_node
    class MultiplyNode:
        x = Input("float", default=1.0)
        y = Input("float", default=1.0)
        result = Output("float")

        def run(self, x: float, y: float) -> dict:
            return {"result": x * y}

    meta = get_node_meta(MultiplyNode)
    assert not meta.has_exec_in
    assert not meta.has_exec_out
    assert not meta.is_exec_node


def test_input_default_values():
    @ray_node
    class NodeWithDefaults:
        name = Input("str", default="hello")
        count = Input("int", default=42)
        result = Output("str")

        def run(self, name: str, count: int) -> dict:
            return {"result": f"{name}:{count}"}

    meta = get_node_meta(NodeWithDefaults)
    name_pin = next(p for p in meta.inputs if p.name == "name")
    count_pin = next(p for p in meta.inputs if p.name == "count")
    assert name_pin.default == "hello"
    assert count_pin.default == 42
    assert not name_pin.required


def test_catalog_registers_builtin_nodes():
    reset_catalog()
    catalog = get_catalog()
    assert "OnStart" in catalog
    assert "FlowInput" in catalog
    assert "FlowOutput" in catalog
    assert "Branch" in catalog
    assert "Sequence" in catalog
    assert "ForEach" in catalog
    assert "Get" in catalog
    assert "Set" in catalog
    assert "OnEvent" in catalog
    assert "EmitEvent" in catalog
