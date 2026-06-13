"""Nodos de comparación y lógica booleana — pure nodes (sin exec pins).

Se evalúan bajo demanda como inputs de otros nodos (Branch, While, Map…)
sin necesidad de exec wire. Tipos Any para soportar int, float y str.
"""
from typing import Any

from rayflow.nodes.decorators import ExecContext, Input, Output, engine_node


@engine_node
class GreaterThan:
    a = Input("Any", default=0)
    b = Input("Any", default=0)
    result = Output("bool")

    def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a > b}


@engine_node
class LessThan:
    a = Input("Any", default=0)
    b = Input("Any", default=0)
    result = Output("bool")

    def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a < b}


@engine_node
class GreaterThanOrEqual:
    a = Input("Any", default=0)
    b = Input("Any", default=0)
    result = Output("bool")

    def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a >= b}


@engine_node
class LessThanOrEqual:
    a = Input("Any", default=0)
    b = Input("Any", default=0)
    result = Output("bool")

    def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a <= b}


@engine_node
class Equal:
    a = Input("Any", default=None)
    b = Input("Any", default=None)
    result = Output("bool")

    def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a == b}


@engine_node
class NotEqual:
    a = Input("Any", default=None)
    b = Input("Any", default=None)
    result = Output("bool")

    def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a != b}


@engine_node
class Not:
    value = Input("bool", default=False)
    result = Output("bool")

    def run(self, ctx: ExecContext, value: bool) -> dict:
        return {"result": not value}


@engine_node
class And:
    a = Input("bool", default=False)
    b = Input("bool", default=False)
    result = Output("bool")

    def run(self, ctx: ExecContext, a: bool, b: bool) -> dict:
        return {"result": a and b}


@engine_node
class Or:
    a = Input("bool", default=False)
    b = Input("bool", default=False)
    result = Output("bool")

    def run(self, ctx: ExecContext, a: bool, b: bool) -> dict:
        return {"result": a or b}
