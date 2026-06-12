"""Nodos de casteo explícito entre primitivos.

El sistema de tipos es estricto y sin coerción implícita: para cambiar el tipo
de un valor hay que pasarlo por uno de estos nodos.

Los casteos son nodos de EJECUCIÓN (tienen exec in/out): ocurren en un punto
determinista de la secuencia de control. Si el casteo falla (ej. ToInt de un
texto no numérico), la excepción se propaga por Ray y el engine aborta el flow.
"""
from typing import Any

from rayflow.nodes.decorators import ray_node, Input, Output, ExecInput, ExecOutput, ExecContext


@ray_node
class ToInt:
    """Convierte el valor de entrada a int (casteo explícito)."""
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("int")
    exec_out = ExecOutput()

    def run(self, ctx: ExecContext, value: Any) -> dict:
        ctx.fire("exec_out")
        return {"result": int(value)}


@ray_node
class ToFloat:
    """Convierte el valor de entrada a float (casteo explícito)."""
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("float")
    exec_out = ExecOutput()

    def run(self, ctx: ExecContext, value: Any) -> dict:
        ctx.fire("exec_out")
        return {"result": float(value)}


@ray_node
class ToStr:
    """Convierte el valor de entrada a str (casteo explícito)."""
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("str")
    exec_out = ExecOutput()

    def run(self, ctx: ExecContext, value: Any) -> dict:
        ctx.fire("exec_out")
        return {"result": str(value)}


@ray_node
class ToBool:
    """Convierte el valor de entrada a bool (casteo explícito, semántica de Python)."""
    exec_in = ExecInput()
    value = Input("Any")
    result = Output("bool")
    exec_out = ExecOutput()

    def run(self, ctx: ExecContext, value: Any) -> dict:
        ctx.fire("exec_out")
        return {"result": bool(value)}
