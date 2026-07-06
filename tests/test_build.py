"""Tests for the build/validation layer."""
import pytest
from rayflow.schema.loader import load_flow
from rayflow.nodes.registry import get_catalog, reset_catalog
from rayflow.build.validator import build, BuildError, BuiltFlow


def _make_catalog():
    reset_catalog()
    return get_catalog()


def _minimal_flow():
    """Minimal flow: OnStart → FlowOutput."""
    return {
        "name": "minimal",
        "nodes": [
            {"id": "n_start", "type": "OnStart"},
            {"id": "n_out", "type": "FlowOutput", "exec_in": "n_start"},
        ],
    }


def test_build_minimal_flow():
    flow = load_flow(_minimal_flow())
    catalog = _make_catalog()
    built = build(flow, catalog)
    assert isinstance(built, BuiltFlow)
    assert built.entry_node_id == "n_start"
    assert built.output_node_ids == ["n_out"]


def test_build_unknown_node_type():
    flow = load_flow({
        "name": "bad",
        "nodes": [{"id": "x", "type": "NonExistentNode"}],
    })
    catalog = _make_catalog()
    with pytest.raises(BuildError, match="catalog"):
        build(flow, catalog)


def test_build_missing_entry_node():
    flow = load_flow({
        "name": "no_entry",
        "nodes": [
            {"id": "out", "type": "FlowOutput"},
        ],
    })
    catalog = _make_catalog()
    with pytest.raises(BuildError):
        build(flow, catalog)


def test_build_more_than_one_entry_node():
    """A flow with two is_entry nodes (OnStart + OnEvent) must pick exactly one."""
    flow = load_flow({
        "name": "two_entries",
        "nodes": [
            {"id": "a", "type": "OnStart"},
            {"id": "b", "type": "OnEvent"},
        ],
    })
    catalog = _make_catalog()
    with pytest.raises(BuildError, match="more than one entry"):
        build(flow, catalog)


def test_build_custom_entry_node():
    """Any node declared with @entry_node can be a flow's entry point, not just the builtins."""
    from rayflow.nodes.decorators import entry_node, ExecOutput, Input

    @entry_node
    class MyTrigger:
        message = Input("str")
        exec_out = ExecOutput()

    reset_catalog()
    catalog = get_catalog()
    catalog.register(MyTrigger)

    flow = load_flow({
        "name": "custom_entry",
        "nodes": [
            {"id": "trig", "type": "MyTrigger"},
            {"id": "out", "type": "FlowOutput", "exec_in": "trig"},
        ],
    })
    built = build(flow, catalog)
    assert built.entry_node_id == "trig"


def test_build_ray_node_with_is_entry_rejected():
    """A class marked as entry (via @entry_node) cannot also be @ray_node —
    entries run inside the engine and use EntryContext, not a Ray actor."""
    from rayflow.nodes.decorators import ray_node, entry_node, ExecOutput, get_node_meta

    # Build a normal @entry_node, then attempt to re-apply @ray_node on the
    # same class. The is_entry flag is already set on the meta; @ray_node
    # refuses it.
    @entry_node
    class Entry:
        exec_out = ExecOutput()

    with pytest.raises(ValueError, match="@entry_node"):
        ray_node(Entry)


def test_build_entry_node_with_exec_in_rejected():
    """An @entry_node must not declare exec_in — nothing inside the graph
    should be able to fire an entry node."""
    from rayflow.nodes.decorators import entry_node, ExecInput, ExecOutput

    with pytest.raises(ValueError, match="exec_in"):
        @entry_node
        class BadWiredEntry:
            exec_in = ExecInput()
            exec_out = ExecOutput()


def test_build_exec_input_missing():
    """FlowOutput requires exec_in but doesn't have it."""
    flow = load_flow({
        "name": "bad_exec",
        "nodes": [
            {"id": "start", "type": "OnStart"},
            {"id": "out", "type": "FlowOutput"},  # no exec_in
        ],
    })
    catalog = _make_catalog()
    with pytest.raises(BuildError, match="exec input"):
        build(flow, catalog)


