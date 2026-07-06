"""Tests for the node definition and discovery system."""
import subprocess
import sys
from unittest.mock import patch

import pytest
from rayflow.nodes.decorators import ray_node, engine_node, entry_node, ExecContext, Input, Output, ExecInput, ExecOutput, get_node_meta
from rayflow.nodes.loader import NodeCatalog
from rayflow.nodes.registry import get_catalog, reset_catalog
from rayflow.nodes.builtin.claude import invoke_claude_cli


def test_ray_node_decorator_extracts_meta():
    @ray_node
    class AddNode:
        exec_in = ExecInput()
        a = Input("int", default=0)
        b = Input("int", default=0)
        result = Output("int")
        exec_out = ExecOutput()

        def run(self, ctx: ExecContext, a: int, b: int) -> dict:
            ctx.fire("exec_out")
            return {"result": a + b}

    meta = get_node_meta(AddNode)
    assert meta is not None
    assert meta.name == "AddNode"
    assert meta.has_exec_in
    assert meta.has_exec_out
    assert meta.is_exec_node
    assert not meta.is_engine_node
    assert len(meta.inputs) == 2
    assert len(meta.outputs) == 1
    input_names = [p.name for p in meta.inputs]
    assert "a" in input_names
    assert "b" in input_names


def test_engine_node_decorator_extracts_meta():
    @engine_node
    class MyBranch:
        exec_in = ExecInput()
        condition = Input("bool", default=False)
        true = ExecOutput()
        false = ExecOutput()

        def run(self, ctx: ExecContext, condition: bool) -> dict:
            ctx.fire("true" if condition else "false")
            return {}

    meta = get_node_meta(MyBranch)
    assert meta is not None
    assert meta.is_engine_node
    assert meta.has_exec_in
    assert len(meta.exec_outputs) == 2


def test_engine_node_is_entry_defaults_false():
    @engine_node
    class PlainNode:
        exec_in = ExecInput()
        exec_out = ExecOutput()

        def run(self, ctx: ExecContext) -> dict:
            ctx.fire("exec_out")
            return {}

    meta = get_node_meta(PlainNode)
    assert meta is not None
    assert meta.is_entry is False


def test_engine_node_is_entry_extracted():
    @entry_node
    class MyTrigger:
        message = Input("str")
        exec_out = ExecOutput()

    meta = get_node_meta(MyTrigger)
    assert meta is not None
    assert meta.is_entry is True


def test_entry_node_rejects_exec_in():
    """@entry_node must not declare exec_in — nothing wires into an entry."""
    import pytest
    with pytest.raises(ValueError, match="exec_in"):
        @entry_node
        class BadEntry:
            exec_in = ExecInput()
            exec_out = ExecOutput()


def test_entry_node_requires_exec_out():
    """@entry_node must declare at least one ExecOutput."""
    import pytest
    with pytest.raises(ValueError, match="ExecOutput"):
        @entry_node
        class BadEntry:
            message = Input("str")


def test_frontend_flag_defaults_none_and_is_extracted():
    # Default: a node without `frontend` exposes None.
    @engine_node
    class NoFrontend:
        exec_in = ExecInput()
        exec_out = ExecOutput()

        def run(self, ctx: ExecContext) -> dict:
            ctx.fire("exec_out")
            return {}

    assert get_node_meta(NoFrontend).frontend is None

    # A node declaring `frontend` (typically an entry node) surfaces the value.
    @entry_node
    class UiTrigger:
        frontend = "ui_bundle"
        message = Input("str")
        exec_out = ExecOutput()

    meta = get_node_meta(UiTrigger)
    assert meta is not None
    assert meta.frontend == "ui_bundle"


def test_data_node_has_no_exec():
    @ray_node
    class MultiplyNode:
        x = Input("float", default=1.0)
        y = Input("float", default=1.0)
        result = Output("float")

        def run(self, x: float, y: float) -> dict:
            return {"result": x * y}

    meta = get_node_meta(MultiplyNode)
    assert not meta.has_exec_in
    assert not meta.has_exec_out
    assert not meta.is_exec_node


