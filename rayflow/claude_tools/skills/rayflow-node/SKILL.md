---
name: rayflow-node
description: Use when creating or editing a custom Rayflow node — a Python class that becomes a reusable building block in flows, kept in this project's custom_nodes/ directory. Trigger on requests like "add a node that...", "I need a node for...", or when no built-in node covers something the user needs.
---

# Creating custom Rayflow nodes

A custom node is a single Python class decorated with `@ray_node`, `@engine_node`,
`@parallel_node`, or `@entry_node`, saved in `custom_nodes/<name>.py` in this
project's working directory. Rayflow discovers it automatically — there's no
registration step.

## Scripts (use these, not just the prose below)

- `scripts/scaffold_node.py NAME [--decorator ...] [--input name:type[:default]]
  [--output name:type] [--exec] [--write]` — generates the decorator import
  line, `Input`/`Output`/`ExecInput`/`ExecOutput` declarations, and a `run()`
  with the right signature/shape from a short pin description, instead of
  hand-typing that boilerplate. Prints to stdout by default; `--write` saves
  straight to `custom_nodes/<NAME>.py`. It fills in `# TODO` markers for the
  actual logic — you still write the behavior — but the contract boilerplate
  (the part that's easy to get subtly wrong: pin order, `default=`, the
  `-> None` vs `-> dict` return shape) is generated, not typed by hand. Only
  covers `@engine_node`/`@ray_node`/`@parallel_node`; write an `@entry_node`
  by hand (see Entry nodes below — different, incompatible pin constraints).
- `scripts/check_node.py <file.py|->` — locally imports and decorates the
  node source to check the pin contract (does it actually decorate without
  raising, what pins/decorator/exec-shape it ends up with) BEFORE pushing it
  to the live catalog with `create_custom_node`. Catches things like
  `@entry_node` declaring `exec_in` (a `ValueError` at decoration time, not a
  vague runtime failure) in isolation, without touching the running server.

Typical order: `scaffold_node.py ... --write` (or hand-write the file) →
`check_node.py` on it → `mcp__rayflow__create_custom_node` /
`update_custom_node_source` to push it live.

## Before writing anything

Check whether a built-in already covers the need, and whether a custom node
with that name already exists:

- `mcp__rayflow__list_nodes` / `mcp__rayflow__get_node` — full catalog with pins.
- `mcp__rayflow__list_custom_nodes` — existing custom nodes in this project.

Only write a new node if nothing already does the job.

## The contract

```python
from rayflow.nodes.decorators import ray_node, engine_node, ExecContext, ExecInput, ExecOutput, Input, Output

@engine_node   # or @ray_node, or @parallel_node — see "which decorator" below
class MyNode:
    exec_in   = ExecInput()          # omit both exec pins for a "pure" node (see below)
    value     = Input("int", default=0)
    result    = Output("str")
    exec_out  = ExecOutput()

    async def run(self, ctx: ExecContext, value: int) -> None:
        ctx.set_output("result", str(value))
        await ctx.fire("exec_out")
```

- **Pin descriptors** (`Input`, `Output`, `ExecInput`, `ExecOutput`) are class
  attributes; their names become the pin names in the flow editor and in
  `flow_catalog`'s output.
- **Types are canonical strings**: `"int"`, `"str"`, `"bool"`, `"list[str]"`,
  `"dict[str, int]"`, `"Any"` — never a Python class.
- **A node with exec pins** must call `await ctx.fire("<exec_out_name>")` to
  continue the flow, and use `ctx.set_output(name, value)` for its outputs —
  call `set_output` *before* `fire` if a downstream node needs to read that
  output in the same step.
- **A "pure" node** (no `ExecInput`/`ExecOutput` at all) just returns a dict
  matching its `Output` names instead of using `ctx.set_output`/`ctx.fire`:
  ```python
  @engine_node
  class Double:
      x = Input("int", default=0)
      result = Output("int")
      async def run(self, ctx: ExecContext, x: int) -> dict:
          return {"result": x * 2}
  ```

