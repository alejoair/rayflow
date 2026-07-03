---
name: rayflow-flow
description: Use when designing, building, editing, or testing a Rayflow flow (or a set of connected flows) through the MCP tools — turning a request like "build me a flow that..." into a saved, validated, working flow.json. Also covers composing flows out of subflows and wiring event-reactive flows.
---

# Building and testing Rayflow flows

Rayflow flows are JSON graphs of nodes wired by exec pins (control flow,
sequential) and data pins (values, resolved in parallel). Build and verify
them entirely through the MCP tools — don't hand-write flow JSON blind.

## The loop

1. `mcp__rayflow__get_guide` — read this first if you haven't in this
   session; it's the authoritative reference for flow JSON shape and wiring
   rules.
2. `mcp__rayflow__list_nodes` (and `get_node` for exact pins) to learn the
   vocabulary.
3. Draft the FlowDef JSON.
4. `mcp__rayflow__validate_flow` — **iterate on this until `valid: true`**.
   It returns every error in one pass (not just the first), so fix
   everything it reports before re-checking rather than fixing one at a
   time.
5. `mcp__rayflow__create_flow` (new) or `mcp__rayflow__update_flow` (editing
   an existing one — safe to call repeatedly; it unloads any stale loaded
   copy automatically, so the next run always reflects your latest edit).
6. `mcp__rayflow__test_flow` with `expected_outputs` if you know the right
   answer for some input — it tells you `passed`/`mismatches`, which is a
   stronger check than "it ran without error." Use `mcp__rayflow__run_flow`
   if you just want the output for exploration.

If a flow keeps failing validation for reasons that aren't obvious, or
`test_flow` gives a wrong result and you can't tell which node caused it,
hand off to the `rayflow-debugger` subagent instead of guessing — it has
`trace=True` visibility into every node's output and won't burn your main
conversation on the noisy back-and-forth.

## Flow JSON shape

```json
{
  "name": "my_flow",
  "inputs": { "x": "int" },
  "outputs": { "result": "int" },
  "nodes": [
    { "id": "entry", "type": "OnStart" },
    { "id": "add", "type": "Add", "exec_in": "entry", "inputs": { "a": "entry.x", "b": 10 } },
    { "id": "exit", "type": "FlowOutput", "exec_in": "add", "inputs": { "result": "add.result" } }
  ]
}
```

- Every node needs a unique `id`.
- `exec_in` wires control flow: `"<node_id>"`, or `"<node_id>.<exec_out_pin>"`
  if that node has more than one exec output (e.g. `Branch`'s `"true"`/`"false"`).
- Data inputs are either a literal value or a reference string
  `"<node_id>.<output_pin>"`. `OnStart`'s outputs are the flow's own declared
  `inputs`; a `FlowOutput` node's inputs become the flow's declared `outputs`.
- Use `mcp__rayflow__flow_catalog` on a saved flow to see each node's
  *actual resolved* pins in context (dynamic pins like `OnStart`'s or
  `Parallel`'s branches only exist once wired, so `list_nodes`/`get_node`
  alone won't show them for a specific flow).

## Composing bigger flows

- **CallFlow**: embed one saved flow inside another as a single node. Use
  this once a flow gets big or a piece of logic is reused — the subflow is
  spliced into the parent's graph at build time, so there's no runtime
  overhead or namespace collision to worry about.
- **Variables**: `Get`/`Set` nodes read/write flow-scoped state that persists
  across runs of the *same loaded flow* (not across separate flows, unless
  you use events — see below).
- **Events** (for reactive, multi-flow systems): a flow with an `OnEvent`
  node (and the event name declared in its `events` field) can react
  whenever another flow emits that event via an `EmitEvent` node, or whenever
  a variable it's watching changes (`OnVariableChange`). Register it with
  `mcp__rayflow__serve_flow_events`; unregister with `stop_flow_events`. Be
  careful with a flow that watches and rewrites its own variable — it can
  loop.

## HTTP request/response (flows served via `rayflow serve --file`)

Every served flow's trigger IS an HTTP request, so `OnStart` always exposes
4 fixed outputs alongside whatever named `inputs` the flow declares:
`headers` (`dict[str, str]`), `query` (`dict[str, str]`), `body` (`Any`,
the parsed JSON body), `method` (`str`). Wire from `entry.headers` etc.
like any other pin — no special node needed. Outside HTTP (MCP tools,
programmatic calls) these just come back empty.

For the response, `ctx.set_response_status(code)` /
`ctx.set_response_header(name, value)` inside any node's `run()` set the
real HTTP status/headers — invisible to non-HTTP callers (`run_flow`/
`test_flow`), since they live outside `flow.outputs`. Default is 200, no
extra headers, if never called. A simple API-key check is just an ordinary
node:

```python
@engine_node
class CheckApiKey:
    exec_in = ExecInput()
    headers = Input("dict[str, str]", default={})
    authorized = ExecOutput()
    denied = ExecOutput()

    async def run(self, ctx, headers: dict) -> None:
        if headers.get("x-api-key") == os.environ.get("MY_SECRET"):
            await ctx.fire("authorized")
        else:
            ctx.set_response_status(401)
            await ctx.fire("denied")
```

## Common mistakes

- Wiring an `int` output to a `float` input (or vice versa) expecting silent
  coercion — they're strictly incompatible; use a `ToInt`/`ToFloat` cast node.
- Forgetting a node needs `exec_in` to run at all if it has exec pins — a
  node with no incoming exec wire and no entry role just never fires.
- Calling `create_flow` on a name that already exists — it fails on purpose;
  use `update_flow` to edit.