def test_input_default_values():
    @ray_node
    class NodeWithDefaults:
        name = Input("str", default="hello")
        count = Input("int", default=42)
        result = Output("str")

        def run(self, name: str, count: int) -> dict:
            return {"result": f"{name}:{count}"}

    meta = get_node_meta(NodeWithDefaults)
    name_pin = next(p for p in meta.inputs if p.name == "name")
    count_pin = next(p for p in meta.inputs if p.name == "count")
    assert name_pin.default == "hello"
    assert count_pin.default == 42
    assert not name_pin.required


def test_catalog_registers_builtin_nodes():
    reset_catalog()
    catalog = get_catalog()
    assert "OnStart" in catalog
    assert "FlowInput" in catalog
    assert "FlowOutput" in catalog
    assert "Branch" in catalog
    assert "Sequence" in catalog
    assert "ForEach" in catalog
    assert "Get" in catalog
    assert "Set" in catalog
    assert "OnEvent" in catalog
    assert "EmitEvent" in catalog
    assert "Claude" in catalog


def test_catalog_registers_claude_node():
    reset_catalog()
    catalog = get_catalog()
    entry = catalog.get("Claude")
    assert entry is not None, "Claude must be in the builtin catalog"
    _cls, meta = entry
    assert meta.category == "AI"
    assert meta.has_exec_in
    assert set(meta.exec_outputs) == {"success", "failure"}
    input_names = {p.name for p in meta.inputs}
    output_names = {p.name for p in meta.outputs}
    assert input_names == {
        "prompt", "agent", "model", "json_schema", "timeout_seconds",
        "working_directory", "resume_session_id",
    }
    assert output_names == {
        "result", "structured_output", "is_error", "error", "cost_usd", "session_id",
    }
    prompt_pin = next(p for p in meta.inputs if p.name == "prompt")
    assert prompt_pin.required


# --- ISSUE-0010: load_custom_nodes_package must not let one broken file take
# down the whole catalog; failures are scoped per file and recorded in
# NodeCatalog.load_errors (keyed by path.stem) instead of propagating or
# being silently swallowed. ---

