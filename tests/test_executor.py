"""End-to-end execution tests with Ray."""
import pytest
import ray
import rayflow
from rayflow.nodes.registry import reset_catalog
from tests.helpers import run_once


@pytest.fixture(autouse=True)
def ray_init():
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, namespace="rayflow")
    reset_catalog()
    yield


def test_flow_sum():
    result = run_once({"name": "suma", "inputs": {"a": "int", "b": "int"},
        "outputs": {"result": "int"}, "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "add", "type": "Add", "exec_in": "entry",
             "inputs": {"a": "entry.a", "b": "entry.b"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "add",
             "inputs": {"result": "add.result"}},
        ]}, a=3, b=4)
    assert result["result"] == 7


def test_fan_out_both_nodes_run():
    """An exec output wired to two nodes — both must run."""
    from rayflow.nodes.decorators import ray_node, ExecContext, Input, Output, ExecInput, ExecOutput
    from rayflow.nodes.registry import get_catalog

    @ray_node
    class SetFlag:
        exec_in = ExecInput()
        flag_name = Input("str", default="")
        exec_out = ExecOutput()

        async def run(self, ctx: ExecContext, flag_name: str) -> None:
            await ctx.fire("exec_out")

    catalog = get_catalog()
    catalog.register(SetFlag)

    # entry fires node_a and node_b in parallel (fan-out)
    result = run_once({
        "name": "fanout",
        "outputs": {"meta_a": "dict", "meta_b": "dict"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "node_a", "type": "SetFlag", "exec_in": "entry",
             "inputs": {"flag_name": "a"}},
            {"id": "node_b", "type": "SetFlag", "exec_in": "entry",
             "inputs": {"flag_name": "b"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": ["node_a", "node_b"],
             "inputs": {"meta_a": "node_a.meta", "meta_b": "node_b.meta"}},
        ],
    })
    assert result["meta_a"]["id"] == "node_a"
    assert result["meta_b"]["id"] == "node_b"


def test_parallel_fork_join():
    """A Parallel node launches branch_0 and branch_1 simultaneously, joined when done."""
    result = run_once({
        "name": "parallel_test",
        "outputs": {"sum_a": "int", "sum_b": "int"},
        "nodes": [
            {"id": "entry", "type": "FlowInput",
             "inputs": {}},
            {"id": "par", "type": "Parallel", "exec_in": "entry"},
            {"id": "add_a", "type": "Add", "exec_in": "par.branch_0",
             "inputs": {"a": 10, "b": 5}},
            {"id": "add_b", "type": "Add", "exec_in": "par.branch_1",
             "inputs": {"a": 20, "b": 3}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "par.joined",
             "inputs": {"sum_a": "add_a.result", "sum_b": "add_b.result"}},
        ],
    })
    assert result["sum_a"] == 15
    assert result["sum_b"] == 23


def test_parallel_with_foreach_in_branch():
    """Parallel with an @engine_node (ForEach) inside a branch — correct isolation."""
    result = run_once({
        "name": "parallel_foreach",
        "inputs": {"items": "list"},
        "outputs": {"done": "dict"},
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "par", "type": "Parallel", "exec_in": "entry"},
            {"id": "foreach", "type": "ForEach", "exec_in": "par.branch_0",
             "inputs": {"array": "entry.items"}},
            {"id": "add_elem", "type": "Add", "exec_in": "foreach.loop_body",
             "inputs": {"a": "foreach.element", "b": 0}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "par.joined",
             "inputs": {"done": "par.meta"}},
        ],
    }, items=[1, 2, 3])
    assert result["done"]["type"] == "Parallel"


