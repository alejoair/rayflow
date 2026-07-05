"""Builtin Claude node: invokes the Claude Code CLI (`claude -p`) headless.

First concrete step towards rayflow-as-agent-orchestration-language. Kept
deliberately simple: a subprocess call to the `claude` CLI in headless mode
(`-p ... --output-format json`), NOT the Claude Agent SDK. The SDK sits on
the same underlying layer but drags in pydantic/starlette/uvicorn — this
repo's explicit "no Pydantic" stance makes the subprocess the right choice
for this scope; the CLI is versatile enough (agents, models, JSON-schema
structured output) without that dependency weight.
"""
import json
import subprocess
from typing import Any

from rayflow.nodes.decorators import (
    ExecContext,
    ExecInput,
    ExecOutput,
    Input,
    Output,
    ray_node,
)

# Default fields returned when the CLI never produced a usable envelope
# (timeout, missing binary, or an argument-parsing failure that only wrote
# to stderr). Kept as one constant so every failure path builds on the same
# baseline instead of repeating the empty defaults inline.
_EMPTY_RESULT: dict[str, Any] = {
    "result": "",
    "structured_output": {},
    "is_error": True,
    "error": "",
    "cost_usd": 0.0,
    "session_id": "",
}


def invoke_claude_cli(
    prompt: str,
    agent: str = "",
    model: str = "",
    json_schema: str = "",
    timeout_seconds: int = 300,
    working_directory: str = "",
    resume_session_id: str = "",
) -> dict[str, Any]:
    """Runs `claude -p <prompt> --output-format json` as a subprocess and
    parses its envelope. Pure function (no ExecContext, no Ray) so it can be
    exercised directly in tests/scripts without an actor.

    `resume_session_id`, if non-empty, adds `--resume <id>` to resume an
    existing conversation (confirmed against the real CLI: `--resume` is the
    right flag for this — `--session-id` has different semantics, it
    *assigns* a specific id to a NEW conversation and errors out if that id
    is already in use). An invalid/unknown session id passed to `--resume`
    fails with exit code 1 and a message on stderr with empty stdout, which
    already falls into the CLI-argument-parsing-failure branch below — no
    extra handling needed for that case.

    Returns a dict with the node's data outputs (result, structured_output,
    is_error, error, cost_usd, session_id) plus "exec": "success" | "failure"
    telling the caller which exec pin to fire. Never raises: every failure
    mode (timeout, missing binary, CLI argument-parsing failure, malformed
    JSON, or an in-envelope API error) is folded into is_error/error instead
    of propagating an exception.
    """
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    if agent:
        cmd += ["--agent", agent]
    if model:
        cmd += ["--model", model]
    if json_schema:
        cmd += ["--json-schema", json_schema]
    if resume_session_id:
        cmd += ["--resume", resume_session_id]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=working_directory or None,
        )
    except subprocess.TimeoutExpired:
        out = dict(_EMPTY_RESULT)
        out["error"] = f"timed out after {timeout_seconds}s"
        out["exec"] = "failure"
        return out
    except FileNotFoundError:
        out = dict(_EMPTY_RESULT)
        out["error"] = "claude CLI not found in PATH"
        out["exec"] = "failure"
        return out

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    # The CLI failed before ever producing an envelope (e.g. `--json-schema`
    # got malformed JSON, or `--agent` named a subagent that doesn't exist):
    # stdout is empty and the diagnostic is on stderr.
    if not stdout.strip():
        out = dict(_EMPTY_RESULT)
        out["error"] = stderr.strip() or "claude CLI produced no output"
        out["exec"] = "failure"
        return out

    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        # Shouldn't happen with --output-format json, but cover it: treat the
        # raw stdout as the error payload rather than letting the exception
        # propagate.
        out = dict(_EMPTY_RESULT)
        out["error"] = f"could not parse claude CLI output as JSON: {stdout.strip()}"
        out["exec"] = "failure"
        return out

    is_error = bool(envelope.get("is_error", False))
    result = envelope.get("result", "")
    out = {
        "result": result,
        "structured_output": envelope.get("structured_output", {}),
        "is_error": is_error,
        "cost_usd": envelope.get("total_cost_usd", 0.0),
        "session_id": envelope.get("session_id", ""),
    }
    if is_error:
        out["error"] = result or f"API error, status {envelope.get('api_error_status')}"
        out["exec"] = "failure"
    else:
        out["error"] = ""
        out["exec"] = "success"
    return out


@ray_node
class Claude:
    """Invokes the Claude Code CLI (`claude -p`) headless, as a subprocess.

    Runs as a Ray actor (via @ray_node with exec pins) so several
    invocations wired under a `Parallel` node run as real concurrent
    subprocesses instead of blocking one another.

    Fires `success` when the CLI returned a well-formed envelope with
    `is_error: false`; fires `failure` for every other case — a CLI
    argument-parsing failure (empty stdout, message on stderr), a timeout,
    a missing `claude` binary, malformed JSON output, or an envelope with
    `is_error: true`. `error` carries a human-readable diagnostic in the
    failure case and is empty on success; the node never raises.

    Note on pin naming: the exec output for the failure path is named
    `failure`, not `error`, because a data output already named `error`
    (the error message string) is declared on this same class — Python
    class attributes require unique names, so both couldn't be called
    `error`. `success` / `failure` reads the same as the originally
    requested `success` / `error` pair. Same reasoning behind
    `resume_session_id` (Input) vs `session_id` (Output): the output already
    claims that name for the conversation id this call produced/continued.

    Multi-turn pattern: wire this call's `session_id` output into a `Set`
    node writing a GraphState variable, and feed that variable back into the
    next call's `resume_session_id` input (typically inside a `While` loop)
    to carry a conversation across invocations — rayflow nodes are already
    stateful via GraphState, so no extra machinery is needed for this.

    Note on `working_directory`: this isn't a blank-slate call. `claude -p`
    inherits the target directory's project context (`CLAUDE.md`,
    `.claude/agents/*.md`, etc.) the same way an interactive session would,
    confirmed against the real CLI — if `working_directory` (or the
    rayflow process's own cwd, when left empty) is inside a project with its
    own `CLAUDE.md`/`.claude/`, that context is loaded and shapes the
    response.
    """
    category = "AI"
    exec_in = ExecInput()

    prompt = Input("str")
    agent = Input("str", default="")
    model = Input("str", default="")
    json_schema = Input("str", default="")
    timeout_seconds = Input("int", default=300)
    working_directory = Input("str", default="")
    resume_session_id = Input("str", default="")

    result = Output("str")
    structured_output = Output("dict")
    is_error = Output("bool")
    error = Output("str")
    cost_usd = Output("float")
    session_id = Output("str")

    success = ExecOutput()
    failure = ExecOutput()

    async def run(
        self,
        ctx: ExecContext,
        prompt: str,
        agent: str,
        model: str,
        json_schema: str,
        timeout_seconds: int,
        working_directory: str,
        resume_session_id: str,
    ) -> None:
        out = invoke_claude_cli(
            prompt=prompt,
            agent=agent,
            model=model,
            json_schema=json_schema,
            timeout_seconds=timeout_seconds,
            working_directory=working_directory,
            resume_session_id=resume_session_id,
        )
        ctx.set_output("result", out["result"])
        ctx.set_output("structured_output", out["structured_output"])
        ctx.set_output("is_error", out["is_error"])
        ctx.set_output("error", out["error"])
        ctx.set_output("cost_usd", out["cost_usd"])
        ctx.set_output("session_id", out["session_id"])
        await ctx.fire(out["exec"])
