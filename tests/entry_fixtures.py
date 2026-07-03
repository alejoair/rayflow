"""Test-only entry-node fixtures.

These are fixed-shape @entry_node classes (a couple of typed Inputs, no
run() — auto-passthrough mirrors each Input as a same-named Output) that
several inline test flows wire directly (`entry.x`, `entry.a`, `entry.b`,
...). They used to live permanently in rayflow/nodes/builtin/control.py,
which meant every `pip install rayflow` user saw them in their real node
catalog even though nothing in the product itself used them — only this
test suite's inline JSON fixtures did.

They live here instead, registered into the same process-wide
NodeCatalog but only when the test suite imports this module — never
part of rayflow.nodes.builtin.

Call register() from a test file's `ray_init` fixture, right after
reset_catalog(): a catalog reset wipes the whole registry (it isn't part
of the builtin modules that get_catalog() reloads automatically), so
these need to be re-registered for every test. Same underlying pattern
tests/helpers.py::run_once already uses for one-off dynamic entries —
just fixed, named, reusable shapes instead of one generated per call.
"""
from rayflow.nodes.decorators import ExecOutput, Input, entry_node
from rayflow.nodes.registry import get_catalog


@entry_node
class EntryXY:
    """Fixed entry declaring two int inputs (x, y)."""
    x = Input("int")
    y = Input("int")
    exec_out = ExecOutput()


@entry_node
class EntryX:
    """Fixed entry declaring a single int input (x)."""
    x = Input("int")
    exec_out = ExecOutput()


@entry_node
class EntryAB:
    """Fixed entry declaring two int inputs (a, b)."""
    a = Input("int")
    b = Input("int")
    exec_out = ExecOutput()


@entry_node
class EntryN:
    """Fixed entry declaring a single int input (n)."""
    n = Input("int")
    exec_out = ExecOutput()


@entry_node
class EntryABC:
    """Fixed entry declaring three int inputs (a, b, c)."""
    a = Input("int")
    b = Input("int")
    c = Input("int")
    exec_out = ExecOutput()


@entry_node
class EntryItems:
    """Fixed entry declaring a single list input (items)."""
    items = Input("list")
    exec_out = ExecOutput()


@entry_node
class EntryNumbersThreshold:
    """Fixed entry declaring list (numbers) + int (threshold)."""
    numbers = Input("list")
    threshold = Input("int")
    exec_out = ExecOutput()


@entry_node
class EntryXBool:
    """Fixed entry declaring int (x) + bool (use_positive)."""
    x = Input("int")
    use_positive = Input("bool")
    exec_out = ExecOutput()


_ALL = (
    EntryXY, EntryX, EntryAB, EntryN, EntryABC, EntryItems,
    EntryNumbersThreshold, EntryXBool,
)


def register() -> None:
    """Registers all test-only entry fixtures into the current catalog."""
    catalog = get_catalog()
    for cls in _ALL:
        catalog.register(cls)
