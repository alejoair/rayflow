from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Iterator

from rayflow.nodes.decorators import NodeMeta, _NODE_META_ATTR, get_node_meta


class NodeCatalog:
    """Discovers and registers nodes from one or more directories."""

    def __init__(self):
        # node_name → (class, NodeMeta)
        self._registry: dict[str, tuple[type, NodeMeta]] = {}
        # path.stem → error message, for custom node files that failed to
        # import or register (see load_custom_nodes_package).
        self.load_errors: dict[str, str] = {}

    def load_custom_nodes_package(self) -> None:
        """Imports the cwd's ./custom_nodes/ as a REAL package.

        Unlike load_directory (which uses synthetic module names that can't
        be imported from another process), here the nodes live under
        `custom_nodes.<module>` — an importable module. This is what lets
        their classes be reconstructed in Ray workers (which receive
        custom_nodes/ via runtime_env py_modules) when deserializing the
        BuiltFlow.
        """
        from rayflow.workspace import custom_nodes_path

        cn = custom_nodes_path()
        if not cn.exists():
            return
        # cwd must be on sys.path for `import custom_nodes.*` to work.
        cwd = str(cn.parent)
        if cwd not in sys.path:
            sys.path.insert(0, cwd)

        for path in sorted(cn.glob("*.py")):
            if path.name == "__init__.py" or path.name.startswith("_"):
                continue
            module_name = f"custom_nodes.{path.stem}"
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:
                self.load_errors[path.stem] = str(exc)
                continue
            # Force serialization by value: custom_nodes/ is only on the
            # driver's sys.path, not on Ray workers or the FlowEngine actor.
            try:
                import ray.cloudpickle as _cp
                _cp.register_pickle_by_value(module)
            except Exception:
                pass
            try:
                self._register_from_module(module)
            except Exception as exc:
                self.load_errors[path.stem] = str(exc)

    def load_directory(self, directory: str | Path) -> None:
        """Imports every .py in the directory and registers the nodes found.

        Uses synthetic module names — fine for nodes local to the driver,
        NOT for distribution to workers (use custom_nodes/ for that).
        """
        directory = Path(directory)
        if not directory.exists():
            return
        for path in sorted(directory.rglob("*.py")):
            if path.name.startswith("_"):
                continue
            self._load_file(path)

    def _load_file(self, path: Path) -> None:
        module_name = f"_rayflow_node_{path.stem}_{abs(hash(str(path)))}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            return
        self._register_from_module(module)
        # Remove from sys.modules after registering: cloudpickle serializes
        # classes by reference to their module only if it's present in
        # sys.modules. Without it, serialization falls back to by-value
        # (inline), which lets them be deserialized in Ray workers without
        # needing to import an unavailable synthetic module.
        sys.modules.pop(module_name, None)

    def _register_from_module(self, module) -> None:
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if isinstance(obj, type) and get_node_meta(obj) is not None:
                self.register(obj)

    def register(self, cls: type) -> None:
        meta = get_node_meta(cls)
        if meta is None:
            raise ValueError(f"{cls} has no node metadata (@node was not applied)")
        existing = self._registry.get(meta.name)
        if existing is not None and existing[0] is not cls:
            raise ValueError(
                f"Duplicate node '{meta.name}': already registered as {existing[0]!r}, "
                f"attempted to register {cls!r}. Rename one of the two."
            )
        self._registry[meta.name] = (cls, meta)

    def register_alias(self, alias: str, target: str) -> None:
        """Registers `alias` pointing to the same class and metadata as `target`."""
        entry = self._registry.get(target)
        if entry is None:
            raise ValueError(f"Can't create alias '{alias}': node '{target}' is not registered")
        self._registry[alias] = entry

    def get(self, name: str) -> tuple[type, NodeMeta] | None:
        return self._registry.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._registry

    def all_names(self) -> list[str]:
        return list(self._registry.keys())

    def __iter__(self) -> Iterator[tuple[str, type, NodeMeta]]:
        for name, (cls, meta) in self._registry.items():
            yield name, cls, meta
