"""Tests del backend del editor visual (/editor/*)."""
import json
import pytest
import ray
from pathlib import Path
from fastapi.testclient import TestClient

from rayflow.nodes.registry import reset_catalog
from rayflow.server import load_served_flows, create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def ray_init():
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, namespace="rayflow")
    reset_catalog()
    yield


@pytest.fixture
def flows_dir(tmp_path, monkeypatch):
    """Redirige flows_path() a un directorio temporal para cada test."""
    import rayflow.editor.storage as storage_mod
    monkeypatch.setattr(storage_mod, "flows_path", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def client(flows_dir):
    served = load_served_flows([])
    return TestClient(create_app(served))


# Flows de ejemplo reutilizables
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

MINIMAL = {
    "name": "minimal",
    "nodes": [
        {"id": "start", "type": "OnStart"},
        {"id": "out", "type": "FlowOutput", "exec_in": "start"},
    ],
}

INVALID_TYPES = {
    "name": "bad_types",
    "nodes": [
        {"id": "entry", "type": "FlowInput"},
        {"id": "exit", "type": "FlowOutput", "exec_in": "entry",
         "inputs": {"x": "entry.x"}},
    ],
    "inputs": {"x": "TIPO_INVALIDO"},
    "outputs": {"x": "int"},
}


# ---------------------------------------------------------------------------
# GET /editor/nodes — catálogo de nodos
# ---------------------------------------------------------------------------

def test_list_nodes_devuelve_nodos_builtin(client):
    r = client.get("/editor/nodes")
    assert r.status_code == 200
    types = {n["type"] for n in r.json()}
    for expected in ("Add", "Branch", "ForEach", "Get", "Set", "CallFlow",
                     "FlowInput", "FlowOutput", "OnStart", "Parallel"):
        assert expected in types


def test_list_nodes_estructura_completa(client):
    r = client.get("/editor/nodes")
    add = next(n for n in r.json() if n["type"] == "Add")
    assert add["decorator"] == "ray_node"
    assert add["has_exec_in"] is True
    assert add["has_exec_out"] is True
    assert add["is_exec_node"] is True
    assert add["is_parallel"] is False
    assert add["exec_outputs"] == ["exec_out"]
    input_names = {p["name"] for p in add["inputs"]}
    assert input_names == {"a", "b"}
    output_names = {p["name"] for p in add["outputs"]}
    assert output_names == {"result"}


def test_list_nodes_pin_con_default(client):
    r = client.get("/editor/nodes")
    add = next(n for n in r.json() if n["type"] == "Add")
    pin_a = next(p for p in add["inputs"] if p["name"] == "a")
    assert pin_a["type"] == "int"
    assert pin_a["default"] == 0
    assert pin_a["required"] is False


def test_list_nodes_pure_node_sin_exec(client):
    r = client.get("/editor/nodes")
    get = next(n for n in r.json() if n["type"] == "Get")
    assert get["has_exec_in"] is False
    assert get["has_exec_out"] is False
    assert get["is_exec_node"] is False


def test_list_nodes_parallel_node(client):
    r = client.get("/editor/nodes")
    par = next(n for n in r.json() if n["type"] == "Parallel")
    assert par["decorator"] == "parallel_node"
    assert par["is_parallel"] is True


# ---------------------------------------------------------------------------
# GET /editor/nodes/{type}
# ---------------------------------------------------------------------------

def test_get_node_existente(client):
    r = client.get("/editor/nodes/Branch")
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "Branch"
    assert data["decorator"] == "engine_node"
    input_names = {p["name"] for p in data["inputs"]}
    assert "condition" in input_names


def test_get_node_inexistente(client):
    r = client.get("/editor/nodes/NoExiste")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /editor/types
# ---------------------------------------------------------------------------

def test_get_types(client):
    r = client.get("/editor/types")
    assert r.status_code == 200
    data = r.json()
    assert "int" in data["primitives"]
    assert "Any" in data["primitives"]
    assert len(data["generics"]) >= 2


# ---------------------------------------------------------------------------
# POST /editor/type-check
# ---------------------------------------------------------------------------

def test_type_check_compatibles(client):
    r = client.post("/editor/type-check", json={"from_type": "int", "to_type": "int"})
    assert r.status_code == 200
    assert r.json()["compatible"] is True


def test_type_check_incompatibles(client):
    r = client.post("/editor/type-check", json={"from_type": "int", "to_type": "str"})
    assert r.status_code == 200
    assert r.json()["compatible"] is False


def test_type_check_any_es_compatible_con_todo(client):
    r = client.post("/editor/type-check", json={"from_type": "int", "to_type": "Any"})
    assert r.status_code == 200
    assert r.json()["compatible"] is True


def test_type_check_int_float_incompatibles(client):
    r = client.post("/editor/type-check", json={"from_type": "int", "to_type": "float"})
    assert r.status_code == 200
    assert r.json()["compatible"] is False


def test_type_check_genericos_compatibles(client):
    r = client.post("/editor/type-check", json={"from_type": "list[str]", "to_type": "list[str]"})
    assert r.status_code == 200
    assert r.json()["compatible"] is True


def test_type_check_genericos_incompatibles(client):
    r = client.post("/editor/type-check", json={"from_type": "list[int]", "to_type": "list[str]"})
    assert r.status_code == 200
    assert r.json()["compatible"] is False


def test_type_check_faltan_campos(client):
    r = client.post("/editor/type-check", json={"from_type": "int"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /editor/validate
# ---------------------------------------------------------------------------

def test_validate_flow_valido(client):
    r = client.post("/editor/validate", json=MINIMAL)
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True
    assert data["errors"] == []


def test_validate_flow_con_errores_de_tipo(client):
    r = client.post("/editor/validate", json=INVALID_TYPES)
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0


def test_validate_flow_tipo_nodo_desconocido(client):
    bad = {
        "name": "bad",
        "nodes": [{"id": "x", "type": "NodoQueNoExiste"}],
    }
    r = client.post("/editor/validate", json=bad)
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_validate_body_no_es_objeto(client):
    r = client.post("/editor/validate", json=[1, 2, 3])
    assert r.status_code == 400


def test_validate_flow_suma_completo(client):
    r = client.post("/editor/validate", json=SUMA)
    assert r.status_code == 200
    assert r.json()["valid"] is True


# ---------------------------------------------------------------------------
# CRUD de flows
# ---------------------------------------------------------------------------

def test_list_flows_vacio(client):
    r = client.get("/editor/flows")
    assert r.status_code == 200
    assert r.json()["flows"] == []


def test_create_flow(client):
    r = client.post("/editor/flows", json=MINIMAL)
    assert r.status_code == 201
    assert r.json()["name"] == "minimal"


def test_create_flow_aparece_en_list(client):
    client.post("/editor/flows", json=MINIMAL)
    r = client.get("/editor/flows")
    names = [f["name"] for f in r.json()["flows"]]
    assert "minimal" in names


def test_create_flow_conflicto(client):
    client.post("/editor/flows", json=MINIMAL)
    r = client.post("/editor/flows", json=MINIMAL)
    assert r.status_code == 409


def test_get_flow_existente(client):
    client.post("/editor/flows", json=SUMA)
    r = client.get("/editor/flows/suma")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "suma"
    assert data["inputs"] == {"x": "int", "y": "int"}


def test_get_flow_inexistente(client):
    r = client.get("/editor/flows/noexiste")
    assert r.status_code == 404


def test_update_flow(client):
    client.post("/editor/flows", json=MINIMAL)
    updated = {**MINIMAL, "version": "2"}
    r = client.put("/editor/flows/minimal", json=updated)
    assert r.status_code == 200
    assert r.json()["version"] == "2"
    # Persiste
    r2 = client.get("/editor/flows/minimal")
    assert r2.json()["version"] == "2"


def test_update_flow_nombre_distinto_falla(client):
    r = client.put("/editor/flows/minimal", json={**MINIMAL, "name": "otro"})
    assert r.status_code == 400


def test_update_flow_sin_nombre_en_body_usa_ruta(client):
    """El frontend puede omitir 'name' en el body; se toma del path."""
    sin_nombre = {k: v for k, v in MINIMAL.items() if k != "name"}
    r = client.put("/editor/flows/minimal", json=sin_nombre)
    assert r.status_code == 200
    assert r.json()["name"] == "minimal"


def test_delete_flow(client):
    client.post("/editor/flows", json=MINIMAL)
    r = client.delete("/editor/flows/minimal")
    assert r.status_code == 204
    assert client.get("/editor/flows/minimal").status_code == 404


def test_delete_flow_inexistente(client):
    r = client.delete("/editor/flows/noexiste")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Campo `ui` — metadatos del canvas
# ---------------------------------------------------------------------------

def test_ui_se_preserva_en_nodo(client):
    flow_con_ui = {
        **MINIMAL,
        "nodes": [
            {"id": "start", "type": "OnStart", "ui": {"x": 100, "y": 200}},
            {"id": "out", "type": "FlowOutput", "exec_in": "start",
             "ui": {"x": 400, "y": 200, "comment": "salida"}},
        ],
    }
    client.post("/editor/flows", json=flow_con_ui)
    r = client.get("/editor/flows/minimal")
    nodes = {n["id"]: n for n in r.json()["nodes"]}
    assert nodes["start"]["ui"] == {"x": 100, "y": 200}
    assert nodes["out"]["ui"]["comment"] == "salida"


def test_nodo_sin_ui_no_incluye_campo(client):
    client.post("/editor/flows", json=MINIMAL)
    r = client.get("/editor/flows/minimal")
    for node in r.json()["nodes"]:
        assert "ui" not in node


# ---------------------------------------------------------------------------
# POST /editor/flows/{name}/run — ejecución desde el editor
# ---------------------------------------------------------------------------

def test_run_flow_desde_editor(client):
    client.post("/editor/flows", json=SUMA)
    r = client.post("/editor/flows/suma/run", json={"x": 4, "y": 6})
    assert r.status_code == 200
    assert r.json()["resultado"] == 10


def test_run_flow_inexistente(client):
    r = client.post("/editor/flows/noexiste/run", json={})
    assert r.status_code == 404


def test_run_flow_body_no_es_objeto(client):
    client.post("/editor/flows", json=MINIMAL)
    r = client.post("/editor/flows/minimal/run", json=[1, 2])
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Custom nodes — aparecen en el catálogo y pasan validación
# ---------------------------------------------------------------------------

CUSTOM_NODE_SRC = """\
from rayflow.nodes.decorators import engine_node, ExecInput, ExecOutput, Input, Output, ExecContext

@engine_node
class Duplicate:
    exec_in = ExecInput()
    value = Input("int", default=0)
    doubled = Output("int")
    exec_out = ExecOutput()

    async def run(self, ctx, value: int) -> None:
        ctx.set_output("doubled", value * 2)
        await ctx.fire("exec_out")
"""

DUPLICATE_FLOW = {
    "name": "duplicate_flow",
    "inputs": {"n": "int"},
    "outputs": {"result": "int"},
    "nodes": [
        {"id": "entry", "type": "FlowInput"},
        {"id": "dup", "type": "Duplicate", "exec_in": "entry", "inputs": {"value": "entry.n"}},
        {"id": "exit", "type": "FlowOutput", "exec_in": "dup", "inputs": {"result": "dup.doubled"}},
    ],
}


@pytest.fixture
def client_with_custom_node(tmp_path, monkeypatch):
    """Client con un @engine_node custom cargado vía --nodes-dir."""
    import rayflow.editor.storage as storage_mod
    monkeypatch.setattr(storage_mod, "flows_path", lambda: tmp_path)

    node_dir = tmp_path / "extra_nodes"
    node_dir.mkdir()
    (node_dir / "my_nodes.py").write_text(CUSTOM_NODE_SRC, encoding="utf-8")

    reset_catalog()
    served = load_served_flows([], extra_node_dirs=[str(node_dir)])
    return TestClient(create_app(served))


def test_custom_node_aparece_en_catalogo(client_with_custom_node):
    r = client_with_custom_node.get("/editor/nodes")
    assert r.status_code == 200
    types = {n["type"] for n in r.json()}
    assert "Duplicate" in types


def test_custom_node_spec_correcta(client_with_custom_node):
    r = client_with_custom_node.get("/editor/nodes/Duplicate")
    assert r.status_code == 200
    data = r.json()
    assert data["decorator"] == "engine_node"
    assert data["has_exec_in"] is True
    input_names = {p["name"] for p in data["inputs"]}
    assert input_names == {"value"}
    output_names = {p["name"] for p in data["outputs"]}
    assert output_names == {"doubled"}


def test_custom_node_pasa_validacion(client_with_custom_node, tmp_path, monkeypatch):
    r = client_with_custom_node.post("/editor/validate", json=DUPLICATE_FLOW)
    assert r.status_code == 200
    assert r.json()["valid"] is True


def test_custom_engine_node_se_ejecuta(client_with_custom_node):
    """@engine_node custom corre en el driver — no depende de runtime_env de Ray."""
    client_with_custom_node.post("/editor/flows", json=DUPLICATE_FLOW)
    r = client_with_custom_node.post("/editor/flows/duplicate_flow/run", json={"n": 7})
    assert r.status_code == 200
    assert r.json()["result"] == 14


# ---------------------------------------------------------------------------
# Concurrencia — varios flows al mismo tiempo no se interfieren
# ---------------------------------------------------------------------------

def test_ejecuciones_concurrentes_aisladas(client):
    """Dos ejecuciones simultáneas del mismo flow devuelven resultados correctos."""
    import threading

    client.post("/editor/flows", json=SUMA)
    results = {}

    def run(key, x, y):
        r = client.post("/editor/flows/suma/run", json={"x": x, "y": y})
        results[key] = r.json()

    t1 = threading.Thread(target=run, args=("a", 3, 7))
    t2 = threading.Thread(target=run, args=("b", 10, 20))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert results["a"]["resultado"] == 10
    assert results["b"]["resultado"] == 30


# ---------------------------------------------------------------------------
# Eventos — serve-events y stop
# ---------------------------------------------------------------------------

EVENTO_FLOW = {
    "name": "receptor_evento",
    "events": ["editor/test_event"],
    "nodes": [
        {"id": "on", "type": "OnEvent", "inputs": {"event_name": "editor/test_event"}},
        {"id": "out", "type": "FlowOutput", "exec_in": "on"},
    ],
}


def test_serve_events_registra_flow(client):
    client.post("/editor/flows", json=EVENTO_FLOW)
    r = client.post("/editor/flows/receptor_evento/serve-events")
    assert r.status_code == 201
    data = r.json()
    assert "graph_id" in data
    assert data["flow"] == "receptor_evento"


def test_serve_events_flow_inexistente(client):
    r = client.post("/editor/flows/noexiste/serve-events")
    assert r.status_code == 404


def test_stop_events_desuscribe(client):
    client.post("/editor/flows", json=EVENTO_FLOW)
    r = client.post("/editor/flows/receptor_evento/serve-events")
    graph_id = r.json()["graph_id"]
    r2 = client.delete(f"/editor/flows/receptor_evento/serve-events/{graph_id}")
    assert r2.status_code == 204

