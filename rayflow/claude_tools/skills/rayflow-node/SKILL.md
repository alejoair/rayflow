---
name: rayflow-node
description: Use when creating or editing a custom Rayflow node — a Python class that becomes a reusable building block in flows, kept in this project's custom_nodes/ directory. Trigger on requests like "add a node that...", "I need a node for...", or when no built-in node covers something the user needs.
---

# Creating custom Rayflow nodes

A custom node is a single Python class decorated with `@ray_node`, `@engine_node`,
or `@parallel_node`, saved in `custom_nodes/<name>.py` in this project's working
directory. Rayflow discovers it automatically — there's no registration step.

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
  isolation from the main process.
- `@parallel_node` — alias of `@engine_node`, used for nodes that fork
  execution into multiple branches (rare; only if writing something like a
  custom `ForEach`).

If in doubt, use `@engine_node`.

## Category

Set `category = "..."` (a plain string English word: `"Math"`, `"Control"`,
`"Text"`, `"HTTP"`, etc. — match existing categories from `list_nodes`
rather than inventing new casing/language for the same concept).

## Creating it

Use `mcp__rayflow__create_custom_node` with `name` and `source` — it validates
Python syntax and **hot-reloads the catalog automatically**, so the node shows
up in `list_nodes`/`validate_flow` immediately, no server restart needed.
(Writing the file directly to `custom_nodes/<name>.py` also works since you
have filesystem access here, but then call `mcp__rayflow__reload_custom_nodes`
afterward — the catalog is cached in-process and won't otherwise notice a
file that appeared outside the MCP tool.)

To edit an existing one: `mcp__rayflow__get_custom_node_source` to read it,
`mcp__rayflow__update_custom_node_source` to save changes (also hot-reloads).

## After creating it

1. Confirm it appears: `mcp__rayflow__get_node` with its name.
2. Wire it into a small flow and verify it behaves as expected — see the
   `rayflow-flow` skill for the create/validate/test loop. If it produces the
   wrong output and you can't tell why, that's a job for the `rayflow-debugger`
   subagent, not more guessing here.

## Common mistakes

- Forgetting `await` on `ctx.fire(...)` (it's a coroutine).
- Declaring an output but never calling `ctx.set_output` for it before the
  node's last `fire` — downstream nodes will see the default value.
- Using a Python type (`int`, `list`) instead of the canonical string type
  (`"int"`, `"list[int]"`) in an `Input`/`Output` declaration.
- Mixing `int` and `float` pins expecting silent coercion — they're strictly
  incompatible in Rayflow's type system; cast explicitly if needed.