def test_parallel_n_branches():
    """Parallel with 4 dynamic branches (branch_0 through branch_3)."""
    result = run_once({
        "name": "parallel_4branches",
        "outputs": {"r0": "int", "r1": "int", "r2": "int", "r3": "int"},
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "par", "type": "Parallel", "exec_in": "entry"},
            {"id": "add_0", "type": "Add", "exec_in": "par.branch_0",
             "inputs": {"a": 1, "b": 10}},
            {"id": "add_1", "type": "Add", "exec_in": "par.branch_1",
             "inputs": {"a": 2, "b": 20}},
            {"id": "add_2", "type": "Add", "exec_in": "par.branch_2",
             "inputs": {"a": 3, "b": 30}},
            {"id": "add_3", "type": "Add", "exec_in": "par.branch_3",
             "inputs": {"a": 4, "b": 40}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "par.joined",
             "inputs": {
                 "r0": "add_0.result",
                 "r1": "add_1.result",
                 "r2": "add_2.result",
                 "r3": "add_3.result",
             }},
        ],
    })
    assert result["r0"] == 11
    assert result["r1"] == 22
    assert result["r2"] == 33
    assert result["r3"] == 44


def test_parallel_with_pure_engine_node():
    """Parallel with branches made only of @engine_node (Branch + Set), no @ray_node."""
    result = run_once({
        "name": "parallel_engine_only",
        "outputs": {"done": "dict"},
        "variables": [{"name": "x", "type": "int", "default": 0}],
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "set_init", "type": "Set", "exec_in": "entry",
             "inputs": {"variable_name": "x", "value": 100}},
            {"id": "par", "type": "Parallel", "exec_in": "set_init"},
            {"id": "branch_a", "type": "Branch", "exec_in": "par.branch_0",
             "inputs": {"condition": True}},
            {"id": "set_a", "type": "Set", "exec_in": "branch_a.true",
             "inputs": {"variable_name": "x", "value": 200}},
            {"id": "branch_b", "type": "Branch", "exec_in": "par.branch_1",
             "inputs": {"condition": True}},
            {"id": "set_b", "type": "Set", "exec_in": "branch_b.true",
             "inputs": {"variable_name": "x", "value": 300}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "par.joined",
             "inputs": {"done": "par.meta"}},
        ],
    })
    assert result["done"]["type"] == "Parallel"


def test_parallel_nested():
    """A Parallel inside a branch of another Parallel (nested fork/join)."""
    result = run_once({
        "name": "nested_parallel",
        "outputs": {"r0": "int", "r1": "int", "r2": "int"},
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "par_outer", "type": "Parallel", "exec_in": "entry"},
            {"id": "add_a", "type": "Add", "exec_in": "par_outer.branch_0",
             "inputs": {"a": 1, "b": 2}},
            {"id": "par_inner", "type": "Parallel", "exec_in": "par_outer.branch_1"},
            {"id": "add_b0", "type": "Add", "exec_in": "par_inner.branch_0",
             "inputs": {"a": 10, "b": 20}},
            {"id": "add_b1", "type": "Add", "exec_in": "par_inner.branch_1",
             "inputs": {"a": 30, "b": 40}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "par_outer.joined",
             "inputs": {
                 "r0": "add_a.result",
                 "r1": "add_b0.result",
                 "r2": "add_b1.result",
             }},
        ],
    })
    assert result["r0"] == 3
    assert result["r1"] == 30
    assert result["r2"] == 70


# ---------------------------------------------------------------------------
# AND/OR exec_in semantics
# ---------------------------------------------------------------------------

def test_and_join_waits_for_both_branches():
    """Fan-out of 2 branches; the exit node with a list exec_in (AND) waits for both."""
    result = run_once({
        "name": "and_join_basic",
        "outputs": {"r0": "int", "r1": "int"},
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "add_a", "type": "Add", "exec_in": "entry",
             "inputs": {"a": 1, "b": 10}},
            {"id": "add_b", "type": "Add", "exec_in": "entry",
             "inputs": {"a": 2, "b": 20}},
            {"id": "exit", "type": "FlowOutput",
             "exec_in": ["add_a", "add_b"],
             "inputs": {"r0": "add_a.result", "r1": "add_b.result"}},
        ],
    })
    assert result["r0"] == 11
    assert result["r1"] == 22