@pytest.fixture
def isolated_custom_nodes_dir(tmp_path, monkeypatch):
    """Points custom_nodes_path() at a fresh tmp_path/custom_nodes/ and
    clears any cached `custom_nodes.*` modules so each test re-imports from
    scratch (same pattern as tests/test_mcp.py's custom_nodes_dir fixture)."""
    cn = tmp_path / "custom_nodes"
    cn.mkdir()
    (cn / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for key in list(sys.modules):
        if key == "custom_nodes" or key.startswith("custom_nodes."):
            sys.modules.pop(key)
    return cn


def test_load_custom_nodes_package_records_import_error(isolated_custom_nodes_dir):
    (isolated_custom_nodes_dir / "broken_import.py").write_text(
        "import this_module_does_not_exist_anywhere_xyz\n",
        encoding="utf-8",
    )
    catalog = NodeCatalog()
    catalog.load_custom_nodes_package()  # must not raise
    assert "broken_import" in catalog.load_errors
    assert "this_module_does_not_exist_anywhere_xyz" in catalog.load_errors["broken_import"]


def test_load_custom_nodes_package_records_entry_node_without_exec_output(isolated_custom_nodes_dir):
    (isolated_custom_nodes_dir / "bad_entry.py").write_text(
        "from rayflow.nodes.decorators import entry_node, Input\n\n\n"
        "@entry_node\n"
        "class BadEntry:\n"
        "    message = Input('str')\n",
        encoding="utf-8",
    )
    catalog = NodeCatalog()
    catalog.load_custom_nodes_package()  # must not raise
    assert "bad_entry" in catalog.load_errors
    assert "ExecOutput" in catalog.load_errors["bad_entry"]
    assert "BadEntry" not in catalog


def test_load_custom_nodes_package_records_duplicate_node_name(isolated_custom_nodes_dir):
    node_src = (
        "from rayflow.nodes.decorators import engine_node, ExecContext, ExecInput, ExecOutput\n\n\n"
        "@engine_node\n"
        "class DupNode:\n"
        "    exec_in = ExecInput()\n"
        "    exec_out = ExecOutput()\n\n"
        "    def run(self, ctx: ExecContext) -> dict:\n"
        "        ctx.fire('exec_out')\n"
        "        return {}\n"
    )
    # Sorted alphabetically by load_custom_nodes_package: dup_a loads first
    # and wins the name; dup_b loses and its error is recorded.
    (isolated_custom_nodes_dir / "dup_a.py").write_text(node_src, encoding="utf-8")
    (isolated_custom_nodes_dir / "dup_b.py").write_text(node_src, encoding="utf-8")
    catalog = NodeCatalog()
    catalog.load_custom_nodes_package()  # must not raise
    assert "dup_a" not in catalog.load_errors
    assert "dup_b" in catalog.load_errors
    assert "Duplicate node" in catalog.load_errors["dup_b"]
    # The winner is still registered and usable.
    assert "DupNode" in catalog
    entry = catalog.get("DupNode")
    assert entry is not None
    cls, _meta = entry
    assert cls.__module__ == "custom_nodes.dup_a"


def test_load_custom_nodes_package_valid_module_has_no_load_error(isolated_custom_nodes_dir):
    (isolated_custom_nodes_dir / "good_node.py").write_text(
        "from rayflow.nodes.decorators import engine_node, ExecContext, ExecInput, ExecOutput\n\n\n"
        "@engine_node\n"
        "class GoodNode:\n"
        "    exec_in = ExecInput()\n"
        "    exec_out = ExecOutput()\n\n"
        "    def run(self, ctx: ExecContext) -> dict:\n"
        "        ctx.fire('exec_out')\n"
        "        return {}\n",
        encoding="utf-8",
    )
    catalog = NodeCatalog()
    catalog.load_custom_nodes_package()
    assert catalog.load_errors == {}
    assert "GoodNode" in catalog


def test_catalog_registers_chat_trigger_with_frontend():
    reset_catalog()
    catalog = get_catalog()
    entry = catalog.get("ChatTrigger")
    assert entry is not None, "ChatTrigger must be in the builtin catalog"
    _cls, meta = entry
    assert meta.is_entry is True
    assert meta.frontend == "chat_trigger_frontend"
    # ChatTrigger declares `message` as Input and `message_out` as Output
    input_names = {p.name for p in meta.inputs}
    output_names = {p.name for p in meta.outputs}
    assert "message" in input_names
    assert "message_out" in output_names


# ---------------------------------------------------------------------------
# Claude node — invoke_claude_cli, exercised with subprocess.run mocked out.
# No real `claude` process is ever spawned in this test module.
# ---------------------------------------------------------------------------

def _fake_proc(stdout: str = "", stderr: str = "", returncode: int = 0):
    proc = subprocess.CompletedProcess(args=["claude"], returncode=returncode)
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


def test_invoke_claude_cli_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=5)):
        out = invoke_claude_cli(prompt="hi", timeout_seconds=5)
    assert out["is_error"] is True
    assert out["error"] == "timed out after 5s"
    assert out["result"] == ""
    assert out["structured_output"] == {}
    assert out["cost_usd"] == 0.0
    assert out["session_id"] == ""
    assert out["exec"] == "failure"


def test_invoke_claude_cli_binary_not_found():
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        out = invoke_claude_cli(prompt="hi")
    assert out["is_error"] is True
    assert out["error"] == "claude CLI not found in PATH"
    assert out["exec"] == "failure"


def test_invoke_claude_cli_argument_parsing_failure():
    # Empty stdout + stderr content: the CLI failed to parse its own args
    # (e.g. bad --agent name or malformed --json-schema) before producing
    # an envelope.
    with patch("subprocess.run", return_value=_fake_proc(stdout="", stderr="error: unknown agent 'nope'\n", returncode=1)):
        out = invoke_claude_cli(prompt="hi", agent="nope")
    assert out["is_error"] is True
    assert out["error"] == "error: unknown agent 'nope'"
    assert out["exec"] == "failure"


def test_invoke_claude_cli_malformed_json():
    with patch("subprocess.run", return_value=_fake_proc(stdout="not json at all", stderr="")):
        out = invoke_claude_cli(prompt="hi")
    assert out["is_error"] is True
    assert "not json at all" in out["error"]
    assert out["exec"] == "failure"


