from __future__ import annotations

import importlib
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

    def load_custom_nodes_package(self) -> None:
        """Importa el paquete ./custom_nodes/ del cwd como módulo REAL.

        A diferencia de load_directory (que usa nombres de módulo sintéticos no
        importables desde otro proceso), aquí los nodos quedan bajo
        `custom_nodes.<modulo>` — un módulo importable. Esto es lo que permite
        que sus clases se reconstruyan en los workers Ray (que reciben
        custom_nodes/ vía runtime_env py_modules) al deserializar el BuiltFlow.
        """
        from rayflow.workspace import custom_nodes_path

        cn = custom_nodes_path()
        if not cn.exists():
            return
        # El cwd debe estar en sys.path para que `import custom_nodes.*` funcione.
        cwd = str(cn.parent)
        if cwd not in sys.path:
            sys.path.insert(0, cwd)

        for path in sorted(cn.glob("*.py")):
            if path.name == "__init__.py" or path.name.startswith("_"):
                continue
            module_name = f"custom_nodes.{path.stem}"
            try:
                module = importlib.import_module(module_name)
            except Exception:
                continue
            # Forzar serialización por valor: custom_nodes/ solo está en sys.path
            # del driver, no en los workers Ray ni en el actor FlowEngine.
            try:
                import ray.cloudpickle as _cp
                _cp.register_pickle_by_value(module)
            except Exception:
                pass
            self._register_from_module(module)

    def load_directory(self, directory: str | Path) -> None:
        """Importa todos los .py del directorio y registra los nodos encontrados.

        Usa nombres de módulo sintéticos — apto para nodos locales del driver,
        NO para distribución a workers (usar custom_nodes/ para eso).
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
        # Quitar de sys.modules después de registrar: cloudpickle serializa las
        # clases por referencia al módulo solo si está en sys.modules. Sin él,
        # fuerza serialización por valor (inline), lo que permite deserializarlas
        # en workers Ray sin necesidad de importar un módulo sintético no disponible.
        sys.modules.pop(module_name, None)

    def _register_from_module(self, module) -> None:
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if isinstance(obj, type) and get_node_meta(obj) is not None:
                self.register(obj)

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
