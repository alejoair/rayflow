"""Tests for the `rayflow install claude-tools` CLI command."""
import json

from click.testing import CliRunner

from rayflow.cli.main import cli


def _run(*args):
    return CliRunner().invoke(cli, ["install", "claude-tools", *args])


def test_install_claude_tools_writes_skills_agent_and_mcp_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = _run()
    assert result.exit_code == 0, result.output

    assert (tmp_path / ".claude" / "skills" / "rayflow-node" / "SKILL.md").exists()
    assert (tmp_path / ".claude" / "skills" / "rayflow-flow" / "SKILL.md").exists()
    assert (tmp_path / ".claude" / "agents" / "rayflow-debugger.md").exists()

    mcp = json.loads((tmp_path / ".mcp.json").read_text())
    assert mcp["mcpServers"]["rayflow"]["url"] == "http://localhost:8000/mcp/"


def test_install_claude_tools_is_idempotent_without_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _run()

    skill_path = tmp_path / ".claude" / "skills" / "rayflow-node" / "SKILL.md"
    skill_path.write_text("TAMPERED", encoding="utf-8")

    result = _run()
    assert result.exit_code == 0
    assert skill_path.read_text() == "TAMPERED"  # untouched: skipped, not overwritten
    assert "skipped" in result.output


def test_install_claude_tools_force_overwrites_skills_but_not_mcp_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _run()

    skill_path = tmp_path / ".claude" / "skills" / "rayflow-node" / "SKILL.md"
    skill_path.write_text("TAMPERED", encoding="utf-8")
    mcp_path = tmp_path / ".mcp.json"
    mcp_path.write_text(json.dumps({"mcpServers": {"other": {"type": "http", "url": "http://x"}}}))

    result = _run("--force")
    assert result.exit_code == 0
    assert skill_path.read_text() != "TAMPERED"  # overwritten
    assert json.loads(mcp_path.read_text())["mcpServers"] == {"other": {"type": "http", "url": "http://x"}}
    assert "never" not in result.output  # sanity: didn't accidentally print an error
