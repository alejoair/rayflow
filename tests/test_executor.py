"""Tests de ejecución end-to-end con Ray."""
import pytest
import ray
import rayflow
from rayflow.nodes.registry import reset_catalog


@pytest.fixture(autouse=True)
def ray_init():
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, namespace="rayflow")
    reset_catalog()
    yield


def test_flow_suma():
    result = rayflow.run({"name": "suma", "inputs": {"a": "int", "b": "int"},
        "outputs": {"result": "int"}, "nodes": [
            {"id": "entry", "type": "FlowInput"},
            {"id": "add", "type": "Add", "exec_in": "entry",
             "inputs": {"a": "entry.a", "b": "entry.b"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "add",
             "inputs": {"result": "add.result"}},
        ]}, a=3, b=4)
    assert result["result"] == 7


def test_fan_out_ambos_nodos_se_ejecutan():
    """Un exec output conectado a dos nodos — ambos deben ejecutarse."""
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

    # entry dispara a nodo_a y nodo_b en paralelo (fan-out)
    result = rayflow.run({
        "name": "fanout",
        "outputs": {"meta_a": "dict", "meta_b": "dict"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "nodo_a", "type": "SetFlag", "exec_in": "entry",
             "inputs": {"flag_name": "a"}},
            {"id": "nodo_b", "type": "SetFlag", "exec_in": "entry",
             "inputs": {"flag_name": "b"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": ["nodo_a", "nodo_b"],
             "inputs": {"meta_a": "nodo_a.meta", "meta_b": "nodo_b.meta"}},
        ],
    })
    assert result["meta_a"]["id"] == "nodo_a"
    assert result["meta_b"]["id"] == "nodo_b"


def test_parallel_fork_join():
    """Nodo Parallel lanza branch_0 y branch_1 simultáneamente, joined al terminar."""
    result = rayflow.run({
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


def test_parallel_con_foreach_en_rama():
    """Parallel con @engine_node (ForEach) dentro de una rama — aislamiento correcto."""
    result = rayflow.run({
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
    """Parallel con 4 ramas dinámicas (branch_0 a branch_3)."""
    result = rayflow.run({
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


def test_parallel_con_engine_node_puro():
    """Parallel con ramas que solo tienen @engine_node (Branch + Set), sin @ray_node."""
    result = rayflow.run({
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


def test_parallel_anidado():
    """Parallel dentro de una rama de otro Parallel (nested fork/join)."""
    result = rayflow.run({
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
# AND/OR exec_in semántico
# ---------------------------------------------------------------------------

def test_and_join_espera_ambas_ramas():
    """Fan-out de 2 ramas; el nodo de salida con exec_in lista (AND) espera ambas."""
    result = rayflow.run({
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


def test_and_join_espera_rama_lenta():
    """El AND-join espera a la rama con más nodos en cadena."""
    result = rayflow.run({
        "name": "and_join_slow_branch",
        "outputs": {"r0": "int", "r1": "int"},
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
            # rama rápida: un solo nodo
            {"id": "fast", "type": "Add", "exec_in": "entry",
             "inputs": {"a": 1, "b": 0}},
            # rama lenta: dos nodos en cadena
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


def test_and_join_dentro_de_loop_se_resetea():
    """Un join AND recorrido en cada iteración debe esperar a ambas ramas SIEMPRE.

    Regresión: _exec_arrivals no se reseteaba al quedar listo, así que tras la
    primera iteración el join quedaba permanentemente "listo" y se disparaba con
    cada llegada (2x por iteración en vez de 1x). Con 3 iteraciones, el contador
    daba 5 en vez de 3.
    """
    result = rayflow.run({
        "name": "and_join_in_loop",
        "inputs": {"items": "list"},
        "outputs": {"count": "int"},
        "variables": [{"name": "jc", "type": "int", "default": 0}],
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "loop", "type": "ForEach", "exec_in": "entry",
             "inputs": {"array": "entry.items"}},
            # fan-out del cuerpo del loop a dos ramas
            {"id": "na", "type": "Add", "exec_in": "loop.loop_body", "inputs": {"a": 0, "b": 0}},
            {"id": "nb", "type": "Add", "exec_in": "loop.loop_body", "inputs": {"a": 0, "b": 0}},
            # join AND: incrementa jc una vez por iteración (si espera a ambas)
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
    assert result["count"] == 3  # una vez por iteración, no 5


def test_or_join_post_branch():
    """OR explícito: convergencia post-Branch; solo una rama ejecuta."""
    result = rayflow.run({
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
    """OR: rama false del Branch también llega al join."""
    result = rayflow.run({
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
# Map
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Comparaciones puras
# ---------------------------------------------------------------------------

def test_comparacion_pura_lazy():
    """LessThan evaluado lazy como data input de FlowOutput, sin exec wire."""
    result = rayflow.run({
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


def test_comparacion_pura_como_condicion_branch():
    """GreaterThan pure alimenta Branch.condition directamente."""
    result = rayflow.run({
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

def test_while_itera_hasta_condicion():
    """While con condición basada en variable — cuenta hasta 5."""
    result = rayflow.run({
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


def test_while_cero_iteraciones():
    """While con condición False desde el inicio: cero iteraciones."""
    result = rayflow.run({
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

def test_map_con_ray_node_exec():
    """Map aplica un @ray_node exec (ToStr) a cada elemento del array."""
    result = rayflow.run({
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


def test_map_con_engine_node_puro():
    """Map aplica un @engine_node pure (Get) — devuelve siempre el mismo valor."""
    result = rayflow.run({
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
# Aislamiento de outputs entre runs (RunContext)
# ---------------------------------------------------------------------------

def _execute_collect(name: str, inputs: dict) -> dict | None:
    """Ejecuta un flow ya cargado y devuelve el result del flow_done."""
    result = None
    for evt in rayflow.execute(name, inputs):
        if evt.get("event") == "flow_done":
            result = evt.get("result")
        elif evt.get("event") == "flow_error":
            raise AssertionError(f"flow_error: {evt.get('error')}")
    return result


def test_outputs_no_stale_entre_runs():
    """Un nodo no disparado en este run no deja su output visible al siguiente.

    Regresión del bug latente que motivó el RunContext: con node_outputs
    compartido en el GraphState, el output de `producer` (run 1, rama true)
    quedaba almacenado y `reader` lo leía en el run 2 (rama false) aunque
    producer NO se hubiera disparado — recibía 100 stale en vez de su default.

    Con node_outputs por-run, reader cae a su default (0) en el run 2.
    Se carga el flow UNA vez y se ejecuta dos veces: la staleness solo aparece
    si el scratch persiste entre runs del mismo flow cargado.
    """
    flow = {
        "name": "stale_check",
        "inputs": {"cond": "bool"},
        "outputs": {"via_producer": "int", "via_reader": "int"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "br", "type": "Branch", "exec_in": "entry",
             "inputs": {"condition": "entry.cond"}},
            # rama true: produce 100
            {"id": "producer", "type": "Add", "exec_in": "br.true",
             "inputs": {"a": 100, "b": 0}},
            # rama false: lee producer.result (no disparado en este run)
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
        # Run 1: cond=True → producer dispara, deja result=100 en el estado
        r1 = _execute_collect("stale_check", {"cond": True})
        assert r1["via_producer"] == 100  # producer corrió de verdad

        # Run 2: cond=False → reader corre y lee producer.result.
        # Sin aislamiento per-run leería 100 (stale); con RunContext cae al default 0.
        r2 = _execute_collect("stale_check", {"cond": False})
        assert r2["via_reader"] == 0, (
            f"reader leyó {r2['via_reader']} — output stale del run anterior"
        )
    finally:
        rayflow.unload("stale_check")
