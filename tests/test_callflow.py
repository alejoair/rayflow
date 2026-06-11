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
        {"id": "entry", "type": "FlowInput"},
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
            {"id": "entry", "type": "FlowInput"},
            {"id": "sub", "type": "CallFlow",
             "exec_in": "entry",
             "inputs": {"flow": SUBFLOW_SUMA, "isolated": True,
                        "a": "entry.x", "b": "entry.y"}},
            {"id": "exit", "type": "FlowOutput", "exec_in": "sub",
             "inputs": {"respuesta": "sub.result"}},
        ],
    }, x=3, y=7)

    assert result["respuesta"]["total"] == 10


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


def test_callflow_anidado():
    """Dos CallFlow en secuencia — cada uno recibe outputs del anterior via result dict."""
    subflow_doble = {
        "name": "doble",
        "inputs": {"n": "int"},
        "outputs": {"valor": "int"},
        "nodes": [
            {"id": "entry", "type": "FlowInput"},
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
            {"id": "entry", "type": "FlowInput"},
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