def test_and_join_waits_for_slow_branch():
    """The AND-join waits for the branch with more nodes in its chain."""
    result = run_once({
        "name": "and_join_slow_branch",
        "outputs": {"r0": "int", "r1": "int"},
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            # fast branch: a single node
            {"id": "fast", "type": "Add", "exec_in": "entry",
             "inputs": {"a": 1, "b": 0}},
            # slow branch: two chained nodes
            {"id": "slow1", "type": "Add", "exec_in": "entry",
             "inputs": {"a": 10, "b": 0}},
            {"id": "slow2", "type": "Add", "exec_in": "slow1",
             "inputs": {"a": "slow1.result", "b": 5}},
            {"id": "exit", "type": "FlowOutput",
             "exec_in": ["fast", "slow2"],
             "inputs": {"r0": "fast.result", "r1": "slow2.result"}},
        ],
    })
    assert result["r0"] == 1
    assert result["r1"] == 15


def test_and_join_inside_loop_resets():
    """An AND join visited on every iteration must ALWAYS wait for both branches.

    Regression: _exec_arrivals wasn't reset once ready, so after the first
    iteration the join stayed permanently "ready" and fired on every single
    arrival (2x per iteration instead of 1x). With 3 iterations, the counter
    ended up at 5 instead of 3.
    """
    result = run_once({
        "name": "and_join_in_loop",
        "inputs": {"items": "list"},
        "outputs": {"count": "int"},
        "variables": [{"name": "jc", "type": "int", "default": 0}],
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "loop", "type": "ForEach", "exec_in": "entry",
             "inputs": {"array": "entry.items"}},
            # fan-out of the loop body into two branches
            {"id": "na", "type": "Add", "exec_in": "loop.loop_body", "inputs": {"a": 0, "b": 0}},
            {"id": "nb", "type": "Add", "exec_in": "loop.loop_body", "inputs": {"a": 0, "b": 0}},
            # AND join: increments jc once per iteration (if it waits for both)
            {"id": "getjc", "type": "Get", "inputs": {"variable_name": "jc"}},
            {"id": "inc", "type": "Add", "exec_in": ["na", "nb"],
             "inputs": {"a": "getjc.value", "b": 1}},
            {"id": "setjc", "type": "Set", "exec_in": "inc",
             "inputs": {"variable_name": "jc", "value": "inc.result"}},
            {"id": "getfinal", "type": "Get", "inputs": {"variable_name": "jc"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "loop.completed",
             "inputs": {"count": "getfinal.value"}},
        ],
    }, items=[1, 2, 3])
    assert result["count"] == 3  # once per iteration, not 5


def test_or_join_post_branch():
    """Explicit OR: convergence after a Branch; only one branch runs."""
    result = run_once({
        "name": "or_join_branch",
        "inputs": {"cond": "bool"},
        "outputs": {"out": "int"},
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "br", "type": "Branch", "exec_in": "entry",
             "inputs": {"condition": "entry.cond"}},
            {"id": "true_add", "type": "Add", "exec_in": "br.true",
             "inputs": {"a": 1, "b": 0}},
            {"id": "false_add", "type": "Add", "exec_in": "br.false",
             "inputs": {"a": 2, "b": 0}},
            {"id": "exit", "type": "FlowOutput",
             "exec_in": {"or": ["true_add", "false_add"]},
             "inputs": {"out": "true_add.result"}},
        ],
    }, cond=True)
    assert result["out"] == 1


def test_or_join_post_branch_false():
    """OR: the Branch's false branch also reaches the join."""
    result = run_once({
        "name": "or_join_branch_false",
        "inputs": {"cond": "bool"},
        "outputs": {"out": "int"},
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "br", "type": "Branch", "exec_in": "entry",
             "inputs": {"condition": "entry.cond"}},
            {"id": "true_add", "type": "Add", "exec_in": "br.true",
             "inputs": {"a": 1, "b": 0}},
            {"id": "false_add", "type": "Add", "exec_in": "br.false",
             "inputs": {"a": 99, "b": 0}},
            {"id": "exit", "type": "FlowOutput",
             "exec_in": {"or": ["true_add", "false_add"]},
             "inputs": {"out": "false_add.result"}},
        ],
    }, cond=False)
    assert result["out"] == 99


