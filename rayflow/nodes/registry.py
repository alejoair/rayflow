"""Global node catalog. Built once per process."""
from __future__ import annotations

import dataclasses
from pathlib import Path

from rayflow.nodes.loader import NodeCatalog
from rayflow.nodes.builtin import control, variables, events, cast, math as math_nodes, flow as flow_nodes, compare as compare_nodes

# Already-decorated builtin classes (avoids re-importing them with importlib).
_BUILTIN_MODULES = (control, variables, events, cast, math_nodes, flow_nodes, compare_nodes)

# Singleton catalog — loaded once.
_catalog: NodeCatalog | None = None


def get_catalog(extra_dirs: list[str | Path] | None = None) -> NodeCatalog:
    """Returns the global catalog, registering builtin + user nodes.

    By convention, discovers custom nodes from the working directory's
    ./custom_nodes/ package (imported as a real module so its classes are
    picklable/reconstructible in Ray workers via runtime_env). `extra_dirs`
    adds extra directories.
    """
    global _catalog
    if _catalog is None:
        _catalog = NodeCatalog()
        for module in _BUILTIN_MODULES:
            _register_module(_catalog, module)

        # Mark builtin nodes as is_builtin=True after registration.
        for name in _catalog.all_names():
            cls, meta = _catalog.get(name)
            # Update the builtin node's metadata.
            _catalog._registry[name] = (cls, dataclasses.replace(meta, is_builtin=True))

        # FlowInput is a historical alias of OnStart — kept for compatibility with tests and saved flows.
        _catalog.register_alias("FlowInput", "OnStart")
        _catalog.load_custom_nodes_package()  # custom nodes are automatically marked is_builtin=False

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
    """For tests only: forces the catalog to be rebuilt."""
    global _catalog
    _catalog = None
