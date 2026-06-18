"""Tests de CallFlow — subgrafos compartidos y aislados."""
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


# Flow auxiliar usado como subgrafo en varios tests
SUBFLOW_SUMA = {
    "name": "subflow_suma",
    "inputs": {"a": "int", "b": "int"},
    "outputs": {"total": "int"},
    "nodes": [
        {"id": "entry", "type": "OnStart"},
        {"id": "add", "type": "Add", "exec_in": "entry",
         "inputs": {"a": "entry.a", "b": "entry.b"}},
        {"id": "exit", "type": "FlowOutput", "exec_in": "add",
         "inputs": {"total": "add.result"}},
    ],
}

# Flow auxiliar que escribe una variable (para modo compartido)
SUBFLOW_SET_VAR = {
    "name": "subflow_set_var",
    "nodes": [
        {"id": "entry", "type": "OnStart"},
        {"id": "set", "type": "Set", "exec_in": "entry",
         "inputs": {"variable_name": "contador", "value": 42}},
        {"id": "exit", "type": "FlowOutput", "exec_in": "set",
         "inputs": {}},
    ],
}


def test_callflow_aislado_inputs_outputs():
    """CallFlow aislado recibe inputs y devuelve outputs en 'result'."""
    result = rayflow.run({
        "name": "padre",
        "inputs": {"x": "int", "y": "int"},
        "outputs": {"respuesta": "dict"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "sub", "type": "CallFlow",
             "exec_in": "entry",
             "inputs": {"flow": SUBFLOW_SUMA, "isolated": True,
                        "a": "entry.x", "b": "entry.y"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "sub",
             "inputs": {"respuesta": "sub.result"}},
        ],
    }, x=3, y=7)

    assert result["respuesta"]["total"] == 10


def test_callflow_meta_flow_es_el_subflow_declarante():
    """meta['flow'] refleja el flow que DECLARÓ el nodo, no el flow raíz.

    Un nodo del subflow reporta el nombre del subflow; uno del raíz, el del raíz.
    meta['id'] es la ruta plana ("sub/add").
    """
    result = rayflow.run({
        "name": "mipadre",
        "inputs": {"x": "int"},
        "outputs": {"sub_meta": "dict", "root_meta": "dict"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "sub", "type": "CallFlow", "exec_in": "entry",
             "inputs": {"flow": SUBFLOW_SUMA, "isolated": True,
                        "a": "entry.x", "b": "entry.x"}},
            {"id": "dbl", "type": "Add", "exec_in": "sub",
             "inputs": {"a": "entry.x", "b": "entry.x"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "dbl",
             "inputs": {"sub_meta": "sub/add.meta", "root_meta": "dbl.meta"}},
        ],
    }, x=5)
    # El nodo 'add' vive dentro del subflow → flow del subflow, id con ruta.
    assert result["sub_meta"]["flow"] == "subflow_suma"
    assert result["sub_meta"]["id"] == "sub/add"
    # El nodo 'dbl' es del flow raíz.
    assert result["root_meta"]["flow"] == "mipadre"
    assert result["root_meta"]["id"] == "dbl"