# ---------------------------------------------------------------------------
# Pure comparisons
# ---------------------------------------------------------------------------

def test_pure_comparison_lazy():
    """LessThan evaluated lazily as a FlowOutput data input, with no exec wire."""
    result = run_once({
        "name": "lt_lazy",
        "inputs": {"x": "int"},
        "outputs": {"is_small": "bool"},
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "lt", "type": "LessThan", "inputs": {"a": "entry.x", "b": 10}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "entry",
             "inputs": {"is_small": "lt.result"}},
        ],
    }, x=5)
    assert result["is_small"] is True


def test_pure_comparison_as_branch_condition():
    """A pure GreaterThan feeds Branch.condition directly."""
    result = run_once({
        "name": "gt_branch",
        "inputs": {"x": "int"},
        "outputs": {"out": "int"},
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "gt", "type": "GreaterThan", "inputs": {"a": "entry.x", "b": 0}},
            {"id": "br", "type": "Branch", "exec_in": "entry",
             "inputs": {"condition": "gt.result"}},
            {"id": "pos", "type": "Add", "exec_in": "br.true",
             "inputs": {"a": "entry.x", "b": 0}},
            {"id": "neg", "type": "Add", "exec_in": "br.false",
             "inputs": {"a": "entry.x", "b": 0}},
            {"id": "exit", "type": "FlowOutput",
             "exec_in": {"or": ["pos", "neg"]},
             "inputs": {"out": "entry.x"}},
        ],
    }, x=7)
    assert result["out"] == 7


# ---------------------------------------------------------------------------
# While
# ---------------------------------------------------------------------------

def test_while_iterates_until_condition():
    """While with a variable-based condition — counts up to 5."""
    result = run_once({
        "name": "while_count",
        "outputs": {"count": "int"},
        "variables": [
            {"name": "i",    "type": "int",  "default": 0},
            {"name": "keep", "type": "bool", "default": True},
        ],
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "w", "type": "While", "exec_in": "entry",
             "inputs": {"condition_var": "keep"}},
            # loop body
            {"id": "get_i",     "type": "Get", "inputs": {"variable_name": "i"}},
            {"id": "add",       "type": "Add", "exec_in": "w.loop_body",
             "inputs": {"a": "get_i.value", "b": 1}},
            {"id": "set_i",     "type": "Set", "exec_in": "add",
             "inputs": {"variable_name": "i", "value": "add.result"}},
            {"id": "lt",        "type": "LessThan",
             "inputs": {"a": "add.result", "b": 5}},
            {"id": "set_keep",  "type": "Set", "exec_in": "set_i",
             "inputs": {"variable_name": "keep", "value": "lt.result"}},
            # completed
            {"id": "get_final", "type": "Get", "inputs": {"variable_name": "i"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "w.completed",
             "inputs": {"count": "get_final.value"}},
        ],
    })
    assert result["count"] == 5


def test_while_zero_iterations():
    """While with a condition that's False from the start: zero iterations."""
    result = run_once({
        "name": "while_zero",
        "outputs": {"count": "int"},
        "variables": [
            {"name": "i",    "type": "int",  "default": 0},
            {"name": "keep", "type": "bool", "default": False},
        ],
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "w", "type": "While", "exec_in": "entry",
             "inputs": {"condition_var": "keep"}},
            {"id": "get_i", "type": "Get", "inputs": {"variable_name": "i"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "w.completed",
             "inputs": {"count": "get_i.value"}},
        ],
    })
    assert result["count"] == 0


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

def test_map_with_ray_node_exec():
    """Map applies an exec @ray_node (ToStr) to each element of the array."""
    result = run_once({
        "name": "map_tostr",
        "inputs": {"items": "list"},
        "outputs": {"strings": "list"},
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "m", "type": "Map", "exec_in": "entry",
             "inputs": {"array": "entry.items", "node_type": "ToStr"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "m",
             "inputs": {"strings": "m.result"}},
        ],
    }, items=[1, 2, 3])
    assert result["strings"] == ["1", "2", "3"]


