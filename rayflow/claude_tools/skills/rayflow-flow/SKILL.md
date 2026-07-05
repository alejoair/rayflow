---
name: rayflow-flow
description: Use when designing, building, editing, or testing a Rayflow flow (or a set of connected flows) through the MCP tools — turning a request like "build me a flow that..." into a saved, validated, working flow.json. Also covers composing flows out of subflows and wiring event-reactive flows.
---

# Building and testing Rayflow flows

Rayflow flows are JSON graphs of nodes wired by exec pins (control flow,
sequential) and data pins (values, resolved in parallel). Build and verify
them through the MCP tools — don't hand-write flow JSON blind — and lean on
the scripts in this skill's `scripts/` directory for the parts of the loop
that would otherwise cost a network round-trip per iteration.

## Scripts (use these, not just the prose below)

- `scripts/validate_flow.py <flow.json|->` — the exact same validation
  logic as `mcp__rayflow__validate_flow` (it imports
  `rayflow.build.validator.validate_all` directly), run locally with no
  server round-trip. Iterate on a flow's JSON against this until
  `valid: true` — it's instant — then confirm once against the live
  `mcp__rayflow__validate_flow` before saving, since the running server's
  catalog (custom nodes especially) can drift from what a fresh local
  import sees. Must run from the project root (same cwd as `rayflow
  serve`, so `custom_nodes/` resolves the same way); needs `rayflow`
  importable.
- `scripts/batch_test.py <flow_name> <cases.json> [--url URL]` — runs a
  flow against a whole list of `{name?, inputs, expected_outputs?}` cases
  against a running `rayflow serve` in one shot (hits the same
  `/editor/flows/{name}/test` endpoint `test_flow` uses) instead of one
  MCP call per case, and prints a pass/fail table. Use it once you have
  more than one or two cases to check — table-driven edge cases, a
  regression check after editing the flow, etc.

Both print machine-readable JSON per case/run so you can act on the
result directly instead of re-parsing prose.

## The loop

1. `mcp__rayflow__get_guide` — read this first if you haven't in this
   session; it's the authoritative reference for flow JSON shape and wiring
   rules.
2. `mcp__rayflow__list_nodes` (and `get_node` for exact pins) to learn the
   vocabulary.
3. Draft the FlowDef JSON.
4. Validate: `scripts/validate_flow.py` in a loop while iterating locally
   (fast, no round-trip), then `mcp__rayflow__validate_flow` once against
   the live server before saving. **Iterate until `valid: true`** — both
   return every error in one pass (not just the first), so fix everything
   reported before re-checking rather than fixing one at a time. Also read
   the `warnings` field even when `valid: true`: the parser silently drops
   unrecognized/typo'd keys ("input" instead of "inputs", "exec" instead of
   "exec_in", a stray key on a variable) instead of erroring, so a
   warning today is a confusing "pin required but has no value" error
   tomorrow if you ignore it.
5. `mcp__rayflow__create_flow` (new) or `mcp__rayflow__update_flow` (editing
   an existing one — safe to call repeatedly; it unloads any stale loaded
   copy automatically, so the next run always reflects your latest edit).
6. Verify: `mcp__rayflow__test_flow` with `expected_outputs` for a single
   case, `scripts/batch_test.py` for several at once, or
   `mcp__rayflow__run_flow` if you just want the output for exploration.
   A `passed`/`mismatches` check is a stronger signal than "it ran without
   error."

If a flow keeps failing validation for reasons that aren't obvious, or
verification gives a wrong result and you can't tell which node caused it,
hand off to the `rayflow-debugger` subagent instead of guessing — it has
`trace=True` visibility into every node's output and won't burn your main
conversation on the noisy back-and-forth.

## Flow JSON shape

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

- Every node needs a unique `id` (validation error otherwise: `Node id
  'x' is duplicate`).
- `exec_in` wires control flow, declared from the CONSUMER's side:
  - `"<node_id>"` — the source's default exec output. Only valid if the
    source has exactly one; if it has several (e.g. `Branch`), you get
    `Exec source 'x' (Branch) has multiple exec outputs [...]; specify
    which one with 'node_id.pin_name'`.
  - `"<node_id>.<exec_out_pin>"` — a specific one (`branch.true`,
    `seq.then_0`, `par.branch_0`).
  - `["a", "b"]` — an **AND join**: waits for both `a` and `b` to fire
    before running.
  - `{"or": ["a", "b"]}` — an **OR join**: runs on whichever of `a`/`b`
    fires first.
