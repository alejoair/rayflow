"""Sistema de tipos de los data pins.

Decisiones de diseño (acordadas para v1):
- Registro cerrado de primitivos: int, float, str, bool, list, dict, Any.
- Genéricos opcionales: list[T] y dict[str, T]. list sin parámetro == list[Any].
- Compatibilidad ESTRICTA: dos pins conectados deben tener el mismo tipo, o uno
  ser Any. No hay coerción implícita. En particular int y float son incompatibles
  (los casteos se hacen con nodos explícitos: ToInt, ToFloat, ...).
- Sin tipos de usuario en v1.

Un tipo se representa siempre como string canónico ("int", "list[str]",
"dict[str, Any]"). Las clases Python (int, str, ...) usadas en anotaciones se
normalizan a ese string.
"""
from __future__ import annotations

from dataclasses import dataclass

# Conjunto cerrado de tipos primitivos permitidos.
PRIMITIVES: frozenset[str] = frozenset(
    {"int", "float", "str", "bool", "list", "dict", "Any"}
)

# Tipos que admiten parámetro genérico.
GENERIC_CONTAINERS: frozenset[str] = frozenset({"list", "dict"})


class TypeError_(Exception):
    """Error de tipo del sistema de pines (nombre con _ para no chocar con builtin)."""


@dataclass(frozen=True)
class PinType:
    """Tipo de un data pin ya parseado y validado.

    base: nombre del contenedor o primitivo ("int", "list", "dict", "Any").
    param: tipo del elemento para list[T] / dict[str, T]; None si no aplica.
           Para dict solo se modela el tipo del valor (la clave es siempre str).
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
# Parseo / normalización
# ---------------------------------------------------------------------------

def parse_type(spec) -> PinType:
    """Convierte un tipo canónico (string) en un PinType validado.

    La ÚNICA forma de expresar un tipo es un string: "int", "list[str]",
    "dict[str, Any]", "Any". Lanza TypeError_ si es desconocido o mal formado.
    """
    if spec is None:
        return ANY
    if isinstance(spec, PinType):
        return spec
    if isinstance(spec, str):
        return _parse_str(spec.strip())
    raise TypeError_(
        f"El tipo de un pin debe ser un string canónico (p.ej. 'int', 'list[str]'); "
        f"recibido {spec!r}"
    )


def _parse_str(s: str) -> PinType:
    if "[" not in s:
        if s not in PRIMITIVES:
            raise TypeError_(f"Tipo desconocido: '{s}'. Permitidos: {sorted(PRIMITIVES)}")
        return PinType(s)

    # Contenedor genérico: base[...]
    if not s.endswith("]"):
        raise TypeError_(f"Tipo mal formado: '{s}'")
    base, inner = s[: s.index("[")], s[s.index("[") + 1 : -1]
    base = base.strip()
    inner = inner.strip()

    if base not in GENERIC_CONTAINERS:
        raise TypeError_(f"'{base}' no admite parámetro genérico")

    if base == "dict":
        # dict[str, V]: la clave debe ser str.
        key, _, val = inner.partition(",")
        if val == "":
            raise TypeError_("dict requiere dos parámetros: dict[str, V]")
        if key.strip() != "str":
            raise TypeError_("La clave de dict debe ser str: dict[str, V]")
        return PinType("dict", _parse_str(val.strip()))

    # list[T]
    return PinType("list", _parse_str(inner))


# ---------------------------------------------------------------------------
# Compatibilidad estricta
# ---------------------------------------------------------------------------

def compatible(consumer, producer) -> bool:
    """True si un valor de tipo `producer` puede conectarse a un pin `consumer`.

    Estricto: mismo tipo o uno de los dos es Any. Recursivo en el parámetro
    genérico (list[str] conecta con list[str] y con list[Any], no con list[int]).
    Sin coerción: int y float son incompatibles.
    """
    c = parse_type(consumer)
    p = parse_type(producer)
    return _compatible(c, p)


def _compatible(c: PinType, p: PinType) -> bool:
    if c.base == "Any" or p.base == "Any":
        return True
    if c.base != p.base:
        return False
    # Mismo base. Comparar parámetro si ambos lo tienen.
    if c.param is None or p.param is None:
        # list vs list[str]: uno sin parámetro == list[Any] -> compatible.
        return True
    return _compatible(c.param, p.param)
