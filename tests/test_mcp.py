"""Tests de la capa MCP curada (rayflow/mcp/server.py)."""
import pytest
import ray
from fastmcp import Client

from rayflow.nodes.registry import reset_catalog
from rayflow.mcp.server import create_mcp


@pytest.fixture(autouse=True)
def ray_init():
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, namespace="rayflow")
    reset_catalog()
    yield


@pytest.fixture
def flows_dir(tmp_path, monkeypatch):
    import rayflow.editor.storage as storage_mod
    monkeypatch.setattr(storage_mod, "flows_path", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def mcp():
    return create_mcp({})


SUMA = {
    "name": "suma",
    "inputs": {"x": "int", "y": "int"},
    "outputs": {"resultado": "int"},
    "nodes": [
        {"id": "entry", "type": "FlowInput"},
        {"id": "add", "type": "Add", "exec_in": "entry",
         "inputs": {"a": "entry.x", "b": "entry.y"}},
        {"id": "exit", "type": "FlowOutput", "exec_in": "add",
         "inputs": {"resultado": "add.result"}},
    ],
}


async def test_lista_tools_curadas(mcp):
    async with Client(mcp) as c:
        names = {t.name for t in await c.list_tools()}
    for expected in ("get_guide", "list_nodes", "validate_flow", "create_flow",
                     "run_flow", "test_flow", "list_examples", "flow_catalog"):
        assert expected in names


async def test_validate_flow_recolecta_errores(mcp):
    flow = {
        "name": "broken",
        "nodes": [
            {"id": "a", "type": "Add", "inputs": {"a": "hola", "b": 1}},
            {"id": "a", "type": "Add", "inputs": {"a": 1, "b": 2}},
        ],
    }
    async with Client(mcp) as c:
        r = await c.call_tool("validate_flow", {"flow": flow})
    assert r.data["valid"] is False
    assert len(r.data["errors"]) >= 2


async def test_list_nodes_incluye_dynamic(mcp):
    async with Client(mcp) as c:
        r = await c.call_tool("list_nodes", {})
    by_type = {n["type"]: n for n in r.data}
    assert by_type["OnStart"]["dynamic"]["outputs_from"] == "flow.inputs"


async def test_crud_y_flow_catalog(mcp, flows_dir):
    async with Client(mcp) as c:
        await c.call_tool("create_flow", {"flow": SUMA})
        names = {f["name"] for f in (await c.call_tool("list_flows", {})).data}
        assert "suma" in names
        cat = (await c.call_tool("flow_catalog", {"name": "suma"})).data
        nodes = {n["id"]: n for n in cat["nodes"]}
        entry_outputs = {p["name"] for p in nodes["entry"]["outputs"]}
        assert {"x", "y"}.issubset(entry_outputs)


async def test_test_flow_verifica_outputs(mcp, flows_dir):
    async with Client(mcp) as c:
        await c.call_tool("create_flow", {"flow": SUMA})
        r = await c.call_tool("test_flow", {
            "name": "suma", "inputs": {"x": 2, "y": 3},
            "expected_outputs": {"resultado": 5},
        })
    assert r.data["passed"] is True


async def test_examples_disponibles(mcp):
    async with Client(mcp) as c:
        ex = (await c.call_tool("list_examples", {})).data
        assert any(e["name"] == "branch_demo" for e in ex)
        full = (await c.call_tool("get_example", {"name": "suma"})).data
        assert full["name"] == "suma"
