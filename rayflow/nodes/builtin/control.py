"""Flow-control nodes."""
import asyncio
import inspect
from typing import Any

from rayflow.nodes.decorators import (
    EntryContext,
    ExecContext,
    ExecInput,
    ExecOutput,
    Input,
    Output,
    engine_node,
    entry_node,
    parallel_node,
    ray_node,
)


class _MapCaptureCtx:
    """Capture context for Map: collects set_output, ignores fire().

    Lets any inline node's run() execute (no Ray actors) while capturing its
    data outputs without propagating the exec flow.
    Variable/event operations are delegated to the parent context.
    """

    def __init__(self, parent: ExecContext):
        self._parent = parent
        self.outputs: dict[str, Any] = {}

    async def fire(self, pin_name: str) -> None:
        pass

    def set_output(self, pin_name: str, value: Any) -> None:
        self.outputs[pin_name] = value

    def get_variable(self, name: str) -> Any:
        return self._parent.get_variable(name)

    def set_variable(self, name: str, value: Any) -> None:
        self._parent.set_variable(name, value)

    def emit_event(self, event_name: str, payload: Any = None) -> None:
        self._parent.emit_event(event_name, payload)

    async def exec_outputs_except(self, *exclude: str) -> list[str]:
        return []


@entry_node
class OnStart:
    """Entry point of a flow triggered by a direct call (HTTP or programmatic).

    Declares the standard HTTP request envelope as inputs so the author can
    cable them downstream. Defaults are empty so non-HTTP callers (MCP,
    execute() direct) get sensible empty values instead of None. Without
    run(), the engine auto-passthroughs each Input as an output of the same
    name. For triggers that need to compute something before firing
    exec_out, override run() and use ctx.set_output.
    """
    category = "Control"
    body    = Input("Any", default={})
    headers = Input("dict[str, str]", default={})
    query   = Input("dict[str, str]", default={})
    method  = Input("str", default="GET")
    exec_out = ExecOutput()


@entry_node
class ChatTrigger:
    """Entry point with a built-in chat UI.

    Declares `message` as the user's chat input (POSTed by the bundled UI
    at /flows/{name}/ui). Defines run() to forward it as `message_out`,
    which downstream nodes cable as `chat.message_out`. The bundle's JS
    POSTs {"message": "..."} to /flows/{name}/run — same endpoint as any
    caller, no special transport.
    """
    category = "Control"
    frontend = "chat_trigger_frontend"
    message = Input("str")
    message_out = Output("str")
    exec_out = ExecOutput()

    async def run(self, ctx: EntryContext, message: str) -> None:
        ctx.set_output("message_out", message)
        await ctx.fire("exec_out")


@entry_node
class EntryXY:
    """Convenience entry declaring two int inputs (x, y) — used by tests
    and examples that need a fixed-shape trigger without the full HTTP
    envelope. Auto-passthrough mirrors x and y as outputs."""
    category = "Control"
    x = Input("int")
    y = Input("int")
    exec_out = ExecOutput()


@entry_node
class EntryX:
    """Convenience entry declaring a single int input (x). Used by tests
    and examples. Auto-passthrough mirrors x as output."""
    category = "Control"
    x = Input("int")
    exec_out = ExecOutput()


@entry_node
class EntryAB:
    """Convenience entry declaring two int inputs (a, b). Used by tests
    and examples (especially subflow CallFlow tests). Auto-passthrough
    mirrors a and b as outputs."""
    category = "Control"
    a = Input("int")
    b = Input("int")
    exec_out = ExecOutput()


@entry_node
class EntryN:
    """Convenience entry declaring a single int input (n). Used by tests
    and examples. Auto-passthrough mirrors n as output."""
    category = "Control"
    n = Input("int")
    exec_out = ExecOutput()


@entry_node
class EntryABC:
    """Convenience entry declaring three int inputs (a, b, c). Used by
    examples. Auto-passthrough mirrors a, b, c as outputs."""
    category = "Control"
    a = Input("int")
    b = Input("int")
    c = Input("int")
    exec_out = ExecOutput()


@entry_node
class EntryItems:
    """Convenience entry declaring a single list input (items). Used by
    examples that loop over a list. Auto-passthrough mirrors items as
    output."""
    category = "Control"
    items = Input("list")
    exec_out = ExecOutput()


@entry_node
class EntryNumbersThreshold:
    """Convenience entry declaring list (numbers) + int (threshold). Used
    by examples that filter a list. Auto-passthrough mirrors both as
    outputs."""
    category = "Control"
    numbers = Input("list")
    threshold = Input("int")
    exec_out = ExecOutput()


@entry_node
class EntryXBool:
    """Convenience entry declaring int (x) + bool (use_positive). Used by
    examples that branch on a flag. Auto-passthrough mirrors both as
    outputs."""
    category = "Control"
    x = Input("int")
    use_positive = Input("bool")
    exec_out = ExecOutput()

