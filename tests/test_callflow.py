"""Tests for CallFlow — shared and isolated subgraphs."""
import pytest
import ray
import rayflow
from rayflow.nodes.registry import reset_catalog
from tests.helpers import run_once
from tests import entry_fixtures


@pytest.fixture(autouse=True)
def ray_init():
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, namespace="rayflow")
    reset_catalog()
    entry_fixtures.register()
    yield


# Helper flow used as a subgraph in several tests.
# Uses EntryAB (an entry declaring a/b as Input) — auto-passthrough mirrors
# them as outputs so the subgraph can cable entry.a/entry.b.
SUBFLOW_SUM = {
    "name": "subflow_sum",
    "outputs": {"total": "int"},
    "nodes": [
        {"id": "entry", "type": "EntryAB"},
        {"id": "add", "type": "Add", "exec_in": "entry",
         "inputs": {"a": "entry.a", "b": "entry.b"}},
        {"id": "exit", "type": "FlowOutput", "exec_in": "add",
         "inputs": {"total": "add.result"}},
    ],
}

# Helper flow that writes a variable (for shared mode)
SUBFLOW_SET_VAR = {
    "name": "subflow_set_var",
    "nodes": [
        {"id": "entry", "type": "OnStart"},
        {"id": "set", "type": "Set", "exec_in": "entry",
         "inputs": {"variable_name": "counter", "value": 42}},
        {"id": "exit", "type": "FlowOutput", "exec_in": "set",
         "inputs": {}},
    ],
}


def test_callflow_isolated_inputs_outputs():
    """An isolated CallFlow receives inputs and returns outputs under 'result'."""
    result = run_once({
        "name": "parent",
        "inputs": {"x": "int", "y": "int"},
        "outputs": {"answer": "dict"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "sub", "type": "CallFlow",
             "exec_in": "entry",
             "inputs": {"flow": SUBFLOW_SUM, "isolated": True,
                        "a": "entry.x", "b": "entry.y"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "sub",
             "inputs": {"answer": "sub.result"}},
        ],
    }, x=3, y=7)

    assert result["answer"]["total"] == 10


def test_callflow_meta_flow_is_the_declaring_subflow():
    """meta['flow'] reflects the flow that DECLARED the node, not the root flow.

    A node from the subflow reports the subflow's name; one from the root
    reports the root's. meta['id'] is the flat path ("sub/add").
    """
    result = run_once({
        "name": "my_parent",
        "inputs": {"x": "int"},
        "outputs": {"sub_meta": "dict", "root_meta": "dict"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "sub", "type": "CallFlow", "exec_in": "entry",
             "inputs": {"flow": SUBFLOW_SUM, "isolated": True,
                        "a": "entry.x", "b": "entry.x"}},
            {"id": "dbl", "type": "Add", "exec_in": "sub",
             "inputs": {"a": "entry.x", "b": "entry.x"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "dbl",
             "inputs": {"sub_meta": "sub/add.meta", "root_meta": "dbl.meta"}},
        ],
    }, x=5)
    # The 'add' node lives inside the subflow → subflow's name, path-qualified id.
    assert result["sub_meta"]["flow"] == "subflow_sum"
    assert result["sub_meta"]["id"] == "sub/add"
    # The 'dbl' node belongs to the root flow.
    assert result["root_meta"]["flow"] == "my_parent"
    assert result["root_meta"]["id"] == "dbl"


