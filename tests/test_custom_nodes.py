"""Tests de nodos custom por convención (custom_nodes/ + flows/ en el cwd)."""
import sys
import textwrap

import pytest
import ray

import rayflow
from rayflow.nodes.registry import get_catalog, reset_catalog
from rayflow import workspace


CUSTOM_NODE_SRC = textwrap.dedent('''
    from rayflow.nodes.decorators import (
        ray_node, engine_node, ExecInput, ExecOutput, Input, Output, ExecContext,
    )

    @ray_node
    class Triple:
        exec_in = ExecInput()
        n = Input("int", default=0)
        result = Output("int")
        exec_out = ExecOutput()
        def run(self, ctx, n):
            ctx.fire("exec_out")
            return {"result": n * 3}

    @engine_node
    class Shout:
        exec_in = ExecInput()
        text = Input("str", default="")
        loud = Output("str")
        exec_out = ExecOutput()
        async def run(self, ctx, text):
            # set_output expone 'loud' ANTES del await fire, así el
            # subgrafo disparado por exec_out ya lo puede leer.
            ctx.set_output("loud", text.upper() + "!")
            await ctx.fire("exec_out")
''')

TRIPLE_FLOW = {
    "name": "triple_flow",
    "inputs": {"x": "int"},
    "outputs": {"r": "int"},
    "nodes": [
        {"id": "entry", "type": "OnStart"},
        {"id": "t", "type": "Triple", "exec_in": "entry", "inputs": {"n": "entry.x"}},
        {"id": "exit", "type": "FlowOutput", "exec_in": "t", "inputs": {"r": "t.result"}},
    ],
}


@pytest.fixture
def workspace_dir(tmp_path, monkeypatch):
    """Crea un workspace temporal con custom_nodes/ y flows/, y hace cwd ahí."""
    cn = tmp_path / "custom_nodes"
    cn.mkdir()
    (cn / "__init__.py").write_text("", encoding="utf-8")
    (cn / "mis_nodos.py").write_text(CUSTOM_NODE_SRC, encoding="utf-8")
    (tmp_path / "flows").mkdir()
    import json
    (tmp_path / "flows" / "triple_flow.json").write_text(
        json.dumps(TRIPLE_FLOW), encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, namespace="rayflow")
    # Limpiar módulos custom_nodes cacheados de runs anteriores para que
    # importlib.import_module() reimporte desde el nuevo cwd.
    for key in list(sys.modules):
        if key == "custom_nodes" or key.startswith("custom_nodes."):
            sys.modules.pop(key)
    reset_catalog()
    get_catalog()  # fuerza carga del catálogo desde el nuevo cwd
    yield tmp_path


def test_custom_nodes_descubiertos_por_convencion(workspace_dir):
    """get_catalog descubre Triple y Shout desde ./custom_nodes/."""
    cat = get_catalog()
    assert cat.get("Triple") is not None
    assert cat.get("Shout") is not None


def test_ensure_workspace_crea_carpetas(tmp_path, monkeypatch):
    """ensure_workspace crea custom_nodes/ (con __init__.py) y flows/."""
    monkeypatch.chdir(tmp_path)
    workspace.ensure_workspace()
    assert (tmp_path / "custom_nodes" / "__init__.py").exists()
    assert (tmp_path / "flows").exists()


def test_resolve_flow_por_nombre(workspace_dir):
    """resolve_flow encuentra flows/triple_flow.json por nombre."""
    path = workspace.resolve_flow("triple_flow")
    assert path.endswith("triple_flow.json")


def test_resolve_flow_inexistente(workspace_dir):
    with pytest.raises(FileNotFoundError):
        workspace.resolve_flow("no_existe")


def test_runtime_env_con_nodos(workspace_dir):
    """runtime_env apunta a custom_nodes/ cuando hay nodos custom."""
    env = workspace.runtime_env()
    assert env is not None
    assert "py_modules" in env
    assert env["py_modules"][0].endswith("custom_nodes")


def test_engine_node_custom_se_ejecuta(workspace_dir):
    """Un @engine_node custom (corre en el driver) funciona."""
    out = rayflow.run({
        "name": "shout_flow",
        "inputs": {"msg": "str"},
        "outputs": {"out": "str"},
        "nodes": [
            {"id": "e", "type": "OnStart"},
            {"id": "s", "type": "Shout", "exec_in": "e", "inputs": {"text": "e.msg"}},
            {"id": "x", "type": "FlowOutput", "exec_in": "s", "inputs": {"out": "s.loud"}},
        ],
    }, msg="hola")
    assert out == {"out": "HOLA!"}
