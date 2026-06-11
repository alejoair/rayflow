"""Tests de ejecución end-to-end con Ray."""
import pytest
import ray
import rayflow
from rayflow.nodes.registry import reset_catalog


@pytest.fixture(autouse=True)
def ray_init():
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, namespace="rayflow")
    reset_catalog()
    yield


def test_flow_suma():
    result = rayflow.run({"name": "suma", "inputs": {"a": "int", "b": "int"},
        "outputs": {"result": "int"}, "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "add", "type": "Add", "exec_in": "entry",
             "inputs": {"a": "entry.a", "b": "entry.b"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "add",
             "inputs": {"result": "add.result"}},
        ]}, a=3, b=4)
    assert result["result"] == 7


def test_fan_out_ambos_nodos_se_ejecutan():
    """Un exec output conectado a dos nodos — ambos deben ejecutarse."""
    from rayflow.nodes.decorators import ray_node, ExecContext, Input, Output, ExecInput, ExecOutput
    from rayflow.nodes.registry import get_catalog

    @ray_node
    class SetFlag:
        exec_in = ExecInput()
        flag_name = Input("str", default="")
        exec_out = ExecOutput()

        def run(self, ctx: ExecContext, flag_name: str) -> dict:
            ctx.fire("exec_out")
            return {}

    catalog = get_catalog()
    catalog.register(SetFlag)

    # entry dispara a nodo_a y nodo_b en paralelo (fan-out)
    result = rayflow.run({
        "name": "fanout",
        "outputs": {"meta_a": "dict", "meta_b": "dict"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "nodo_a", "type": "SetFlag", "exec_in": "entry",
             "inputs": {"flag_name": "a"}},
            {"id": "nodo_b", "type": "SetFlag", "exec_in": "entry",
             "inputs": {"flag_name": "b"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": ["nodo_a", "nodo_b"],
             "inputs": {"meta_a": "nodo_a.meta", "meta_b": "nodo_b.meta"}},
        ],
    })
    assert result["meta_a"]["id"] == "nodo_a"
    assert result["meta_b"]["id"] == "nodo_b"


def test_parallel_fork_join():
    """Nodo Parallel lanza branch_0 y branch_1 simultáneamente, joined al terminar."""
    result = rayflow.run({
        "name": "parallel_test",
        "outputs": {"sum_a": "int", "sum_b": "int"},
        "nodes": [
            {"id": "entry", "type": "FlowInput",
             "inputs": {}},
            {"id": "par", "type": "Parallel", "exec_in": "entry"},
            {"id": "add_a", "type": "Add", "exec_in": "par.branch_0",
             "inputs": {"a": 10, "b": 5}},
            {"id": "add_b", "type": "Add", "exec_in": "par.branch_1",
             "inputs": {"a": 20, "b": 3}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "par.joined",
             "inputs": {"sum_a": "add_a.result", "sum_b": "add_b.result"}},
        ],
    })
    assert result["sum_a"] == 15
    assert result["sum_b"] == 23


def test_parallel_con_foreach_en_rama():
    """Parallel con @engine_node (ForEach) dentro de una rama — aislamiento correcto."""
    result = rayflow.run({
        "name": "parallel_foreach",
        "inputs": {"items": "list"},
        "outputs": {"done": "dict"},
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "par", "type": "Parallel", "exec_in": "entry"},
            {"id": "foreach", "type": "ForEach", "exec_in": "par.branch_0",
             "inputs": {"array": "entry.items"}},
            {"id": "add_elem", "type": "Add", "exec_in": "foreach.loop_body",
             "inputs": {"a": "foreach.element", "b": 0}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "par.joined",
             "inputs": {"done": "par.meta"}},
        ],
    }, items=[1, 2, 3])
    assert result["done"]["type"] == "Parallel"
