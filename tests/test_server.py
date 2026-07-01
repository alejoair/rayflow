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


COUNTER = {
    "name": "counter",
    "outputs": {"count": "int"},
    "variables": [{"name": "n", "type": "int", "default": 0}],
    "nodes": [
        {"id": "entry", "type": "OnStart"},
        {"id": "get_n", "type": "Get", "inputs": {"variable_name": "n"}},
        {"id": "add", "type": "Add", "exec_in": "entry", "inputs": {"a": "get_n.value", "b": 1}},
        {"id": "set_n", "type": "Set", "exec_in": "add", "inputs": {"variable_name": "n", "value": "add.result"}},
        {"id": "exit", "type": "FlowOutput", "exec_in": "set_n", "inputs": {"count": "add.result"}},
    ],
}


def test_graphstate_persists_across_requests():
    """Regression test: /flows/{name}/run used to route through the one-shot
    rayflow.api.run() (load -> execute -> unload on every single request),
    destroying the flow's GraphState after each call. A variable this flow
    increments would silently reset to its default every request instead of
    accumulating. The fix loads once (in create_app) and reuses that same
    graph across requests, isolated per-request only by run_id/RunContext."""
    served = load_served_flows([COUNTER])
    client = TestClient(create_app(served))

    assert client.post("/flows/counter/run", json={}).json() == {"count": 1}
    assert client.post("/flows/counter/run", json={}).json() == {"count": 2}
    assert client.post("/flows/counter/run", json={}).json() == {"count": 3}


ECHO_REQUEST = {
    "name": "echo_request",
    "outputs": {"headers": "dict", "query": "dict", "body": "Any", "method": "str"},
    "nodes": [
        {"id": "entry", "type": "OnStart"},
        {"id": "exit", "type": "FlowOutput", "exec_in": "entry", "inputs": {
            "headers": "entry.headers", "query": "entry.query",
            "body": "entry.body", "method": "entry.method",
        }},
    ],
}


def test_onstart_exposes_the_http_request():
    """Every served flow's trigger IS the HTTP request — OnStart always
    exposes headers/query/body/method, regardless of the flow's declared
    `inputs`."""
    served = load_served_flows([ECHO_REQUEST])
    client = TestClient(create_app(served))

    r = client.post(
        "/flows/echo_request/run?foo=bar",
        json={"hello": "world"},
        headers={"x-custom": "value123"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["headers"]["x-custom"] == "value123"
    assert data["query"] == {"foo": "bar"}
    assert data["body"] == {"hello": "world"}
    assert data["method"] == "POST"


CHECK_API_KEY_FLOW = {
    "name": "check_api_key",
    "outputs": {"status": "str"},
    "nodes": [
        {"id": "entry", "type": "OnStart"},
        {"id": "auth", "type": "_TestCheckApiKey", "exec_in": "entry", "inputs": {"headers": "entry.headers"}},
        {"id": "ok", "type": "FlowOutput", "exec_in": "auth.authorized", "inputs": {"status": "ok"}},
        {"id": "no", "type": "FlowOutput", "exec_in": "auth.denied", "inputs": {"status": "denied"}},
    ],
}


@pytest.fixture
def check_api_key_client():
    from rayflow.nodes.decorators import engine_node, ExecContext, ExecInput, ExecOutput, Input
    from rayflow.nodes.registry import get_catalog

    @engine_node
    class _TestCheckApiKey:
        exec_in = ExecInput()
        headers = Input("dict[str, str]", default={})
        authorized = ExecOutput()
        denied = ExecOutput()

        async def run(self, ctx: ExecContext, headers: dict) -> None:
            if headers.get("x-api-key") == "secret123":
                await ctx.fire("authorized")
            else:
                ctx.set_response_status(401)
                ctx.set_response_header("x-auth-error", "bad-key")
                await ctx.fire("denied")

    get_catalog().register(_TestCheckApiKey)
    served = load_served_flows([CHECK_API_KEY_FLOW])
    return TestClient(create_app(served))


def test_ctx_set_response_status_reaches_the_real_http_response(check_api_key_client):
    r = check_api_key_client.post("/flows/check_api_key/run", json={})
    assert r.status_code == 401
    assert r.json() == {"status": "denied"}
    assert r.headers["x-auth-error"] == "bad-key"

    r = check_api_key_client.post(
        "/flows/check_api_key/run", json={}, headers={"x-api-key": "secret123"}
    )
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert "x-auth-error" not in r.headers  # isolated per run, no bleed from the denied request
