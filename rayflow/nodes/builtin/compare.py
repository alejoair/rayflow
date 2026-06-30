"""Nodos de comparación y lógica booleana — pure nodes (sin exec pins).

Se evalúan bajo demanda como inputs de otros nodos (Branch, While, Map…)
sin necesidad de exec wire. Tipos Any para soportar int, float y str.
"""
from typing import Any

from rayflow.nodes.decorators import ExecContext, Input, Output, engine_node, ray_node


@engine_node
class GreaterThan:
    """Devuelve True si a > b. Pure node: evaluable como input de Branch/While."""
    a = Input("Any", default=0)
    b = Input("Any", default=0)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a > b}


@engine_node
class LessThan:
    """Devuelve True si a < b. Pure node: evaluable como input de Branch/While."""
    a = Input("Any", default=0)
    b = Input("Any", default=0)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a < b}


@engine_node
class GreaterThanOrEqual:
    """Devuelve True si a >= b. Pure node: evaluable como input de Branch/While."""
    a = Input("Any", default=0)
    b = Input("Any", default=0)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a >= b}


@engine_node
class LessThanOrEqual:
    """Devuelve True si a <= b. Pure node: evaluable como input de Branch/While."""
    a = Input("Any", default=0)
    b = Input("Any", default=0)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a <= b}


@ray_node
class Equal:
    """Devuelve True si a == b. Pure node: evaluable como input de Branch/While."""
    a = Input("Any", default=None)
    b = Input("Any", default=None)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a == b}


@engine_node
class NotEqual:
    """Devuelve True si a != b. Pure node: evaluable como input de Branch/While."""
    a = Input("Any", default=None)
    b = Input("Any", default=None)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a != b}


@engine_node
class Not:
    """Negación lógica: devuelve True si value es False y viceversa."""
    value = Input("bool", default=False)
    result = Output("bool")

    async def run(self, ctx: ExecContext, value: bool) -> dict:
        return {"result": not value}


@engine_node
class And:
    """Conjunción lógica: devuelve True solo si a y b son ambos True."""
    a = Input("bool", default=False)
    b = Input("bool", default=False)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: bool, b: bool) -> dict:
        return {"result": a and b}


@engine_node
class Or:
    """Disyunción lógica: devuelve True si a o b (o ambos) son True."""
    a = Input("bool", default=False)
    b = Input("bool", default=False)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: bool, b: bool) -> dict:
        return {"result": a or b}
