"""Catálogo global de nodos. Se construye una vez por proceso."""
from __future__ import annotations

import dataclasses
from pathlib import Path

from rayflow.nodes.loader import NodeCatalog
from rayflow.nodes.builtin import control, variables, events, cast, math as math_nodes, flow as flow_nodes, compare as compare_nodes

# Clases built-in ya decoradas (evita re-importarlas con importlib).
_BUILTIN_MODULES = (control, variables, events, cast, math_nodes, flow_nodes, compare_nodes)

# Catálogo singleton — cargado una vez.
_catalog: NodeCatalog | None = None


def get_catalog(extra_dirs: list[str | Path] | None = None) -> NodeCatalog:
    """Devuelve el catálogo global, registrando built-in + nodos de usuario.

    Por convención, descubre los nodos custom del paquete ./custom_nodes/ del
    working directory (importado como módulo real para que sus clases sean
    picklables/reconstruibles en los workers Ray vía runtime_env). `extra_dirs`
    añade directorios adicionales.
    """
    global _catalog
    if _catalog is None:
        _catalog = NodeCatalog()
        for module in _BUILTIN_MODULES:
            _register_module(_catalog, module)

        # Marcar nodos builtin como is_builtin=True después del registro
        for name in _catalog.all_names():
            cls, meta = _catalog.get(name)
            # Actualizamos la meta del nodo builtin
            _catalog._registry[name] = (cls, dataclasses.replace(meta, is_builtin=True))

        # FlowInput es alias histórico de OnStart — mantener por compatibilidad con tests y flows guardados
        _catalog.register_alias("FlowInput", "OnStart")
        _catalog.load_custom_nodes_package()  # Los custom se marcan como is_builtin=False automáticamente

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