## Which decorator

- `@engine_node` — runs directly inside the flow engine, no extra process.
  **Default choice** for ordinary logic (string/number/list manipulation,
  calling an HTTP API, etc.). Stateless between flow runs.
- `@ray_node` — runs as a Ray actor (with exec pins) or task (without). Use it
  only if the node genuinely needs persistent state across executions (an
  actor instantiated once, living until the flow is unloaded) or CPU/GPU
  isolation from the main process. Still just needs `ray` importable to
  decorate — actually invoking it needs a live `ray.init()`'d cluster
  (`rayflow serve` does this for you).
- `@parallel_node` — same runtime as `@engine_node` plus a fork/join
  contract: the node's own `run()` discovers its dynamic branch exec
  outputs at runtime via `await ctx.exec_outputs_except("joined")` and
  launches them with `asyncio.gather`, the same way the builtin `Parallel`
  node does. Only write one of these if you need a custom fork/join shape
  `Parallel`/`ForEach` don't already cover (rare).
- `@entry_node` — a flow's trigger, not an ordinary logic node. Different,
  mutually exclusive constraints from the three above: must NOT declare
  `exec_in` (nothing inside a graph can fire an entry), MUST declare at
  least one `ExecOutput`, and can't be combined with `@ray_node`. See
  "Entry nodes" below — it's covered separately because of these
  constraints and because it receives an `EntryContext` (with `.request`)
  instead of a plain `ExecContext`.

If in doubt, use `@engine_node`.

## Category

Set `category = "..."` (a plain string English word: `"Math"`, `"Control"`,
`"Text"`, `"HTTP"`, etc. — match existing categories from `list_nodes`
rather than inventing new casing/language for the same concept).

## Entry nodes

Entry nodes (any `@entry_node`) are the flow's trigger. They declare their
own `Input`/`Output` pins like any other node; the engine populates the
inputs from the request body (POST `{"message": "..."}` → entry's `message`
Input). If an entry doesn't define `run()`, the engine auto-mirrors each
declared Input as an output of the same name, so downstream nodes can
cable `entry.x` with zero code (this is exactly how the builtin `OnStart`
works — it declares `body`/`headers`/`query`/`method` and has no `run()`).
Entries also have access to `ctx.request` (`body`/`headers`/`query`/
`method`) via the `EntryContext` they receive — a plain `ExecContext` for
non-entry nodes has no `.request` at all.

A common reason to write a custom entry: when you want a subflow (invoked
via `CallFlow` from another flow — see the `rayflow-flow` skill) to accept
individually-typed inputs. `OnStart`'s only declared pins are `body`/
`headers`/`query`/`method`, so a `CallFlow`'s extra `inputs` only wire
into a subflow whose entry declares pins with those exact names — a
minimal typed entry looks like:

```python
@entry_node
class SumEntry:
    """Entry for a subflow that expects two named ints (a, b)."""
    a = Input("int", default=0)
    b = Input("int", default=0)
    exec_out = ExecOutput()
    # No run() needed — auto-passthrough mirrors a/b as outputs of the
    # same name, so the subflow's other nodes can wire "entry.a"/"entry.b".
```

### Optional frontend bundle

A node declared with `@entry_node` may also declare `frontend = "<dir_name>"`
— the name of a directory of static assets (HTML/JS/CSS) sibling to the
node's `.py` file. When a **served** flow's entry node declares it
(`rayflow serve --file`, not editor-managed flows), the server mounts that
directory at `GET /flows/{flow_name}/ui` so the flow ships with its own UI.

```python
@entry_node
class MyTrigger:
    message = Input("str")              # populated from the request body
    message_out = Output("str")         # produced by run()
    frontend = "my_trigger_ui"          # → custom_nodes/my_trigger_ui/index.html
    exec_out = ExecOutput()

    async def run(self, ctx: EntryContext, message: str) -> None:
        # ctx.request is available here — body/headers/query/method.
        ctx.set_output("message_out", message)
        await ctx.fire("exec_out")
```