def test_callflow_aislado_no_contamina_estado_padre():
    """CallFlow aislado no puede ver ni modificar variables del padre."""
    result = rayflow.run({
        "name": "padre",
        "variables": [{"name": "val", "type": "int", "default": 99}],
        "outputs": {"val_padre": "Any"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            # subflow intenta set_variable("val", 0) pero en su propio GraphState
            {"id": "sub", "type": "CallFlow",
             "exec_in": "entry",
             "inputs": {"flow": SUBFLOW_SET_VAR, "isolated": True}},
            {"id": "get_val", "type": "Get",
             "inputs": {"variable_name": "val"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "sub",
             "inputs": {"val_padre": "get_val.value"}},
        ],
    })
    # La variable del padre sigue siendo 99 — el subflow aislado no la tocó
    assert result["val_padre"] == 99


def test_callflow_compartido_modifica_variable_padre():
    """CallFlow compartido puede escribir variables del padre."""
    result = rayflow.run({
        "name": "padre",
        "variables": [{"name": "contador", "type": "int", "default": 0}],
        "outputs": {"final": "Any"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "sub", "type": "CallFlow",
             "exec_in": "entry",
             "inputs": {"flow": SUBFLOW_SET_VAR, "isolated": False}},
            {"id": "get_contador", "type": "Get",
             "inputs": {"variable_name": "contador"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "sub",
             "inputs": {"final": "get_contador.value"}},
        ],
    })
    # El subflow compartido escribió 42 en la variable del padre
    assert result["final"] == 42


def test_callflow_dentro_de_rama_parallel():
    """Un CallFlow dentro de una rama de Parallel se orquesta correctamente.

    Regresión: con el ejecutor de ramas fusionado en FlowEngine, una rama de
    Parallel reusa toda la lógica de _fire_* (incluido CallFlow). Antes, el
    ejecutor de ramas separado no sabía orquestar CallFlow.
    """
    sub = {
        "name": "s",
        "inputs": {"a": "int", "b": "int"},
        "outputs": {"t": "int"},
        "nodes": [
            {"id": "e", "type": "OnStart"},
            {"id": "add", "type": "Add", "exec_in": "e",
             "inputs": {"a": "e.a", "b": "e.b"}},
            {"id": "x", "type": "FlowOutput", "exec_in": "add",
             "inputs": {"t": "add.result"}},
        ],
    }
    result = rayflow.run({
        "name": "p",
        "inputs": {"n": "int"},
        "outputs": {"r": "dict"},
        "nodes": [
            {"id": "e", "type": "OnStart"},
            {"id": "par", "type": "Parallel", "exec_in": "e"},
            {"id": "cf", "type": "CallFlow", "exec_in": "par.branch_0",
             "inputs": {"flow": sub, "isolated": True, "a": "e.n", "b": "e.n"}},
            {"id": "noop", "type": "Set", "exec_in": "par.branch_1",
             "inputs": {"variable_name": "dummy", "value": 1}},
            {"id": "x", "type": "FlowOutput", "exec_in": "par.joined",
             "inputs": {"r": "cf.result"}},
        ],
    }, n=4)
    assert result["r"]["t"] == 8


def test_callflow_aislado_misma_variable_no_colisiona():
    """Aislamiento real: padre y subflow con la MISMA variable no se pisan.

    El subflow aislado escribe su 'contador' en su propio namespace de estado
    (state_path), así que el 'contador' del padre permanece intacto.
    """
    sub = {
        "name": "sub",
        "variables": [{"name": "contador", "type": "int", "default": 0}],
        "nodes": [
            {"id": "e", "type": "OnStart"},
            {"id": "s", "type": "Set", "exec_in": "e",
             "inputs": {"variable_name": "contador", "value": 7}},
            {"id": "x", "type": "FlowOutput", "exec_in": "s", "inputs": {}},
        ],
    }
    result = rayflow.run({
        "name": "padre",
        "variables": [{"name": "contador", "type": "int", "default": 99}],
        "outputs": {"val": "Any"},
        "nodes": [
            {"id": "e", "type": "OnStart"},
            {"id": "sub", "type": "CallFlow", "exec_in": "e",
             "inputs": {"flow": sub, "isolated": True}},
            {"id": "g", "type": "Get", "inputs": {"variable_name": "contador"}},
            {"id": "x", "type": "FlowOutput", "exec_in": "sub",
             "inputs": {"val": "g.value"}},
        ],
    })
    # El subflow aislado NO tocó el contador del padre.
    assert result["val"] == 99


def test_callflow_compartido_misma_variable_si_colisiona():
    """Modo compartido: el subflow SÍ pisa la variable del padre (mismo namespace)."""
    sub = {
        "name": "sub",
        "variables": [{"name": "contador", "type": "int", "default": 0}],
        "nodes": [
            {"id": "e", "type": "OnStart"},
            {"id": "s", "type": "Set", "exec_in": "e",
             "inputs": {"variable_name": "contador", "value": 7}},
            {"id": "x", "type": "FlowOutput", "exec_in": "s", "inputs": {}},
        ],
    }
    result = rayflow.run({
        "name": "padre",
        "variables": [{"name": "contador", "type": "int", "default": 99}],
        "outputs": {"val": "Any"},
        "nodes": [
            {"id": "e", "type": "OnStart"},
            {"id": "sub", "type": "CallFlow", "exec_in": "e",
             "inputs": {"flow": sub, "isolated": False}},
            {"id": "g", "type": "Get", "inputs": {"variable_name": "contador"}},
            {"id": "x", "type": "FlowOutput", "exec_in": "sub",
             "inputs": {"val": "g.value"}},
        ],
    })
    assert result["val"] == 7


def test_callflow_anidado():
    """Dos CallFlow en secuencia — cada uno recibe outputs del anterior via result dict."""
    subflow_doble = {
        "name": "doble",
        "inputs": {"n": "int"},
        "outputs": {"valor": "int"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "add", "type": "Add", "exec_in": "entry",
             "inputs": {"a": "entry.n", "b": "entry.n"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "add",
             "inputs": {"valor": "add.result"}},
        ],
    }

    result = rayflow.run({
        "name": "padre",
        "inputs": {"x": "int"},
        "outputs": {"r1": "dict", "r2": "dict"},
        "nodes": [
            {"id": "entry", "type": "OnStart"},
            {"id": "sub1", "type": "CallFlow",
             "exec_in": "entry",
             "inputs": {"flow": subflow_doble, "isolated": True, "n": "entry.x"}},
            {"id": "sub2", "type": "CallFlow",
             "exec_in": "sub1",
             "inputs": {"flow": subflow_doble, "isolated": True, "n": "entry.x"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "sub2",
             "inputs": {"r1": "sub1.result", "r2": "sub2.result"}},
        ],
    }, x=5)

    assert result["r1"]["valor"] == 10
    assert result["r2"]["valor"] == 10