- Data inputs (in a node's `inputs`) are either a literal of the pin's
  declared type, or a reference string `"<node_id>.<output_pin>"` (e.g.
  `"a": "entry.x"`, `"result": "add.result"`). There's no flow-level
  `inputs` field — the entry node (`OnStart` or a custom `@entry_node`)
  declares its own `Input` pins, populated from the request body by name;
  wire them downstream as `entry.<pin_name>` like any other pin. A
  `FlowOutput` node's inputs become the flow's declared `outputs` (one
  required input per declared output).
- `public` (bool, default `false`): pure metadata for an external gateway
  to decide whether this flow should be considered reachable without
  auth — rayflow itself never reads or enforces it.
- `variables`/`events` are optional top-level fields: `variables` seeds
  `Get`/`Set`-backed flow state (name/type/default); `events` declares
  which event names an `OnEvent` node in this flow subscribes to (required
  for `serve_flow_events` to register it — see Events below).
- Use `mcp__rayflow__flow_catalog` on a saved flow to see each node's
  *actual resolved* pins in context (dynamic pins like `Parallel`'s branches
  or `FlowOutput`'s inputs only exist once wired, so `list_nodes`/`get_node`
  alone won't show them for a specific flow — entry nodes like `OnStart` are
  static and already show up there).

## Control-flow patterns

- **Branch**: `condition: bool` input, fires `true` or `false`. Downstream
  nodes pick which with `"exec_in": "branch_id.true"` /
  `"exec_in": "branch_id.false"`.
- **Parallel**: forks into `branch_0`, `branch_1`, … — discovered from the
  wiring itself (any node whose `exec_in` names `"<parallel_id>.branch_N"`
  defines a branch), and joins on `joined` once every branch has finished
  (excerpt of a flow's `nodes` array):
  ```json
  [
    { "id": "par", "type": "Parallel", "exec_in": "entry" },
    { "id": "a", "type": "SomeNode", "exec_in": "par.branch_0", "inputs": {} },
    { "id": "b", "type": "SomeNode", "exec_in": "par.branch_1", "inputs": {} },
    { "id": "exit", "type": "FlowOutput", "exec_in": "par.joined", "inputs": {} }
  ]
  ```
- **ForEach**: `array: list` input; fires `loop_body` once per element
  (`element`/`index` outputs available inside the body), then `completed`.
- **While**: `condition_var: str` names a variable in `variables`; loops
  `loop_body` while it's truthy (the body must `Set` it to end the loop),
  then fires `completed`.
- **Map**: applies another catalog node (`node_type: str`, e.g. `"ToStr"`)
  to every element of `array`, collecting that node's first output into
  `result`. Works with any pure or exec node; the applied node's own exec
  outputs are ignored.

## Composing bigger flows

- **CallFlow**: embeds a subflow as a single node.
  - `flow` (required) must be a **static** value: an inline flow JSON
    object (most common — just embed the subflow's full JSON as the
    value), or a file path string. It can NOT be a wired reference like
    `"other_node.output"` — the build only accepts a plain dict or a path
    with no `.` in it as a reference marker, and rejects a dynamic
    reference with `the 'flow' input must be a static subflow (a dict or a
    path), not a dynamic reference`. In practice: embed the subflow inline.
  - `isolated` (bool, default `false`): `false` shares the parent's
    `GraphState` — a `Set` inside the subflow overwrites the parent's
    variable of the same name (real collision, verified behavior, not a
    hypothetical). `true` gives the subflow its own state namespace: same
    variable name, no collision, and the parent can't read anything the
    subflow set.
  - Any other key in `inputs` is passed through to the subflow's entry
    node **by matching declared `Input` pin name** — this is the part
    that trips people up: `OnStart`'s only declared pins are `body`/
    `headers`/`query`/`method`. Passing `{"a": "entry.x", "b": "entry.y"}`
    to a CallFlow whose subflow's entry is `OnStart` wires nothing (no
    pin named `a`/`b` exists on `OnStart`) — it's silently dropped, not an
    error. Two ways to actually get typed values into a subflow:
    1. Give the subflow entry a custom `@entry_node` that declares the
       exact `Input` pins you want (see the `rayflow-node` skill) — then
       CallFlow's extra inputs match those pins by name.
    2. Reuse `OnStart` and pass a single `"body": {...}` dict — that DOES
       match `OnStart`'s declared `body` pin — but the subflow then has
       to read individual fields out of that dict itself (there's no
       builtin "get a key from a dict" node; a custom node is the only way
       to destructure it further).
  - `result` (output, `dict`) holds the subflow's declared outputs, e.g.
    `"answer": "sub.result"` where `sub.result` is itself a dict like
    `{"total": 10}` if the subflow declared `outputs: {"total": "int"}`.
- **Variables**: `Get` (pure — no `exec_in` needed, evaluated on demand
  whenever another node reads its `value` output) / `Set` (needs
  `exec_in`) read/write flow-scoped state that persists across runs of the
  *same loaded flow* (not across separate flows, unless you use events —
  see below, or a shared/non-isolated `CallFlow`, see above).
- **Events** (for reactive, multi-flow systems): a flow with an `OnEvent`
  node (`event_name` input) reacts whenever another flow's `EmitEvent`
  node fires with a matching `event_name` (exact string match — there's no
  wildcard namespacing), or a flow with `OnVariableChange`
  (`variable`/`source` inputs, `source` = the flow name that owns the
  variable, empty = this same flow) reacts whenever a `Set` node writes
  that variable to a *different* value. Either way: declare the event name
  in the watching flow's top-level `events` field, then register with
  `mcp__rayflow__serve_flow_events`; unregister with `stop_flow_events`.
  Delivery is fire-and-forget, no ordering guarantee, and the source
  flow must already be loaded (served) before the watch is registered so
  its `GraphState` exists. Concrete shape (two independent flows):
  ```json
  {
    "name": "receiver",
    "events": ["demo/ping"],
    "nodes": [
      { "id": "on", "type": "OnEvent", "inputs": { "event_name": "demo/ping" } },
      { "id": "handle", "type": "EmitEvent", "exec_in": "on",
        "inputs": { "event_name": "demo/done", "payload": "on.payload" } }
    ]
  }
  ```
  Be careful with a flow that watches and rewrites its own variable — it
  can loop.

## HTTP request/response (flows served via `rayflow serve --file`)

Every served flow's trigger IS an HTTP request. `OnStart` declares
`body` (`Any`, the parsed JSON body), `headers` (`dict[str, str]`), `query`
(`dict[str, str]`), and `method` (`str`) as its own `Input` pins, so any
flow with `OnStart` as entry gets them for free — wire from `entry.headers`
etc. like any other pin. A custom `@entry_node` that wants them must
declare the same pins itself (or read `ctx.request` directly inside its
`run()`). Outside HTTP (MCP tools, programmatic calls) these just come back
empty.

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

## Common mistakes and their exact error text

Recognizing these verbatim (from `validate_flow`'s `errors`) saves a guess:

- **Type mismatch on a wire**: `pin 'X' (int) is incompatible with
  'node.output' (float). Use an explicit cast node (ToInt, ToFloat, ToStr,
  ToBool)` — int/float are never silently coerced; the same message with
  "receives a literal ... of type ..." shows up for a literal value of the
  wrong type instead of a wire.
- **Missing required input**: `pin 'X' is required but has no value or
  edge` — either the pin has no default and nothing is wired to it, or
  (very common with an LLM-authored flow) you meant to wire it but typo'd
  the source node's `id`.
- **Dangling reference**: `pin 'X' references 'Y', which doesn't exist` —
  the `"Y.pin"` reference names a node id that isn't in the graph (typo,
  or forgot to add the node).
- **Missing exec wiring**: `Node 'X' (id=Y) requires an exec input but has
  no edge` — the node has `ExecInput` but nothing points `exec_in` at it,
  so it never fires. The inverse mistake — giving a node `exec_in` it
  doesn't accept — is just silently ignored by the schema, not an error;
  check `warnings` for the "unknown key" hint if a wire seems to do nothing.
- **Ambiguous exec source**: `Exec source 'X' (Branch) has multiple exec
  outputs ['true', 'false']; specify which one with 'node_id.pin_name'` —
  you wrote `"exec_in": "branch_id"` instead of `"branch_id.true"`.
- **Entry problems**: `The flow has no entry node` (no `@entry_node`-typed
  node present) or `The flow has more than one entry node: [...]` (exactly
  one is required — if you meant one to be a subflow's entry, that only
  works through `CallFlow`, not by adding two entries to one flow).
- **Cycles**: `Data cycle detected: 'a' → ... → 'b'` / `Execution cycle
  detected: ...` — Rayflow has no implicit loop-back; use `ForEach`/`While`
  for iteration instead of wiring a node back to an earlier one.
- **CallFlow-specific**: `the 'flow' input must be a static subflow (a
  dict or a path), not a dynamic reference` (see Composing bigger flows
  above) and `CallFlow 'X': the subflow has no entry node`.
- Calling `create_flow` on a name that already exists fails on purpose
  (`A flow named 'X' already exists`) — use `update_flow` to edit.

## When a run/test gives the wrong answer, not a validation error

- `run_flow`/`test_flow` return `{"error": "..."}` (not a validation
  error) for something that failed *during* execution — e.g. a cast node
  given a value it can't convert, or a custom node's `run()` raising.
  Compare that to `test_flow`'s `passed: false` with a populated
  `mismatches` dict, which means the flow ran fine but produced the wrong
  values — a logic bug, not a crash.
- Both accept `trace=True` to get the ordered `node_start`/`node_done`/
  `edge_fire` events instead of just the final result — use it the moment
  you can't tell which node produced a wrong intermediate value by staring
  at the flow JSON. Past that point, hand off to `rayflow-debugger` rather
  than guessing further.
- Served over HTTP (`rayflow serve --file`, not MCP), a `flow_error` event
  becomes a real `500` response; a successful run defaults to `200` unless
  a node called `ctx.set_response_status`. MCP's `run_flow`/`test_flow`
  never see that status/headers layer at all — it lives outside
  `flow.outputs` by design (see HTTP request/response below).
