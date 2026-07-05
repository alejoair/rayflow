"""Process-wide registry of served flows.

This is the **single source of truth** for "which flows are currently served"
(i.e. have live Ray actors and can receive requests). It is consulted by:

- `rayflow.api` (load/unload mutate the registry)
- `rayflow.server` (the `/run`, `/ui`, `/flows` endpoints read it)
- `rayflow.editor.routes` (the editor's `/load`, `/unload`, CRUD endpoints)
- `rayflow.mcp.server` (the MCP tools that drive flows)

The registry is intentionally agnostic of FastAPI and Ray — it is a plain dict
with typed accessors. This neutrality is what breaks the previous circular
coupling between `api.py` and `server.py` (both needed to know about
ServedFlow, which lived in server.py).

A "served flow" means: a flow that has been validated (`build()` passed) and
loaded into Ray (actors live). The origin (CLI `--file`, editor `/load`, etc.)
no longer matters — once registered, the flow exposes the full contract:
runnable via `/run`, mountable `/ui` (if the entry node declared `frontend`),
listed in `/flows`, etc.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rayflow.engine.executor import LoadedFlow
    from rayflow.build.validator import BuiltFlow
    from rayflow.schema.models import FlowDef


class ServedFlow:
    """A loaded, validated flow, ready to run per request.

    Combines the original `source`, the parsed `flow_def`, the validated
    `built` graph, and the live `loaded` actors wrapper. `built` is kept so
    the dynamic `/ui` handler can read the entry node's `meta.frontend` and
    other build-time metadata without re-parsing.
    """

    def __init__(
        self,
        source: "str | Path | dict",
        flow_def: "FlowDef",
        built: "BuiltFlow | None" = None,
        loaded: "LoadedFlow | None" = None,
    ):
        # Keeps the original source (path or dict) to re-run the flow per
        # request via execute_async — NOT its str(), which would lose an
        # inline dict.
        self.source = source
        self.flow_def = flow_def
        # The validated BuiltFlow (kept so the /ui handler and other readers
        # can access entry node meta without re-building). None when
        # ServedFlow is constructed without building (some tests).
        self.built = built
        # The live Ray actors wrapper. None only in edge cases where the
        # ServedFlow exists but actors haven't been spawned (test stubs).
        self.loaded = loaded

    @property
    def source_label(self) -> str:
        """Human-readable origin label (for error messages)."""
        if isinstance(self.source, (str, Path)):
            return str(self.source)
        return f"<dict:{self.name}>"

    @property
    def name(self) -> str:
        return self.flow_def.name

    @property
    def interface(self) -> dict:
        """Public HTTP interface description (used by GET /flows, /flows/{name})."""
        # Inputs are derived from the entry node's declared Input pins
        # (the entry's run() arguments), not from flow.inputs (removed).
        # Falls back to {} if the built graph isn't available.
        entry_inputs: dict[str, dict[str, str | bool]] = {}
        if self.built is not None:
            entry_rnode = self.built.nodes.get(self.built.entry_node_id)
            if entry_rnode is not None:
                for pin in entry_rnode.meta.inputs:
                    entry_inputs[pin.name] = {
                        "type": pin.type or "Any",
                        "required": pin.required,
                    }
        return {
            "name": self.flow_def.name,
            "version": self.flow_def.version,
            "endpoint": f"/flows/{self.flow_def.name}/run",
            "method": "POST",
            "public": self.flow_def.public,
            "inputs": entry_inputs,
            "outputs": {
                name: {"type": type_str}
                for name, type_str in self.flow_def.outputs.items()
            },
        }


# The registry itself. Mutated only through the accessors below.
_served: "dict[str, ServedFlow]" = {}


def register_served(sf: ServedFlow) -> None:
    """Adds or replaces a served flow by its name.

    Replacement is the reload semantic: callers (api.load) ensure any previous
    actors are killed before registering the new ServedFlow.
    """
    _served[sf.name] = sf


def unregister_served(name: str) -> ServedFlow | None:
    """Removes a flow from the registry, returning the removed entry.

    Returns None if `name` was not registered (idempotent removal).
    The caller is responsible for killing the underlying actors (ServedFlow.loaded.unload()).
    """
    return _served.pop(name, None)


def get_served(name: str) -> ServedFlow | None:
    """Returns the ServedFlow for `name`, or None if not registered."""
    return _served.get(name)


def all_served() -> list[ServedFlow]:
    """Returns all currently served flows (insertion order)."""
    return list(_served.values())


def is_served(name: str) -> bool:
    """True if `name` is currently in the registry."""
    return name in _served


def clear_served() -> None:
    """Removes every entry from the registry without unloading actors.

    Test-only helper for resetting module state between test cases; production
    code should use unload() so actors are properly killed.
    """
    _served.clear()
