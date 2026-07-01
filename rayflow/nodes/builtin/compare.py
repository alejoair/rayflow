"""Comparison and boolean logic nodes — pure nodes (no exec pins).

Evaluated on demand as inputs of other nodes (Branch, While, Map…) without
needing an exec wire. Typed Any to support int, float, and str.
"""
from typing import Any

from rayflow.nodes.decorators import ExecContext, Input, Output, engine_node, ray_node


@engine_node
class GreaterThan:
    """Returns True if a > b. Pure node: evaluable as an input of Branch/While."""
    a = Input("Any", default=0)
    b = Input("Any", default=0)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a > b}


@engine_node
class LessThan:
    """Returns True if a < b. Pure node: evaluable as an input of Branch/While."""
    a = Input("Any", default=0)
    b = Input("Any", default=0)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a < b}


@engine_node
class GreaterThanOrEqual:
    """Returns True if a >= b. Pure node: evaluable as an input of Branch/While."""
    a = Input("Any", default=0)
    b = Input("Any", default=0)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a >= b}


@engine_node
class LessThanOrEqual:
    """Returns True if a <= b. Pure node: evaluable as an input of Branch/While."""
    a = Input("Any", default=0)
    b = Input("Any", default=0)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a <= b}


@ray_node
class Equal:
    """Returns True if a == b. Pure node: evaluable as an input of Branch/While."""
    a = Input("Any", default=None)
    b = Input("Any", default=None)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a == b}


@engine_node
class NotEqual:
    """Returns True if a != b. Pure node: evaluable as an input of Branch/While."""
    a = Input("Any", default=None)
    b = Input("Any", default=None)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: Any, b: Any) -> dict:
        return {"result": a != b}


@engine_node
class Not:
    """Logical negation: returns True if value is False and vice versa."""
    value = Input("bool", default=False)
    result = Output("bool")

    async def run(self, ctx: ExecContext, value: bool) -> dict:
        return {"result": not value}


@engine_node
class And:
    """Logical conjunction: returns True only if both a and b are True."""
    a = Input("bool", default=False)
    b = Input("bool", default=False)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: bool, b: bool) -> dict:
        return {"result": a and b}


@engine_node
class Or:
    """Logical disjunction: returns True if a or b (or both) are True."""
    a = Input("bool", default=False)
    b = Input("bool", default=False)
    result = Output("bool")

    async def run(self, ctx: ExecContext, a: bool, b: bool) -> dict:
        return {"result": a or b}
