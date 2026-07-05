"""Tests de la capa MCP curada (rayflow/mcp/server.py)."""
import copy
from typing import Any

import pytest
import ray
from fastmcp import Client

from rayflow.nodes.registry import reset_catalog
from rayflow.mcp.server import create_mcp
from tests import entry_fixtures


@pytest.fixture(autouse=True)
def ray_init():
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, namespace="rayflow")
    reset_catalog()
    entry_fixtures.register()
    yield


@pytest.fixture
def flows_dir(tmp_path, monkeypatch):
    import rayflow.editor.storage as storage_mod
    monkeypatch.setattr(storage_mod, "flows_path", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def custom_nodes_dir(tmp_path, monkeypatch):
    """Isolates custom_nodes_path() (cwd-relative) in a temp dir and clears
    any cached custom_nodes.* modules so the catalog re-imports fresh."""
    import sys
    (tmp_path / "custom_nodes").mkdir()
    monkeypatch.chdir(tmp_path)
    for key in list(sys.modules):
        if key == "custom_nodes" or key.startswith("custom_nodes."):
            sys.modules.pop(key)
    yield tmp_path


@pytest.fixture
def mcp():
    return create_mcp()


SUMA = {
    "name": "suma",
    "outputs": {"resultado": "int"},
    "nodes": [
        {"id": "entry", "type": "EntryXY"},
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
                     "run_flow", "test_flow", "flow_catalog"):
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
    # FlowOutput, Parallel, and CallFlow still expose dynamic pin metadata;
    # OnStart no longer does (its pins are statically declared now).
    assert by_type["FlowOutput"]["dynamic"]["inputs_from"] == "flow.outputs"
    assert by_type["Parallel"]["dynamic"]["exec_outputs_pattern"] == "branch_N"


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


DOUBLE_SRC = (
    "from rayflow.nodes.decorators import engine_node, ExecContext, "
    "ExecInput, ExecOutput, Input, Output\n\n"
    "@engine_node\n"
    "class DoubleIt:\n"
    "    exec_in = ExecInput()\n"
    "    value = Input(\"int\", default=0)\n"
    "    result = Output(\"int\")\n"
    "    exec_out = ExecOutput()\n\n"
    "    async def run(self, ctx: ExecContext, value: int) -> None:\n"
    "        ctx.set_output(\"result\", value * 2)\n"
    "        await ctx.fire(\"exec_out\")\n"
)

DOUBLE_FLOW: dict[str, Any] = {
    "name": "double_flow",
    "outputs": {"y": "int"},
    "nodes": [
        {"id": "entry", "type": "EntryX"},
        {"id": "d", "type": "DoubleIt", "exec_in": "entry", "inputs": {"value": "entry.x"}},
        {"id": "exit", "type": "FlowOutput", "exec_in": "d", "inputs": {"y": "d.result"}},
    ],
}


async def test_custom_node_lifecycle_hot_reloads_without_restart(mcp, custom_nodes_dir):
    async with Client(mcp) as c:
        assert (await c.call_tool("list_custom_nodes", {})).data == []

        created = (await c.call_tool(
            "create_custom_node", {"name": "DoubleIt", "source": DOUBLE_SRC}
        )).data
        assert created["created"] is True
        assert "DoubleIt" in created["custom_nodes"]

        # No server restart, no explicit reload call: list_nodes sees it immediately.
        types = {n["type"] for n in (await c.call_tool("list_nodes", {})).data}
        assert "DoubleIt" in types

        src = (await c.call_tool("get_custom_node_source", {"name": "DoubleIt"})).data
        assert "value * 2" in src["source"]

        updated_src = DOUBLE_SRC.replace("value * 2", "value * 10")
        saved = (await c.call_tool(
            "update_custom_node_source", {"name": "DoubleIt", "source": updated_src}
        )).data
        assert saved["saved"] is True

        deleted = (await c.call_tool("delete_custom_node", {"name": "DoubleIt"})).data
        assert deleted["deleted"] is True
        assert (await c.call_tool("list_custom_nodes", {})).data == []


async def test_create_custom_node_rejects_duplicate_and_bad_syntax(mcp, custom_nodes_dir):
    async with Client(mcp) as c:
        await c.call_tool("create_custom_node", {"name": "DoubleIt", "source": DOUBLE_SRC})
        dup = (await c.call_tool(
            "create_custom_node", {"name": "DoubleIt", "source": DOUBLE_SRC}
        )).data
        assert "error" in dup

        bad = (await c.call_tool(
            "create_custom_node", {"name": "Broken", "source": "def bad(:\n"}
        )).data
        assert "error" in bad


async def test_update_flow_unloads_stale_loaded_graph(mcp, flows_dir, custom_nodes_dir):
    """Regression test: without unloading on update, run_flow/test_flow would
    silently keep executing the OLD graph after update_flow, because they
    skip reloading a flow that's already loaded."""
    async with Client(mcp) as c:
        await c.call_tool("create_custom_node", {"name": "DoubleIt", "source": DOUBLE_SRC})
        # create_custom_node hot-reloads the catalog (reset_catalog() + a fresh
        # get_catalog() inside _reload_catalog), which wipes the test-only entry
        # fixtures registered by the ray_init autouse fixture — re-register them
        # before wiring DOUBLE_FLOW's "EntryX" entry.
        entry_fixtures.register()
        await c.call_tool("create_flow", {"flow": DOUBLE_FLOW})

        first = (await c.call_tool("run_flow", {"name": "double_flow", "inputs": {"x": 5}})).data
        assert first["outputs"] == {"y": 10}  # loads the flow as a side effect

        changed = copy.deepcopy(DOUBLE_FLOW)
        changed["nodes"][1]["inputs"] = {"value": 999}  # ignore entry.x now
        await c.call_tool("update_flow", {"name": "double_flow", "flow": changed})

        second = (await c.call_tool("run_flow", {"name": "double_flow", "inputs": {"x": 5}})).data
        assert second["outputs"] == {"y": 1998}  # 999 * 2, NOT the stale 10


async def test_unload_flow_reports_whether_it_was_loaded(mcp, flows_dir):
    async with Client(mcp) as c:
        await c.call_tool("create_flow", {"flow": SUMA})
        # A previous test in this module may have left "suma" loaded in Ray
        # (nothing tears down loaded flows between tests) — force a clean
        # unloaded baseline before asserting on was_loaded's value.
        await c.call_tool("unload_flow", {"name": "suma"})

        not_loaded = (await c.call_tool("unload_flow", {"name": "suma"})).data
        assert not_loaded["was_loaded"] is False

        await c.call_tool("run_flow", {"name": "suma", "inputs": {"x": 1, "y": 1}})
        was_loaded = (await c.call_tool("unload_flow", {"name": "suma"})).data
        assert was_loaded["was_loaded"] is True


async def test_run_flow_trace_returns_ordered_node_events(mcp, flows_dir):
    async with Client(mcp) as c:
        await c.call_tool("create_flow", {"flow": SUMA})
        r = (await c.call_tool(
            "run_flow", {"name": "suma", "inputs": {"x": 2, "y": 3}, "trace": True}
        )).data
        assert r["outputs"] == {"resultado": 5}
        assert r["trace"], "trace should not be empty when trace=True"
        assert all(e["event"] in ("node_start", "node_done", "edge_fire") for e in r["trace"])


FRONTEND_NODE_SRC = """\
from rayflow.nodes.decorators import entry_node, ExecOutput, Input

@entry_node
class WithFrontend:
    frontend = "with_frontend_ui"
    message = Input("str")
    exec_out = ExecOutput()

@entry_node
class WithoutFrontend:
    message = Input("str")
    exec_out = ExecOutput()
"""


@pytest.fixture
async def mcp_with_frontend_node(mcp, custom_nodes_dir):
    """Registers WithFrontend (declares `frontend = "with_frontend_ui"`) and
    WithoutFrontend (doesn't) as real custom nodes via create_custom_node,
    the same hot-reload path a remote MCP client would use — this keeps the
    node's module importable (in sys.modules) afterwards, which
    _resolve_frontend_bundle_dir needs (inspect.getfile) to find the
    bundle's sibling directory. Mirrors client_with_frontend_node in
    tests/test_editor.py, but built through the MCP tool instead of writing
    the file directly, since that's the realistic path being tested here."""
    async with Client(mcp) as c:
        created = (await c.call_tool(
            "create_custom_node", {"name": "frontend_nodes", "source": FRONTEND_NODE_SRC}
        )).data
        assert created["created"] is True
    return mcp


async def test_get_entry_frontend_no_frontend_declared(mcp_with_frontend_node):
    async with Client(mcp_with_frontend_node) as c:
        r = (await c.call_tool("get_entry_frontend", {"node_type": "WithoutFrontend"})).data
    assert "error" in r
    assert "frontend" in r["error"]


async def test_get_entry_frontend_unknown_node_type(mcp_with_frontend_node):
    async with Client(mcp_with_frontend_node) as c:
        r = (await c.call_tool("get_entry_frontend", {"node_type": "NoExiste"})).data
    assert "error" in r


async def test_get_entry_frontend_bundle_dir_missing(mcp_with_frontend_node):
    async with Client(mcp_with_frontend_node) as c:
        r = (await c.call_tool("get_entry_frontend", {"node_type": "WithFrontend"})).data
    assert r["exists"] is False
    assert r["html"] is None


async def test_update_and_delete_entry_frontend(mcp_with_frontend_node, custom_nodes_dir):
    html = "<!doctype html><html><body>hi</body></html>"
    async with Client(mcp_with_frontend_node) as c:
        saved = (await c.call_tool(
            "update_entry_frontend", {"node_type": "WithFrontend", "html": html}
        )).data
        assert saved["saved"] is True

        bundle_dir = custom_nodes_dir / "custom_nodes" / "with_frontend_ui"
        assert (bundle_dir / "index.html").read_text(encoding="utf-8") == html

        got = (await c.call_tool("get_entry_frontend", {"node_type": "WithFrontend"})).data
        assert got == {
            "node_type": "WithFrontend",
            "bundle_dir": str(bundle_dir),
            "exists": True,
            "html": html,
        }

        overwritten = (await c.call_tool(
            "update_entry_frontend", {"node_type": "WithFrontend", "html": "<p>new</p>"}
        )).data
        assert overwritten["saved"] is True
        assert (bundle_dir / "index.html").read_text(encoding="utf-8") == "<p>new</p>"

        deleted = (await c.call_tool("delete_entry_frontend", {"node_type": "WithFrontend"})).data
        assert deleted["deleted"] is True
        assert not (bundle_dir / "index.html").exists()
        assert bundle_dir.exists()  # the bundle directory itself is left in place

        redelete = (await c.call_tool("delete_entry_frontend", {"node_type": "WithFrontend"})).data
        assert "error" in redelete


async def test_update_entry_frontend_rejects_empty_html_and_no_frontend_declared(mcp_with_frontend_node):
    async with Client(mcp_with_frontend_node) as c:
        empty = (await c.call_tool(
            "update_entry_frontend", {"node_type": "WithFrontend", "html": "   "}
        )).data
        assert "error" in empty

        no_frontend = (await c.call_tool(
            "update_entry_frontend", {"node_type": "WithoutFrontend", "html": "<p>x</p>"}
        )).data
        assert "error" in no_frontend


async def test_serve_and_stop_flow_events(mcp, flows_dir):
    listener = {
        "name": "listener",
        "events": ["ping"],
        "outputs": {},
        "nodes": [
            {"id": "on_ping", "type": "OnEvent", "inputs": {"event_name": "ping"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "on_ping"},
        ],
    }
    async with Client(mcp) as c:
        await c.call_tool("create_flow", {"flow": listener})
        served = (await c.call_tool("serve_flow_events", {"name": "listener"})).data
        assert served["graph_id"] == "listener"

        stopped = (await c.call_tool(
            "stop_flow_events", {"name": "listener", "graph_id": served["graph_id"]}
        )).data
        assert stopped["stopped"] is True
