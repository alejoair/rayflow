"""Tests for the REST API (rayflow serve)."""
import pytest
import ray
from fastapi.testclient import TestClient

from rayflow.nodes.registry import reset_catalog
from rayflow.server import load_served_flows, create_app
from rayflow.registry import clear_served


@pytest.fixture(autouse=True)
def ray_init():
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, namespace="rayflow")
    reset_catalog()
    clear_served()
    yield
    clear_served()


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
    # Inputs are derived from the entry node's declared Input pins.
    # EntryXY declares x and y as int (required).
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


def test_run_404_for_unserved_editor_flow(tmp_path, monkeypatch):
    """POST /flows/{name}/run on a flow that exists in the editor's storage
    but has NOT been served (POST /editor/flows/{name}/load) returns 404.
    There's no implicit on-demand loading from /run anymore — "served" =
    "explicitly loaded" (via --file or POST /editor/flows/{name}/load)."""
    import rayflow.editor.storage as storage_mod
    monkeypatch.setattr(storage_mod, "flows_path", lambda: tmp_path)

    served = load_served_flows([])
    client = TestClient(create_app(served))

    client.post("/editor/flows", json=SUMA)
    r = client.post("/flows/suma/run", json={"x": 4, "y": 6})
    assert r.status_code == 404


def test_editor_load_then_run_succeeds(tmp_path, monkeypatch):
    """After POST /editor/flows/{name}/load, the flow is served: /run works."""
    import rayflow.editor.storage as storage_mod
    monkeypatch.setattr(storage_mod, "flows_path", lambda: tmp_path)

    served = load_served_flows([])
    client = TestClient(create_app(served))

    client.post("/editor/flows", json=SUMA)
    r_load = client.post("/editor/flows/suma/load")
    assert r_load.status_code == 200
    r_run = client.post("/flows/suma/run", json={"x": 4, "y": 6})
    assert r_run.status_code == 200
    assert r_run.json() == {"resultado": 10}


def test_editor_load_serves_ui(tmp_path, monkeypatch):
    """A flow loaded via POST /editor/flows/{name}/load exposes its /ui
    bundle (if the entry declares `frontend`). This is the core of the
    unified contract — UI is no longer --file-only."""
    import rayflow.editor.storage as storage_mod
    monkeypatch.setattr(storage_mod, "flows_path", lambda: tmp_path)

    served = load_served_flows([])
    client = TestClient(create_app(served))

    client.post("/editor/flows", json=CHAT_FLOW)
    r_load = client.post("/editor/flows/chat/load")
    assert r_load.status_code == 200
    r_ui = client.get("/flows/chat/ui/")
    assert r_ui.status_code == 200
    assert "text/html" in r_ui.headers["content-type"]
    assert "Rayflow Chat" in r_ui.text


def test_unload_removes_ui(tmp_path, monkeypatch):
    """DELETE /editor/flows/{name}/load removes the flow from the registry,
    so /flows/{name}/ui 404s afterwards."""
    import rayflow.editor.storage as storage_mod
    monkeypatch.setattr(storage_mod, "flows_path", lambda: tmp_path)

    served = load_served_flows([])
    client = TestClient(create_app(served))

    client.post("/editor/flows", json=CHAT_FLOW)
    client.post("/editor/flows/chat/load")
    assert client.get("/flows/chat/ui/").status_code == 200
    client.delete("/editor/flows/chat/load")
    assert client.get("/flows/chat/ui/").status_code == 404


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


# ---------------------------------------------------------------------------
# /flows/{name}/ui — frontend bundle for entry nodes that declare `frontend`
# ---------------------------------------------------------------------------

CHAT_FLOW = {
    "name": "chat",
    "outputs": {"reply": "str"},
    "nodes": [
        {"id": "entry", "type": "ChatTrigger"},
        {"id": "exit", "type": "FlowOutput", "exec_in": "entry",
         "inputs": {"reply": "entry.message_out"}},
    ],
}


def test_chat_flow_ui_serves_the_bundle():
    """A served flow whose entry node declares `frontend` gets its bundle
    mounted at /flows/{name}/ui."""
    served = load_served_flows([CHAT_FLOW])
    client = TestClient(create_app(served))

    r = client.get("/flows/chat/ui/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    # The ChatTrigger bundle's page contains the chat wiring.
    assert "Rayflow Chat" in r.text


def test_flow_without_frontend_returns_404_for_ui(client):
    """A flow whose entry has no `frontend` (OnStart via the FlowInput alias
    here) does not mount /ui — requesting it 404s."""
    r = client.get("/flows/suma/ui/")
    assert r.status_code == 404


def test_chat_trigger_flow_runs_end_to_end():
    """ChatTrigger is a fully-fledged entry: the flow builds, and a POST to
    /flows/chat/run with the declared `message` input flows through to the
    output, just like OnStart."""
    served = load_served_flows([CHAT_FLOW])
    client = TestClient(create_app(served))

    r = client.post("/flows/chat/run", json={"message": "hola"})
    assert r.status_code == 200
    assert r.json() == {"reply": "hola"}
