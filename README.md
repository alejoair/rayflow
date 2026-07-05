# Rayflow

[![PyPI version](https://img.shields.io/pypi/v/rayflow.svg)](https://pypi.org/project/rayflow/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://github.com/alejoair/rayflow/actions/workflows/test.yml/badge.svg)](https://github.com/alejoair/rayflow/actions/workflows/test.yml)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)

**Build distributed systems by drawing them: connect nodes, switch them on, and they stay running.**

Rayflow is a visual editor for building backends on top of [Ray](https://www.ray.io/). You connect nodes — each one a piece of Python logic — with two kinds of wire: one sets the **order of execution**, the other carries **data**. Load the graph and its nodes come up as live processes that **stay available** — not a task that runs once and exits: call them like an API, trigger them with events, or let them keep state between calls, a service you designed by drawing it.

> Status: early (alpha). The execution model and the editor are functional; the API may change.

## Two ways to build a flow

- **Draw it** — open the visual editor, wire nodes together, run it. See [Quickstart](#quickstart) below.
- **Have an agent build it** — install the MCP tools (`rayflow install claude-tools`) and let an LLM agent like Claude Code design, validate, and test the flow for you, talking to the same API the editor uses. See [Path B: an LLM agent, via MCP](#path-b-an-llm-agent-via-mcp) below.

Both paths produce the exact same flow JSON, running on the exact same engine — pick whichever fits how you work today.

## Installation

```bash
pip install rayflow
```

Requires Python 3.10+. Ray, FastAPI, Uvicorn, and FastMCP are installed as dependencies.

## Quickstart

Launch the server (visual editor + REST API + MCP):

```bash
rayflow serve --port 8000
```

- Visual editor: http://localhost:8000/editor
- REST API: http://localhost:8000/flows
- Health check: http://localhost:8000/health

Building an actual flow — by hand in Python, or by having an agent do it — is covered next.

## Building a flow — two paths

### Path A: the Python API

A flow's inputs live on its entry node — there's no flow-level `inputs`
field, so a flow that wants named typed inputs (like `a`/`b` below, as
opposed to the raw HTTP envelope `OnStart` gives you) declares its own
`@entry_node`:

```python
import rayflow
from rayflow.nodes.decorators import entry_node, Input, ExecOutput
from rayflow.nodes.registry import get_catalog

@entry_node
class SumaEntry:
    a = Input("int", default=0)
    b = Input("int", default=0)
    exec_out = ExecOutput()

get_catalog().register(SumaEntry)

# A flow is plain data — here defined inline.
suma = {
    "name": "suma",
    "public": False,  # metadata for external gateways only; default False, rayflow itself doesn't read/enforce it
    "outputs": {"result": "int"},
    "nodes": [
        {"id": "entry", "type": "SumaEntry"},
        {"id": "add", "type": "Add", "exec_in": "entry",
         "inputs": {"a": "entry.a", "b": "entry.b"}},
        {"id": "exit", "type": "FlowOutput", "exec_in": "add",
         "inputs": {"result": "add.result"}},
    ],
}

rayflow.load(suma)
for event in rayflow.execute("suma", {"a": 3, "b": 4}):
    if event["event"] == "flow_done":
        print(event["result"])  # {"result": 7}
rayflow.unload("suma")
```

### Path B: an LLM agent, via MCP

Rayflow ships an MCP server alongside the REST API, so an LLM agent (Claude
Code or any other MCP client) can design, validate, save, and run flows
through the same operations the visual editor uses — no hand-written flow
JSON, no separate SDK.

Install the agent-facing tooling into your project:

```bash
rayflow install claude-tools
```

This drops into your working directory:

- **`.mcp.json`** — registers Rayflow's MCP server (served at `/mcp` by
  `rayflow serve`), so an MCP-aware client picks it up automatically.
- **Two Claude Code skills** (`.claude/skills/`): `rayflow-flow` (design,
  validate, and test a flow end-to-end) and `rayflow-node` (create or edit
  a custom node). Both bundle real, runnable scripts — e.g.
  `validate_flow.py` and `batch_test.py` — so an agent can iterate locally
  against the same validation logic the server uses, instead of paying a
  network round-trip per attempt.
- **A `rayflow-debugger` subagent** for tracing a flow node-by-node when a
  run gives the wrong result and it's not obvious which node is at fault.

With the server running (`rayflow serve --port 8000`), an agent has tools
like `get_guide`, `list_nodes`/`get_node`, `validate_flow`, `create_flow`/
`update_flow`, `run_flow`/`test_flow`, and the custom-node equivalents
(`create_custom_node`, `update_custom_node_source`, hot-reloaded — no
restart needed). A typical exchange:

> **You:** "Build a flow that adds two numbers and doubles the result."
>
> **Agent:** reads `get_guide` and `list_nodes`, drafts a flow wiring
> `Add` → `Multiply`, calls `validate_flow` until it reports `valid: true`,
> then `create_flow` to save it and `test_flow` to confirm the output —
> all without you writing or reading a line of flow JSON.

This is the same node catalog, the same validation, and the same execution
engine the visual editor drives — a flow built by an agent opens in the
editor exactly like one built by hand, and vice versa.

## How a flow is triggered

The same graph can be started in several ways:

- **Programmatically** — `load()` once, `execute()` any number of times (each call streams `node_start`/`node_done`/`flow_done` events and returns the flow's outputs in `flow_done`), `unload()` when done.
- **Served as an API** — `load()` once and `execute()` many times; exposed over HTTP with event streaming. The system stays resident and is invoked repeatedly.
- **With a built-in UI** — use the `ChatTrigger` entry node (or any custom entry node declaring `frontend`) and `rayflow serve --file flow.json` mounts a static web UI at `GET /flows/{name}/ui`. The page talks to the flow over the same `/flows/{name}/run` endpoint — no separate transport. Useful for chat-style flows, forms, or any flow that wants a human-facing surface without writing a frontend app.
- **By event** — `serve_events()` plus an `OnEvent` node: the flow stays resident and is triggered by an event, with no direct call.
- **As a component of another flow** — the `CallFlow` node runs one flow inside another.

Across all of these, a flow can be **stateless or stateful** — with or without memory between invocations (graph variables and state in resident nodes). With `EmitEvent`, a flow can also trigger others and chain reactions.

## Concepts

A flow is a graph of **nodes** connected by two kinds of pin:

- **Exec pins** — define the order of execution (control).
- **Data pins** — carry values between nodes.

Each node is a decorated Python class. The decorator decides *where* it runs, not *what* it does:

```python
from rayflow.nodes.decorators import engine_node, ExecInput, ExecOutput, Input, Output, ExecContext

@engine_node            # runs locally inside the engine
class Add:
    exec_in   = ExecInput()
    a         = Input("int", default=0)
    b         = Input("int", default=0)
    result    = Output("int")
    exec_out  = ExecOutput()

    async def run(self, ctx: ExecContext, a: int, b: int) -> None:
        ctx.set_output("result", a + b)
        await ctx.fire("exec_out")
```

- `@engine_node` runs locally, inside the engine (best for lightweight control logic).
- `@ray_node` runs distributed on Ray (with exec pins it is a persistent, stateful actor).

The `run()` contract is identical for both — only the deployment differs.

A flow is stored as JSON — see the `suma` flow in [Path A](#path-a-the-python-api)
above for a complete example.

## Python API

```python
import rayflow

rayflow.load(source)                    # pre-validate, spawn actors, register as served
rayflow.execute(name, inputs)           # run an already-loaded flow (event stream)
rayflow.unload(name)                    # unload the flow
rayflow.serve_events(source)            # keep the flow resident, subscribed to the event bus
rayflow.stop(graph_id, event_names)     # unsubscribe and unload
```

## Documentation

- Agent-facing skills and MCP tooling: [`rayflow/claude_tools/`](rayflow/claude_tools/) — installed into your project via `rayflow install claude-tools` (see [Path B](#path-b-an-llm-agent-via-mcp) above).
- Contributing guide: [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Development

```bash
pip install -e ".[dev]"
pytest tests/
```

The editor frontend (React + Vite) lives in `rayflow/editor/frontend/`:

```bash
cd rayflow/editor/frontend
npm install
npm run build
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full workflow and the
Contributor License Agreement.

## License

Rayflow is **dual-licensed**:

- **Open source:** [GNU AGPL-3.0-or-later](LICENSE). Free to use, modify, and
  distribute under the AGPL's terms (note its network-use copyleft).
- **Commercial:** for use without the AGPL obligations (e.g. embedding Rayflow
  in a closed-source or hosted product), a separate commercial license is
  required. See [`COMMERCIAL-LICENSE.md`](COMMERCIAL-LICENSE.md).

Personal, educational, research, and non-profit use is fully covered by the
AGPL at no cost. For commercial terms, contact **Manuel Alejandro Cuartas**
(<alejandro.cuartas@yahoo.com>).