The bundle lives next to the source file: for a custom node in
`custom_nodes/my_trigger.py`, the bundle goes in
`custom_nodes/my_trigger_ui/` (at minimum an `index.html`). The framework
serves the files; the bundle's JS is responsible for talking to the flow
over the normal `POST /flows/{name}/run` endpoint — `frontend` only selects
*what UI to serve*, it is not a new transport. The built-in `ChatTrigger`
node (`rayflow/nodes/builtin/control.py`) is the reference example (a chat
page that POSTs `{message: ...}` and renders the flow's outputs). Creating
the bundle directory is manual — `create_custom_node`/`scaffold_node.py`
only write the `.py` file.

## Creating it

Use `mcp__rayflow__create_custom_node` with `name` and `source` — it validates
Python syntax and **hot-reloads the catalog automatically**, so the node shows
up in `list_nodes`/`validate_flow` immediately, no server restart needed.
(Writing the file directly to `custom_nodes/<name>.py` — by hand, or via
`scaffold_node.py --write` — also works since you have filesystem access
here, but then call `mcp__rayflow__reload_custom_nodes` afterward — the
catalog is cached in-process and won't otherwise notice a file that
appeared outside the MCP tool.) Either way, prefer running
`scripts/check_node.py` on the source FIRST — it catches syntax and
decorator/pin-contract errors locally, before they show up as a rejected
`create_custom_node` call or, worse, a node that registers with a subtly
wrong pin shape.

A name collision at this point isn't just "file already exists": the
catalog itself refuses two different classes registered under the same
node name (`Duplicate node 'X': already registered as ..., attempted to
register ...`) — `list_custom_nodes`/`list_nodes` first to steer clear of
both a builtin name (`Add`, `Branch`, `OnStart`, …) and an existing custom
one.

To edit an existing one: `mcp__rayflow__get_custom_node_source` to read it,
`mcp__rayflow__update_custom_node_source` to save changes (also hot-reloads).

## After creating it

1. Confirm it appears: `mcp__rayflow__get_node` with its name.
2. Wire it into a small flow and verify it behaves as expected — see the
   `rayflow-flow` skill for the create/validate/test loop (its
   `scripts/validate_flow.py`/`scripts/batch_test.py` work against a flow
   using your new node exactly like any builtin one, since the catalog
   doesn't distinguish). If it produces the wrong output and you can't
   tell why, that's a job for the `rayflow-debugger` subagent, not more
   guessing here.

## Common mistakes

- Forgetting `await` on `ctx.fire(...)` (it's a coroutine) — `check_node.py`
  won't catch this one (it's a runtime bug, not a decoration-time error);
  it only surfaces once the node actually runs.
- Declaring an output but never calling `ctx.set_output` for it before the
  node's last `fire` — downstream nodes will see the default value, not an
  error.
- Using a Python type (`int`, `list`) instead of the canonical string type
  (`"int"`, `"list[int]"`) in an `Input`/`Output` declaration — raises
  `TypeError_` from `rayflow.types` immediately at import/decoration time
  (so `check_node.py`/`create_custom_node` catches it before it ever
  reaches a flow).
- Mixing `int` and `float` pins expecting silent coercion — they're strictly
  incompatible in Rayflow's type system; cast explicitly if needed (see the
  `rayflow-flow` skill's cast-node guidance).
- `@entry_node` declaring `exec_in`, or declaring zero `ExecOutput`s, or
  combined with `@ray_node` — all three raise `ValueError` at decoration
  time (`check_node.py` reports this as a top-level error, not a "0 nodes
  found" silence).
- Registering a node whose name collides with a builtin or another custom
  node (see "Creating it" above) — check `list_nodes`/`list_custom_nodes`
  first, don't assume the name is free.
- Any non-entry node with exec pins whose `run()` never calls `ctx.fire(...)`
  hangs the flow right there — only `@entry_node` gets an auto-fire safety
  net when `run()` doesn't fire anything; an ordinary `@engine_node`/
  `@ray_node` you forgot to finish just stalls with no error.