def test_callflow_isolated_does_not_pollute_parent_state():
    """An isolated CallFlow can't see or modify the parent's variables."""
    result = run_once({
        "name": "parent",
        "variables": [{"name": "val", "type": "int", "default": 99}],
        "outputs": {"parent_val": "Any"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            # the subflow tries set_variable("val", 0) but in its own GraphState
            {"id": "sub", "type": "CallFlow",
             "exec_in": "entry",
             "inputs": {"flow": SUBFLOW_SET_VAR, "isolated": True}},
            {"id": "get_val", "type": "Get",
             "inputs": {"variable_name": "val"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "sub",
             "inputs": {"parent_val": "get_val.value"}},
        ],
    })
    # The parent's variable is still 99 — the isolated subflow never touched it.
    assert result["parent_val"] == 99


def test_callflow_shared_modifies_parent_variable():
    """A shared CallFlow can write to the parent's variables."""
    result = run_once({
        "name": "parent",
        "variables": [{"name": "counter", "type": "int", "default": 0}],
        "outputs": {"final": "Any"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "sub", "type": "CallFlow",
             "exec_in": "entry",
             "inputs": {"flow": SUBFLOW_SET_VAR, "isolated": False}},
            {"id": "get_counter", "type": "Get",
             "inputs": {"variable_name": "counter"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "sub",
             "inputs": {"final": "get_counter.value"}},
        ],
    })
    # The shared subflow wrote 42 into the parent's variable.
    assert result["final"] == 42


def test_callflow_inside_parallel_branch():
    """A CallFlow inside a Parallel branch is orchestrated correctly.

    Regression: now that the branch executor is merged into FlowEngine, a
    Parallel branch reuses all of the _fire_* logic (including CallFlow).
    Previously, the separate branch executor didn't know how to orchestrate
    CallFlow.
    """
    sub = {
        "name": "s",
        "outputs": {"t": "int"},
        "nodes": [
            {"id": "e", "type": "EntryAB"},
            {"id": "add", "type": "Add", "exec_in": "e",
             "inputs": {"a": "e.a", "b": "e.b"}},
            {"id": "x", "type": "FlowOutput", "exec_in": "add",
             "inputs": {"t": "add.result"}},
        ],
    }
    result = run_once({
        "name": "p",
        "inputs": {"n": "int"},
        "outputs": {"r": "dict"},
        "nodes": [
            {"id": "e", "type": "OnStart"},
            {"id": "par", "type": "Parallel", "exec_in": "e"},
            {"id": "cf", "type": "CallFlow", "exec_in": "par.branch_0",
             "inputs": {"flow": sub, "isolated": True, "a": "e.n", "b": "e.n"}},
            {"id": "noop", "type": "Set", "exec_in": "par.branch_1",
             "inputs": {"variable_name": "dummy", "value": 1}},
            {"id": "x", "type": "FlowOutput", "exec_in": "par.joined",
             "inputs": {"r": "cf.result"}},
        ],
    }, n=4)
    assert result["r"]["t"] == 8


def test_callflow_isolated_same_variable_does_not_collide():
    """Real isolation: parent and subflow with the SAME variable don't stomp each other.

    The isolated subflow writes its 'counter' into its own state namespace
    (state_path), so the parent's 'counter' stays untouched.
    """
    sub = {
        "name": "sub",
        "variables": [{"name": "counter", "type": "int", "default": 0}],
        "nodes": [
            {"id": "e", "type": "OnStart"},
            {"id": "s", "type": "Set", "exec_in": "e",
             "inputs": {"variable_name": "counter", "value": 7}},
            {"id": "x", "type": "FlowOutput", "exec_in": "s", "inputs": {}},
        ],
    }
    result = run_once({
        "name": "parent",
        "variables": [{"name": "counter", "type": "int", "default": 99}],
        "outputs": {"val": "Any"},
        "nodes": [
            {"id": "e", "type": "OnStart"},
            {"id": "sub", "type": "CallFlow", "exec_in": "e",
             "inputs": {"flow": sub, "isolated": True}},
            {"id": "g", "type": "Get", "inputs": {"variable_name": "counter"}},
            {"id": "x", "type": "FlowOutput", "exec_in": "sub",
             "inputs": {"val": "g.value"}},
        ],
    })
    # The isolated subflow did NOT touch the parent's counter.
    assert result["val"] == 99


def test_callflow_shared_same_variable_does_collide():
    """Shared mode: the subflow DOES stomp the parent's variable (same namespace)."""
    sub = {
        "name": "sub",
        "variables": [{"name": "counter", "type": "int", "default": 0}],
        "nodes": [
            {"id": "e", "type": "OnStart"},
            {"id": "s", "type": "Set", "exec_in": "e",
             "inputs": {"variable_name": "counter", "value": 7}},
            {"id": "x", "type": "FlowOutput", "exec_in": "s", "inputs": {}},
        ],
    }
    result = run_once({
        "name": "parent",
        "variables": [{"name": "counter", "type": "int", "default": 99}],
        "outputs": {"val": "Any"},
        "nodes": [
            {"id": "e", "type": "OnStart"},
            {"id": "sub", "type": "CallFlow", "exec_in": "e",
             "inputs": {"flow": sub, "isolated": False}},
            {"id": "g", "type": "Get", "inputs": {"variable_name": "counter"}},
            {"id": "x", "type": "FlowOutput", "exec_in": "sub",
             "inputs": {"val": "g.value"}},
        ],
    })
    assert result["val"] == 7


def test_callflow_nested():
    """Two CallFlows in sequence — each one receives the previous one's outputs via the result dict."""
    subflow_double = {
        "name": "double",
        "outputs": {"value": "int"},
        "nodes": [
            {"id": "entry", "type": "EntryN"},
            {"id": "add", "type": "Add", "exec_in": "entry",
             "inputs": {"a": "entry.n", "b": "entry.n"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "add",
             "inputs": {"value": "add.result"}},
        ],
    }

    result = run_once({
        "name": "parent",
        "inputs": {"x": "int"},
        "outputs": {"r1": "dict", "r2": "dict"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "sub1", "type": "CallFlow",
             "exec_in": "entry",
             "inputs": {"flow": subflow_double, "isolated": True, "n": "entry.x"}},
            {"id": "sub2", "type": "CallFlow",
             "exec_in": "sub1",
             "inputs": {"flow": subflow_double, "isolated": True, "n": "entry.x"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "sub2",
             "inputs": {"r1": "sub1.result", "r2": "sub2.result"}},
        ],
    }, x=5)

    assert result["r1"]["value"] == 10
    assert result["r2"]["value"] == 10
