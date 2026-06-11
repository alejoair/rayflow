"""Catálogo global de nodos. Se construye una vez por proceso."""
from __future__ import annotations

from pathlib import Path

from rayflow.nodes.loader import NodeCatalog
from rayflow.nodes.builtin import control, variables, events, cast, math as math_nodes, flow as flow_nodes

# Clases built-in ya decoradas (evita re-importarlas con importlib).
_BUILTIN_MODULES = (control, variables, events, cast, math_nodes, flow_nodes)

# Catálogo singleton — cargado una vez.
_catalog: NodeCatalog | None = None


def get_catalog(extra_dirs: list[str | Path] | None = None) -> NodeCatalog:
    """Devuelve el catálogo global, registrando built-in + nodos de usuario.

    Los nodos de usuario se descubren por archivo desde `extra_dirs` (y, por
    convención, desde ./nodes en el working directory).
    """
    global _catalog
    if _catalog is None:
        _catalog = NodeCatalog()
        for module in _BUILTIN_MODULES:
            _register_module(_catalog, module)

    if extra_dirs:
        for d in extra_dirs:
            _catalog.load_directory(d)
    return _catalog


def _register_module(catalog: NodeCatalog, module) -> None:
    from rayflow.nodes.decorators import get_node_meta
    for attr in vars(module).values():
        if isinstance(attr, type) and get_node_meta(attr) is not None:
            catalog.register(attr)


def reset_catalog() -> None:
    """Solo para tests: fuerza la reconstrucción del catálogo."""
    global _catalog
    _catalog = None
