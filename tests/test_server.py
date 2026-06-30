"""Tests for the REST API (rayflow serve)."""
import pytest
import ray
from fastapi.testclient import TestClient

from rayflow.nodes.registry import reset_catalog
from rayflow.server import load_served_flows, create_app


@pytest.fixture(autouse=True)
def ray_init():
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, namespace="rayflow")
    reset_catalog()
    yield


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


@pytest.fixture
def client():
    served = load_served_flows([SUMA])
    return TestClient(create_app(served))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_flows(client):
    r = client.get("/flows")
    assert r.status_code == 200
    flows = r.json()["flows"]
    assert len(flows) == 1
    assert flows[0]["name"] == "suma"
    assert flows[0]["inputs"] == {"x": {"type": "int", "required": True}, "y": {"type": "int", "required": True}}
    assert flows[0]["outputs"] == {"resultado": {"type": "int"}}


def test_flow_detail(client):
    r = client.get("/flows/suma")
    assert r.status_code == 200
    assert r.json()["name"] == "suma"


def test_flow_detail_404(client):
    r = client.get("/flows/nonexistent")
    assert r.status_code == 404


def test_run_flow(client):
    r = client.post("/flows/suma/run", json={"x": 3, "y": 7})
    assert r.status_code == 200
    assert r.json() == {"resultado": 10}


def test_run_flow_404(client):
    r = client.post("/flows/nonexistent/run", json={"x": 1})
    assert r.status_code == 404


def test_run_flow_body_is_not_an_object(client):
    r = client.post("/flows/suma/run", json=[1, 2, 3])
    assert r.status_code == 400


def test_duplicate_names_fail_to_load():
    with pytest.raises(ValueError, match="share the name"):
        load_served_flows([SUMA, dict(SUMA)])
