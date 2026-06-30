"""Type system for data pins.

Design decisions (settled for v1):
- Closed registry of primitives: int, float, str, bool, list, dict, Any.
- Optional generics: list[T] and dict[str, T]. list with no parameter ==
  list[Any].
- STRICT compatibility: two connected pins must have the same type, or one
  must be Any. No implicit coercion. In particular, int and float are
  incompatible (casting is done with explicit nodes: ToInt, ToFloat, ...).
- No user-defined types in v1.

A type is always represented as a canonical string ("int", "list[str]",
"dict[str, Any]"). Python classes (int, str, ...) used in annotations are
normalized to that string.
"""
from __future__ import annotations

from dataclasses import dataclass

# Closed set of allowed primitive types.
PRIMITIVES: frozenset[str] = frozenset(
    {"int", "float", "str", "bool", "list", "dict", "Any"}
)

# Types that accept a generic parameter.
GENERIC_CONTAINERS: frozenset[str] = frozenset({"list", "dict"})


class TypeError_(Exception):
    """Pin-type-system error (named with a trailing _ to avoid clashing with the builtin)."""


@dataclass(frozen=True)
class PinType:
    """An already-parsed and validated data pin type.

    base: container or primitive name ("int", "list", "dict", "Any").
    param: element type for list[T] / dict[str, T]; None if not applicable.
           For dict, only the value type is modeled (the key is always str).
    """
    base: str
    param: "PinType | None" = None

    def __str__(self) -> str:
        if self.param is None:
            return self.base
        if self.base == "dict":
            return f"dict[str, {self.param}]"
        return f"{self.base}[{self.param}]"


ANY = PinType("Any")


# ---------------------------------------------------------------------------
# Parsing / normalization
# ---------------------------------------------------------------------------

def parse_type(spec) -> PinType:
    """Converts a canonical type (string) into a validated PinType.

    The ONLY way to express a type is a string: "int", "list[str]",
    "dict[str, Any]", "Any". Raises TypeError_ if unknown or malformed.
    """
    if spec is None:
        return ANY
    if isinstance(spec, PinType):
        return spec
    if isinstance(spec, str):
        return _parse_str(spec.strip())
    raise TypeError_(
        f"A pin's type must be a canonical string (e.g. 'int', 'list[str]'); "
        f"got {spec!r}"
    )


def _parse_str(s: str) -> PinType:
    if "[" not in s:
        if s not in PRIMITIVES:
            raise TypeError_(f"Unknown type: '{s}'. Allowed: {sorted(PRIMITIVES)}")
        return PinType(s)

    # Generic container: base[...]
    if not s.endswith("]"):
        raise TypeError_(f"Malformed type: '{s}'")
    base, inner = s[: s.index("[")], s[s.index("[") + 1 : -1]
    base = base.strip()
    inner = inner.strip()

    if base not in GENERIC_CONTAINERS:
        raise TypeError_(f"'{base}' doesn't accept a generic parameter")

    if base == "dict":
        # dict[str, V]: the key must be str.
        key, _, val = inner.partition(",")
        if val == "":
            raise TypeError_("dict requires two parameters: dict[str, V]")
        if key.strip() != "str":
            raise TypeError_("dict's key must be str: dict[str, V]")
        return PinType("dict", _parse_str(val.strip()))

    # list[T]
    return PinType("list", _parse_str(inner))


# ---------------------------------------------------------------------------
# Strict compatibility
# ---------------------------------------------------------------------------

def compatible(consumer, producer) -> bool:
    """True if a value of type `producer` can connect to a `consumer` pin.

    Strict: same type, or one of the two is Any. Recursive on the generic
    parameter (list[str] connects with list[str] and with list[Any], not
    with list[int]). No coercion: int and float are incompatible.
    """
    c = parse_type(consumer)
    p = parse_type(producer)
    return _compatible(c, p)


def _compatible(c: PinType, p: PinType) -> bool:
    if c.base == "Any" or p.base == "Any":
        return True
    if c.base != p.base:
        return False
    # Same base. Compare the parameter if both have one.
    if c.param is None or p.param is None:
        # list vs list[str]: one with no parameter == list[Any] -> compatible.
        return True
    return _compatible(c.param, p.param)
