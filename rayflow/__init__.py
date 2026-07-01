from importlib.metadata import PackageNotFoundError, version as _version

from rayflow.api import load, unload, execute, serve_events, stop

try:
    __version__ = _version("rayflow")
except PackageNotFoundError:  # pragma: no cover - editable/unbuilt checkout
    __version__ = "0.0.0+unknown"

__all__ = ["load", "unload", "execute", "serve_events", "stop", "__version__"]
