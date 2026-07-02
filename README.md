# Rayflow

[![PyPI version](https://img.shields.io/pypi/v/rayflow.svg)](https://pypi.org/project/rayflow/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://github.com/alejoair/rayflow/actions/workflows/test.yml/badge.svg)](https://github.com/alejoair/rayflow/actions/workflows/test.yml)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)

**Build distributed systems by drawing them: connect nodes, switch them on, and they stay running.**

Rayflow is a visual editor for building backends on top of [Ray](https://www.ray.io/). You connect nodes — each one a piece of Python logic — with two kinds of wire: one sets the **order of execution**, the other carries **data**. When you load the graph, its nodes come up as live processes and **stay available**: you can call them like an API, trigger them with events, or let them keep state between calls.

It is not a task orchestrator that runs and exits. A flow **stays up**, with memory, waiting to be invoked — a service you designed by drawing it.

> Status: early (alpha). The execution model and the editor are functional; the API may change.

## Installation

```bash
pip install rayflow
```

Requires Python 3.10+. Ray, FastAPI, and Uvicorn are installed as dependencies.

## Quickstart

Launch the server (visual editor + REST API):

```bash
rayflow serve --port 8000
```

- Visual editor: http://localhost:8000/editor
- REST API: http://localhost:8000/flows
- Health check: http://localhost:8000/health

Or run a flow from Python:

```python
import rayflow

# A flow is plain data — here defined inline. Load, run, and unload in one call.
suma = {
    "name": "suma",
    "inputs":  {"a": "int", "b": "int"},
    "outputs": {"result": "int"},
    "nodes": [
        {"id": "entry", "type": "OnStart"},
        {"id": "add", "type": "Add", "exec_in": "entry",
         "inputs": {"a": "entry.a", "b": "entry.b"}},
        {"id": "exit", "type": "FlowOutput", "exec_in": "add",
         "inputs": {"result": "add.result"}},
    ],
}

result = rayflow.run(suma, a=3, b=4)
print(result)  # {"result": 7}
```

The same flow as a JSON file lives in [`examples/suma.json`](examples/suma.json),
along with other examples in [`examples/`](examples/).

## How a flow is triggered

The same graph can be started in several ways:

- **One-shot** — `rayflow.run(flow, **inputs)`: load, run, and unload. For a single computation.
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

A flow is stored as JSON. For example, the `suma` flow from the quickstart:

```json
{
  "name": "suma",
  "inputs":  { "a": "int", "b": "int" },
  "outputs": { "result": "int" },
  "nodes": [
    { "id": "entry", "type": "OnStart" },
    { "id": "add", "type": "Add", "exec_in": "entry",
      "inputs": { "a": "entry.a", "b": "entry.b" } },
    { "id": "exit", "type": "FlowOutput", "exec_in": "add",
      "inputs": { "result": "add.result" } }
  ]
}
```

## Python API

```python
import rayflow

rayflow.run(source, **inputs)   # load + run + unload (one-shot)
rayflow.load(source)            # keep the flow resident in Ray
rayflow.execute(name, inputs)   # run an already-loaded flow (event stream)
rayflow.unload(name)            # unload the flow
rayflow.serve_events(source)    # keep the flow resident, subscribed to the event bus
rayflow.stop(graph_id, events)  # unsubscribe and unload
```

## Documentation

- Flow examples: [`examples/`](examples/)
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