def test_invoke_claude_cli_success():
    envelope = {
        "result": "OK",
        "is_error": False,
        "total_cost_usd": 0.0123,
        "session_id": "sess-abc",
    }
    import json
    with patch("subprocess.run", return_value=_fake_proc(stdout=json.dumps(envelope))):
        out = invoke_claude_cli(prompt="respond only with OK")
    assert out["is_error"] is False
    assert out["result"] == "OK"
    assert out["structured_output"] == {}
    assert out["error"] == ""
    assert out["cost_usd"] == 0.0123
    assert out["session_id"] == "sess-abc"
    assert out["exec"] == "success"


def test_invoke_claude_cli_success_with_structured_output():
    envelope = {
        "result": "{\"answer\": 42}",
        "is_error": False,
        "structured_output": {"answer": 42},
        "total_cost_usd": 0.02,
        "session_id": "sess-xyz",
    }
    import json
    with patch("subprocess.run", return_value=_fake_proc(stdout=json.dumps(envelope))):
        out = invoke_claude_cli(prompt="answer", json_schema='{"type": "object"}')
    assert out["is_error"] is False
    assert out["structured_output"] == {"answer": 42}
    assert out["exec"] == "success"


def test_invoke_claude_cli_api_error_envelope():
    envelope = {"result": "The request failed because of X.", "is_error": True}
    import json
    with patch("subprocess.run", return_value=_fake_proc(stdout=json.dumps(envelope))):
        out = invoke_claude_cli(prompt="hi")
    assert out["is_error"] is True
    assert out["error"] == "The request failed because of X."
    assert out["exec"] == "failure"


def test_invoke_claude_cli_api_error_envelope_no_result_falls_back_to_status():
    envelope = {"result": "", "is_error": True, "api_error_status": 529}
    import json
    with patch("subprocess.run", return_value=_fake_proc(stdout=json.dumps(envelope))):
        out = invoke_claude_cli(prompt="hi")
    assert out["is_error"] is True
    assert out["error"] == "API error, status 529"
    assert out["exec"] == "failure"


def test_invoke_claude_cli_passes_flags_only_when_set():
    with patch("subprocess.run", return_value=_fake_proc(stdout='{"result": "ok", "is_error": false}')) as mock_run:
        invoke_claude_cli(prompt="hi")
    cmd = mock_run.call_args[0][0]
    assert cmd == ["claude", "-p", "hi", "--output-format", "json"]

    with patch("subprocess.run", return_value=_fake_proc(stdout='{"result": "ok", "is_error": false}')) as mock_run:
        invoke_claude_cli(
            prompt="hi",
            agent="reviewer",
            model="opus",
            json_schema='{"type": "object"}',
            working_directory="/tmp",
            resume_session_id="sess-abc",
        )
    cmd = mock_run.call_args[0][0]
    assert cmd == [
        "claude", "-p", "hi", "--output-format", "json",
        "--agent", "reviewer",
        "--model", "opus",
        "--json-schema", '{"type": "object"}',
        "--resume", "sess-abc",
    ]
    kwargs = mock_run.call_args[1]
    assert kwargs["cwd"] == "/tmp"


def test_invoke_claude_cli_resume_flag_omitted_when_empty():
    with patch("subprocess.run", return_value=_fake_proc(stdout='{"result": "ok", "is_error": false}')) as mock_run:
        invoke_claude_cli(prompt="hi", resume_session_id="")
    cmd = mock_run.call_args[0][0]
    assert "--resume" not in cmd


def test_invoke_claude_cli_resume_unknown_session_id_is_argument_parsing_failure():
    # Confirmed against the real CLI: an unknown/invalid --resume id exits 1
    # with a message on stderr and empty stdout — no envelope is produced,
    # so it falls into the same branch as any other CLI arg-parsing failure.
    with patch(
        "subprocess.run",
        return_value=_fake_proc(
            stdout="",
            stderr="No conversation found with session ID: bogus-id\n",
            returncode=1,
        ),
    ):
        out = invoke_claude_cli(prompt="hi", resume_session_id="bogus-id")
    assert out["is_error"] is True
    assert out["error"] == "No conversation found with session ID: bogus-id"
    assert out["exec"] == "failure"