def test_build_type_mismatch():
    """Data connection with incompatible types."""
    from rayflow.nodes.decorators import ray_node, ExecContext, Input, Output, ExecInput, ExecOutput

    @ray_node
    class ProducesStr:
        exec_in = ExecInput()
        value = Output("str")
        exec_out = ExecOutput()

        def run(self, ctx: ExecContext) -> dict:
            ctx.fire("exec_out")
            return {"value": "hello"}

    @ray_node
    class ConsumesInt:
        exec_in = ExecInput()
        value = Input("int", default=0)
        exec_out = ExecOutput()

        def run(self, ctx: ExecContext, value: int) -> dict:
            ctx.fire("exec_out")
            return {}

    reset_catalog()
    catalog = get_catalog()
    catalog.register(ProducesStr)
    catalog.register(ConsumesInt)

    flow = load_flow({
        "name": "type_mismatch",
        "nodes": [
            {"id": "start", "type": "OnStart"},
            {"id": "prod", "type": "ProducesStr", "exec_in": "start"},
            {
                "id": "cons",
                "type": "ConsumesInt",
                "exec_in": "prod",
                "inputs": {"value": "prod.value"},
            },
        ],
    })
    with pytest.raises(BuildError, match="incompatible"):
        build(flow, catalog)


def test_callflow_resolves_saved_flow_by_name(tmp_path, monkeypatch):
    """CallFlow's 'flow' input accepts a saved flow's NAME exactly as
    returned by list_flows/create_flow (e.g. "my_subflow", no extension),
    resolved against the workspace's flows/ dir via
    rayflow.workspace.resolve_flow — not just an inline dict or a raw path
    handed straight to schema.loader.load_flow (regression: ISSUE-0012)."""
    import json

    (tmp_path / "flows").mkdir()
    (tmp_path / "flows" / "my_subflow.json").write_text(
        json.dumps({
            "name": "my_subflow",
            "nodes": [
                {"id": "sub_start", "type": "OnStart"},
                {"id": "sub_out", "type": "FlowOutput", "exec_in": "sub_start"},
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    flow = load_flow({
        "name": "parent",
        "nodes": [
            {"id": "start", "type": "OnStart"},
            {"id": "cf", "type": "CallFlow", "exec_in": "start",
             "inputs": {"flow": "my_subflow"}},
            {"id": "out", "type": "FlowOutput", "exec_in": "cf"},
        ],
    })
    catalog = _make_catalog()
    built = build(flow, catalog)
    assert isinstance(built, BuiltFlow)
    # The subflow's nodes got flattened/spliced in under the "cf/" prefix.
    assert "cf/sub_start" in built.nodes
    assert "cf/sub_out" in built.nodes


def test_callflow_unknown_flow_name_raises_domain_error(tmp_path, monkeypatch):
    """An unresolvable 'flow' name/path must raise a clear domain BuildError
    ("references unknown flow"), not a raw filesystem OSError/FileNotFoundError
    leaking out of validate_flow (regression: ISSUE-0012)."""
    (tmp_path / "flows").mkdir()
    monkeypatch.chdir(tmp_path)

    flow = load_flow({
        "name": "parent",
        "nodes": [
            {"id": "start", "type": "OnStart"},
            {"id": "cf", "type": "CallFlow", "exec_in": "start",
             "inputs": {"flow": "does_not_exist"}},
            {"id": "out", "type": "FlowOutput", "exec_in": "cf"},
        ],
    })
    catalog = _make_catalog()
    with pytest.raises(BuildError, match="unknown flow 'does_not_exist'"):
        build(flow, catalog)


def test_build_data_cycle_detected():
    """Cycle in the data subgraph."""
    from rayflow.nodes.decorators import ray_node, Input, Output

    @ray_node
    class NodeA:
        x = Input("int", default=0)
        y = Output("int")

        def run(self, x: int) -> dict:
            return {"y": x}

    @ray_node
    class NodeB:
        x = Input("int", default=0)
        y = Output("int")

        def run(self, x: int) -> dict:
            return {"y": x}

    reset_catalog()
    catalog = get_catalog()
    catalog.register(NodeA)
    catalog.register(NodeB)

    flow = load_flow({
        "name": "cycle",
        "nodes": [
            {"id": "start", "type": "OnStart"},
            {"id": "a", "type": "NodeA", "inputs": {"x": "b.y"}},
            {"id": "b", "type": "NodeB", "inputs": {"x": "a.y"}},
            {"id": "out", "type": "FlowOutput", "exec_in": "start"},
        ],
    })
    with pytest.raises(BuildError, match="[Cc]ycle"):
        build(flow, catalog)