@engine_node
class FlowOutput:
    """Exit point of the flow.

    Its data inputs are generated at build time from the flow's `outputs`.
    """
    category = "Control"
    exec_in = ExecInput()

    async def run(self, ctx: ExecContext) -> None:
        pass


@ray_node
class Branch:
    """Conditional branch. Fires `true` or `false` based on `condition`."""
    category = "Control"
    exec_in = ExecInput()
    condition = Input("bool", default=False)
    true = ExecOutput()
    false = ExecOutput()

    async def run(self, ctx: ExecContext, condition: bool) -> None:
        await ctx.fire("true" if condition else "false")


@ray_node
class Sequence:
    """Fires its exec outputs in sequential order."""
    category = "Control"
    exec_in = ExecInput()
    then_0 = ExecOutput()
    then_1 = ExecOutput()
    then_2 = ExecOutput()

    async def run(self, ctx: ExecContext) -> None:
        await ctx.fire("then_0")
        await ctx.fire("then_1")
        await ctx.fire("then_2")


@parallel_node
class Parallel:
    """Parallel fork/join. Launches N branches simultaneously.

    Branch pins (branch_0, branch_1, …, branch_N) are dynamically injected
    at build time from the JSON wiring. Branches are discovered at runtime
    via ctx.exec_outputs_except("joined") and launched with asyncio.gather.
    The 'joined' pin fires once every branch has finished.
    """
    category = "Loops"
    exec_in = ExecInput()
    joined = ExecOutput()

    async def run(self, ctx: ExecContext) -> None:
        branches = await ctx.exec_outputs_except("joined")
        await asyncio.gather(*[ctx.fire(b) for b in branches])
        await ctx.fire("joined")


@engine_node
class ForEach:
    """Iterates over an array, firing loop_body for each element."""
    category = "Loops"
    exec_in = ExecInput()
    array = Input("list", default=None)
    loop_body = ExecOutput()
    completed = ExecOutput()
    element = Output("Any")
    index = Output("int")

    async def run(self, ctx: ExecContext, array: list) -> None:
        for i, element in enumerate(array or []):
            ctx.set_output("element", element)
            ctx.set_output("index", i)
            await ctx.fire("loop_body")
        await ctx.fire("completed")


@engine_node
class While:
    """Iterates while a boolean variable stays True.

    Reads the `condition_var` variable from GraphState at the start of each
    iteration. The loop body is responsible for updating it (via Set) to
    control exit.

    Example JSON usage:
        variables: [{"name": "keep_going", "type": "bool", "default": true}]
        {"id": "w", "type": "While", "exec_in": "entry",
         "inputs": {"condition_var": "keep_going"}}
    """
    exec_in = ExecInput()
    condition_var = Input("str", default="")
    loop_body = ExecOutput()
    completed = ExecOutput()

    async def run(self, ctx: ExecContext, condition_var: str) -> None:
        while ctx.get_variable(condition_var):
            await ctx.fire("loop_body")
        await ctx.fire("completed")


@engine_node
class Map:
    """Applies a transform node to each element of an array.

    `node_type` is the catalog node type's name (a string literal in the
    JSON). The element is passed to the node's first data input; remaining
    inputs use their declared defaults. The first data output of each
    invocation is collected into the result list.

    Works with any node in the catalog (pure or exec, engine or ray_node).
    The applied node's exec outputs are ignored — Map only captures data.

    Example JSON usage:
        {"id": "m", "type": "Map", "exec_in": "entry",
         "inputs": {"array": "entry.items", "node_type": "ToStr"}}
    """
    exec_in = ExecInput()
    array = Input("list", default=None)
    node_type = Input("str", default="")
    result = Output("list")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, array: list, node_type: str) -> None:
        from rayflow.nodes.registry import get_catalog
        entry = get_catalog().get(node_type)
        if entry is None:
            raise RuntimeError(f"Map: node '{node_type}' not found in the catalog")
        cls, meta = entry
        if not meta.inputs:
            raise RuntimeError(f"Map: '{node_type}' has no data inputs")
        if not meta.outputs:
            raise RuntimeError(f"Map: '{node_type}' has no data outputs")

        first_in = meta.inputs[0].name
        first_out = meta.outputs[0].name
        base_inputs = {pin.name: pin.default for pin in meta.inputs if pin.has_default}

        results = []
        for element in (array or []):
            inputs = {**base_inputs, first_in: element}
            node_instance = cls()
            capture = _MapCaptureCtx(ctx)
            ret = node_instance.run(capture, **inputs)
            if inspect.isawaitable(ret):
                ret = await ret
            # pure nodes return a dict; exec nodes use set_output (ret=None)
            if isinstance(ret, dict):
                results.append(ret.get(first_out))
            else:
                results.append(capture.outputs.get(first_out))

        ctx.set_output("result", results)
        await ctx.fire("exec_out")
