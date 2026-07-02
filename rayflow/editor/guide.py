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
  "inputs":  { "x": "int" },
  "outputs": { "result": "int" },
  "variables": [{ "name": "counter", "type": "int", "default": 0 }],
  "events": [],
  "nodes": [
    { "id": "entry", "type": "OnStart" },
    { "id": "add", "type": "Add", "exec_in": "entry", "inputs": { "a": "entry.x", "b": 10 } },
    { "id": "exit", "type": "FlowOutput", "exec_in": "add", "inputs": { "result": "add.result" } }
  ]
}
```

## Wiring rules

- **Every flow needs exactly one entry node** — a node type declaring
  `is_entry = True`. The three built-ins are `OnStart` (direct execution),
  `OnEvent` (event-triggered), and `OnVariableChange` (variable change); a
  custom node can declare the same flag. Declaring more than one entry node
  in the same flow is a build error.
- **Exec edges**: declared FROM the consumer with `exec_in`:
  - `"exec_in": "node_id"` -> the source node's default exec output.
  - `"exec_in": "node_id.pin"` -> a specific exec output (`branch.true`, `seq.then_0`).
  - `"exec_in": ["a", "b"]` -> waits for both (an "and" join).
  - `"exec_in": {"or": ["a", "b"]}` -> the first one to arrive (an "or" join).
- **Data edges**: in `inputs`, the value is either:
  - a literal of the correct type: `"b": 10`, `"flag": true`, `"name": "hello"`.
  - a reference `"node_id.pin"`: `"a": "entry.x"`, `"result": "add.result"`.

## Dynamic pins (don't appear in the static /editor/nodes)

- Any entry node with `exposes_flow_inputs = True` (built-in: `OnStart`/
  `FlowInput`, `OnEvent`) expose **one data output per input of the
  flow**. If the flow declares `inputs: {x: int}`, you can read `entry.x`.
  They ALSO always expose 4 fixed outputs — `headers`/`query` (`dict[str, str]`),
  `body` (`Any`), `method` (`str`) — since a served flow's trigger is an HTTP
  request. Wire from these like any other pin; outside HTTP they default to
  whatever the consuming `Input` declares. To set the response's real HTTP
  status/headers, call `ctx.set_response_status(code)` /
  `ctx.set_response_header(name, value)` from any node's `run()` — this is
  invisible to non-HTTP callers (MCP's `run_flow`/`test_flow`), since it
  lives outside `flow.outputs`.
- `FlowOutput`: has **one required data input per output of the flow**.
- `Parallel`: its branches `branch_0`, `branch_1`, … are discovered from the
  wiring (nodes whose `exec_in` is `parallel_id.branch_N`); `joined` fires
  once they're all done.
- `CallFlow`: accepts arbitrary inputs mapped to the subflow.

Check `GET /editor/flows/{name}/catalog` to see the already-resolved pins
of a specific flow.

## Type system

Canonical types (strings): `int`, `float`, `str`, `bool`, `list`, `dict`,
`Any`, plus generics `list[T]` and `dict[str, V]`. STRICT compatibility:
same type, or one is `Any`. **int and float are incompatible**: cast with
`ToInt`/`ToFloat`/`ToStr`/`ToBool`. Check `GET /editor/types`.

## Recommended workflow for an agent

1. `GET /editor/guide` and `GET /editor/nodes` to learn the catalog.
2. (Optional) `GET /editor/examples/{name}` as a template.
3. Build the flow JSON.
4. `POST /editor/validate` -> returns ALL errors and warnings at once.
5. Fix until `valid: true`.
6. `POST /editor/flows` (create) or `PUT /editor/flows/{name}` (update).
7. `POST /editor/flows/{name}/test` with `{inputs, expected_outputs}` to
   verify it does what's expected, or `POST /flows/{name}/run` to run it
   (loads it into Ray on demand if needed; add `Accept: text/event-stream`
   for the SSE event stream instead of a single JSON response).
"""
