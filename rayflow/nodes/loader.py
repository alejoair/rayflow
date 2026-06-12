from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Iterator

from rayflow.nodes.decorators import NodeMeta, _NODE_META_ATTR, get_node_meta


class NodeCatalog:
    """Descubre y registra nodos desde uno o varios directorios."""

    def __init__(self):
        # nombre_nodo → (clase, NodeMeta)
        self._registry: dict[str, tuple[type, NodeMeta]] = {}

    def load_directory(self, directory: str | Path) -> None:
        """Importa todos los .py del directorio y registra los nodos encontrados."""
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
            return

        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if isinstance(obj, type):
                meta = get_node_meta(obj)
                if meta is not None:
                    self._registry[meta.name] = (obj, meta)

    def register(self, cls: type) -> None:
        meta = get_node_meta(cls)
        if meta is None:
            raise ValueError(f"{cls} no tiene metadata de nodo (@node no aplicado)")
        existing = self._registry.get(meta.name)
        if existing is not None and existing[0] is not cls:
            raise ValueError(
                f"Nodo '{meta.name}' duplicado: ya registrado como {existing[0]!r}, "
                f"se intentó registrar {cls!r}. Renombra uno de los dos."
            )
        self._registry[meta.name] = (cls, meta)

    def get(self, name: str) -> tuple[type, NodeMeta] | None:
        return self._registry.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._registry

    def all_names(self) -> list[str]:
        return list(self._registry.keys())

    def __iter__(self) -> Iterator[tuple[str, type, NodeMeta]]:
        for name, (cls, meta) in self._registry.items():
            yield name, cls, meta