def test_map_with_pure_engine_node():
    """Map applies a pure @engine_node (Get) — always returns the same value."""
    result = run_once({
        "name": "map_get",
        "inputs": {"items": "list"},
        "outputs": {"values": "list"},
        "variables": [{"name": "magic", "type": "int", "default": 42}],
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "m", "type": "Map", "exec_in": "entry",
             "inputs": {"array": "entry.items", "node_type": "Get"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "m",
             "inputs": {"values": "m.result"}},
        ],
    }, items=["magic", "magic", "magic"])
    assert result["values"] == [42, 42, 42]


# ---------------------------------------------------------------------------
# Output isolation between runs (RunContext)
# ---------------------------------------------------------------------------

def _execute_collect(name: str, inputs: dict) -> dict | None:
    """Runs an already-loaded flow and returns flow_done's result."""
    result = None
    for evt in rayflow.execute(name, inputs):
        if evt.get("event") == "flow_done":
            result = evt.get("result")
        elif evt.get("event") == "flow_error":
            raise AssertionError(f"flow_error: {evt.get('error')}")
    return result


def test_outputs_not_stale_between_runs():
    """A node not fired in this run leaves no output visible to the next one.

    Regression test for the latent bug that motivated RunContext: with
    node_outputs shared in GraphState, `producer`'s output (run 1, true
    branch) stayed stored and `reader` would read it in run 2 (false
    branch) even though producer had NOT fired in that run — it got a
    stale 100 instead of its default.

    With per-run node_outputs, reader falls back to its default (0) in run
    2. The flow is loaded ONCE and run twice: staleness only shows up if
    scratch state persists across runs of the same loaded flow.
    """
    flow = {
        "name": "stale_check",
        "inputs": {"cond": "bool"},
        "outputs": {"via_producer": "int", "via_reader": "int"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "br", "type": "Branch", "exec_in": "entry",
             "inputs": {"condition": "entry.cond"}},
            # true branch: produces 100
            {"id": "producer", "type": "Add", "exec_in": "br.true",
             "inputs": {"a": 100, "b": 0}},
            # false branch: reads producer.result (not fired in this run)
            {"id": "reader", "type": "Add", "exec_in": "br.false",
             "inputs": {"a": "producer.result", "b": 0}},
            {"id": "exit", "type": "FlowOutput",
             "exec_in": {"or": ["producer", "reader"]},
             "inputs": {"via_producer": "producer.result",
                        "via_reader": "reader.result"}},
        ],
    }

    rayflow.load(flow)
    try:
        # Run 1: cond=True → producer fires, leaves result=100 in the state
        r1 = _execute_collect("stale_check", {"cond": True})
        assert r1["via_producer"] == 100  # producer really ran

        # Run 2: cond=False → reader runs and reads producer.result.
        # Without per-run isolation it would read 100 (stale); with
        # RunContext it falls back to the default 0.
        r2 = _execute_collect("stale_check", {"cond": False})
        assert r2["via_reader"] == 0, (
            f"reader read {r2['via_reader']} — stale output from the previous run"
        )
    finally:
        rayflow.unload("stale_check")


# ---------------------------------------------------------------------------
# OnStart's request pins + ctx.set_response_status/set_response_header
# ---------------------------------------------------------------------------

def _execute_flow_done_event(name: str, inputs: dict) -> dict:
    """Runs an already-loaded flow and returns the raw flow_done event
    (not just its 'result'), so response_status/response_headers are
    visible too."""
    evt_out = None
    for evt in rayflow.execute(name, inputs):
        if evt.get("event") == "flow_done":
            evt_out = evt
        elif evt.get("event") == "flow_error":
            raise AssertionError(f"flow_error: {evt.get('error')}")
    assert evt_out is not None
    return evt_out


