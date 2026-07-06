"""Curated guide to Rayflow's model, served by `GET /editor/guide`.

This is the "semantic contract" an LLM agent needs to build flows, which
used to live only in CLAUDE.md / code docstrings. Plain markdown text.
"""

GUIDE = """\
# Guide to building Rayflow flows

A flow is a graph of nodes connected by two kinds of wire:
- **exec** (order of execution): sequential.
- **data** (values): evaluated in parallel on demand.

## Structure of a flow (JSON)

```json
{
  "name": "my_flow",
  "version": "1",
  "public": false,
  "outputs": { "result": "int" },
  "variables": [{ "name": "counter", "type": "int", "default": 0 }],
  "events": [],
  "nodes": [
    { "id": "entry", "type": "OnStart" },
    { "id": "add", "type": "Add", "exec_in": "entry", "inputs": { "a": 5, "b": 10 } },
    { "id": "exit", "type": "FlowOutput", "exec_in": "add", "inputs": { "result": "add.result" } }
  ]
}
```

`public` (bool, default `false`) is pure metadata for an external gateway to
decide whether the flow should be reachable without authentication — rayflow
itself never reads it or enforces any permission based on it.

## Wiring rules

- **Every flow needs exactly one entry node** — a node declared with the
  `@entry_node` decorator. Built-ins: `OnStart` (declares `body`/`headers`/
  `query`/`method` from the HTTP envelope), `OnEvent` (event-triggered),
  `OnVariableChange` (variable change), and `ChatTrigger` (built-in chat UI
  served at `/flows/{name}/ui`); a custom node can use the same decorator.
  Declaring more than one entry node in the same flow is a build error. Any
  entry node may optionally declare `frontend = "<dir>"` to serve a static
  UI bundle at `/flows/{name}/ui` when the flow is served (`rayflow serve
  --file`) — the bundle's JS talks to the flow over the normal
  `/flows/{name}/run` endpoint. That bundle is a single self-contained
  `index.html` (inline CSS/JS — see `ChatTrigger` in
  `rayflow/nodes/builtin/control.py` for the one built-in example); manage
  it with `get_entry_frontend`/`update_entry_frontend`/
  `delete_entry_frontend` (or `GET`/`PUT`/`DELETE
  /editor/nodes/{node_type}/frontend`) instead of touching the filesystem
  directly — this is the only way a remote MCP client with no filesystem
  access can create or edit it. If the node doesn't declare `frontend` yet,
  add it as a class attribute first (for a custom node, via
  `update_custom_node_source`) before calling these.
- **Entry nodes declare their own `Input` pins** like any other node. The
  engine populates them from the request body (POST `{name: value, ...}`
  → entry's `Input` of that name). When an entry doesn't define `run()`,
  the engine auto-mirrors each declared Input as an output of the same
  name, so downstream nodes can cable `entry.x`. When it does define
  `run()`, the author calls `ctx.set_output(...)` explicitly (see
  `ChatTrigger` for an example). Entries also have access to
  `ctx.request` (`body`/`headers`/`query`/`method`) for things they don't
  want to declare as pins.
- **Exec edges**: declared FROM the consumer with `exec_in`:
  - `"exec_in": "node_id"` -> the source node's default exec output.
  - `"exec_in": "node_id.pin"` -> a specific exec output (`branch.true`, `seq.then_0`).
  - `"exec_in": ["a", "b"]` -> waits for both (an "and" join).
  - `"exec_in": {"or": ["a", "b"]}` -> the first one to arrive (an "or" join).
- **Data edges**: in `inputs`, the value is either:
  - a literal of the correct type: `"b": 10`, `"flag": true`, `"name": "hello"`.
  - a reference `"node_id.pin"`: `"a": "entry.x"`, `"result": "add.result"`.

## Dynamic pins (don't appear in the static /editor/nodes)

- `FlowOutput`: has **one required data input per output of the flow**.
- `Parallel`: its branches `branch_0`, `branch_1`, … are discovered from the
  wiring (nodes whose `exec_in` is `parallel_id.branch_N`); `joined` fires
  once they're all done.
- `CallFlow`: accepts arbitrary inputs mapped to the subflow. Its `flow`
  input takes the NAME of a saved flow (as returned by `list_flows`/
  `create_flow`, e.g. `"my_subflow"`, no extension), a literal file path, or
  an inline subflow dict — never a `"node.pin"` reference. An unknown
  name/path is reported as a build error.

Entry nodes (`@entry_node` like `OnStart`, `OnEvent`, `ChatTrigger`, …) used
to carry dynamic pins derived from `flow.inputs`; they now declare their
own `Input`/`Output` statically. To set the response's real HTTP
status/headers, call `ctx.set_response_status(code)` /
`ctx.set_response_header(name, value)` from any node's `run()` — this is
invisible to non-HTTP callers (MCP's `run_flow`/`test_flow`), since it
lives outside `flow.outputs`.

Check `GET /editor/flows/{name}/catalog` to see the already-resolved pins
of a specific flow.

## Type system

Canonical types (strings): `int`, `float`, `str`, `bool`, `list`, `dict`,
`Any`, plus generics `list[T]` and `dict[str, V]`. STRICT compatibility:
same type, or one is `Any`. **int and float are incompatible**: cast with
`ToInt`/`ToFloat`/`ToStr`/`ToBool`. Check `GET /editor/types`.

## Calling an LLM from a flow: the `Claude` node

`Claude` (category `"AI"`) invokes the Claude Code CLI (`claude -p`)
headless, as a subprocess — the first building block for using rayflow to
orchestrate agents. Inputs: `prompt` (str, required), `agent` (str,
optional — subagent name via `--agent`), `model` (str, optional — model
alias via `--model`), `json_schema` (str, optional — a JSON Schema string;
if set, forces structured output via `--json-schema`), `timeout_seconds`
(int, default 300), `working_directory` (str, optional — the subprocess's
cwd; matters because resolving a project `--agent` by name depends on cwd,
and because `claude -p` inherits that directory's project context —
`CLAUDE.md`, `.claude/agents/*.md`, etc. — same as an interactive session;
it is not a blank-slate call), `resume_session_id` (str, optional — resumes
an existing conversation via `--resume <id>`; an unknown/invalid id fails
explicitly with a stderr message and empty stdout, same as any other
CLI-argument-parsing failure). Outputs: `result` (str), `structured_output`
(dict — populated only when `json_schema` was set, `{}` otherwise),
`is_error` (bool), `error` (str — diagnostic message, empty on success),
`cost_usd` (float), `session_id` (str — this call's conversation id). It
has two exec outputs instead of one: `success` (the CLI returned a
well-formed envelope with `is_error: false`) and `failure` (everything else
— CLI argument-parsing failures, a timeout, a missing `claude` binary,
malformed CLI output, or an envelope with `is_error: true`) — wire each to
its own downstream handling instead of assuming the call always works.

**Multi-turn conversations**: wire the `session_id` output into a `Set`
node writing a GraphState variable, and feed that variable into the next
call's `resume_session_id` input (typically inside a `While` loop) to carry
a conversation across invocations — this works because rayflow nodes are
already stateful via GraphState, no extra machinery needed.

## Recommended workflow for an agent

1. `GET /editor/guide` and `GET /editor/nodes` to learn the catalog.
2. Build the flow JSON.
3. `POST /editor/validate` -> returns ALL errors and warnings at once.
4. Fix until `valid: true`.
5. `POST /editor/flows` (create) or `PUT /editor/flows/{name}` (update).
6. `POST /editor/flows/{name}/test` with `{inputs, expected_outputs}` to
   verify it does what's expected, or `POST /flows/{name}/run` to run it
   (loads it into Ray on demand if needed; add `Accept: text/event-stream`
   for the SSE event stream instead of a single JSON response).
"""