def test_onstart_request_pins_default_when_not_triggered_over_http():
    """Calling execute() directly (no server.py involved) never supplies
    headers/query/body/method in flow_inputs — a node wiring from
    entry.headers falls back to its own Input's declared default, per
    _resolve_pin's fallback chain (node_outputs miss -> not a pure node ->
    consumer's default). Uses a custom node with an explicit {} default
    rather than wiring straight into FlowOutput, whose auto-generated
    dynamic pins always default to None regardless of declared type."""
    from rayflow.nodes.decorators import engine_node, ExecContext, ExecInput, ExecOutput, Input, Output
    from rayflow.nodes.registry import get_catalog

    @engine_node
    class EchoHeaders:
        exec_in = ExecInput()
        headers = Input("dict[str, str]", default={})
        out = Output("dict")
        exec_out = ExecOutput()

        async def run(self, ctx: ExecContext, headers: dict) -> None:
            ctx.set_output("out", headers)
            await ctx.fire("exec_out")

    get_catalog().register(EchoHeaders)

    flow = {
        "name": "no_http_context",
        "outputs": {"headers": "dict"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "echo", "type": "EchoHeaders", "exec_in": "entry", "inputs": {"headers": "entry.headers"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "echo", "inputs": {"headers": "echo.out"}},
        ],
    }
    rayflow.load(flow)
    try:
        result = _execute_collect("no_http_context", {})
        assert result["headers"] == {}
    finally:
        rayflow.unload("no_http_context")


def test_set_response_status_and_header_engine_node():
    """ctx.set_response_status()/set_response_header() land in the
    flow_done event via the engine_node local-closure path (no RPC)."""
    from rayflow.nodes.decorators import engine_node, ExecContext, ExecInput, ExecOutput
    from rayflow.nodes.registry import get_catalog

    @engine_node
    class SetRespEngine:
        exec_in = ExecInput()
        exec_out = ExecOutput()

        async def run(self, ctx: ExecContext) -> None:
            ctx.set_response_status(201)
            ctx.set_response_header("x-foo", "bar")
            await ctx.fire("exec_out")

    get_catalog().register(SetRespEngine)

    flow = {
        "name": "resp_engine_node",
        "outputs": {},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "s", "type": "SetRespEngine", "exec_in": "entry"},
            {"id": "exit", "type": "FlowOutput", "exec_in": "s"},
        ],
    }
    rayflow.load(flow)
    try:
        evt = _execute_flow_done_event("resp_engine_node", {})
        assert evt["response_status"] == 201
        assert evt["response_headers"] == {"x-foo": "bar"}
    finally:
        rayflow.unload("resp_engine_node")


def test_set_response_status_ray_node():
    """Same as above, but via a @ray_node — exercises the RPC path
    (set_response_meta on the FlowEngine actor) instead of the local
    closure, from a separate worker process."""
    from rayflow.nodes.decorators import ray_node, ExecContext, ExecInput, ExecOutput
    from rayflow.nodes.registry import get_catalog

    @ray_node
    class SetRespRay:
        exec_in = ExecInput()
        exec_out = ExecOutput()

        async def run(self, ctx: ExecContext) -> None:
            ctx.set_response_status(403)
            await ctx.fire("exec_out")

    get_catalog().register(SetRespRay)

    flow = {
        "name": "resp_ray_node",
        "outputs": {},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "s", "type": "SetRespRay", "exec_in": "entry"},
            {"id": "exit", "type": "FlowOutput", "exec_in": "s"},
        ],
    }
    rayflow.load(flow)
    try:
        evt = _execute_flow_done_event("resp_ray_node", {})
        assert evt["response_status"] == 403
    finally:
        rayflow.unload("resp_ray_node")


def test_response_status_defaults_to_200_when_never_set():
    flow = {
        "name": "resp_default",
        "outputs": {},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "exit", "type": "FlowOutput", "exec_in": "entry"},
        ],
    }
    rayflow.load(flow)
    try:
        evt = _execute_flow_done_event("resp_default", {})
        assert evt["response_status"] == 200
        assert evt["response_headers"] == {}
    finally:
        rayflow.unload("resp_default")
