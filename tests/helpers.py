"""Test-only helper replacing the removed rayflow.api.run().

run() used to load, execute, and unconditionally unload a flow on every
call — safe for tests (many test functions across this suite reuse
generic throwaway flow names like "parent" or "counter", each expecting
its own fresh graph) but wrong as a public API: rayflow/server.py used it
to serve HTTP requests, silently destroying and recreating a served
flow's actors on every single request instead of reusing the persistent
graph the engine is actually designed to share across concurrent runs.

Rather than keep that footgun in rayflow.api, the always-reload behavior
now lives here, scoped to test code where reusing a name across unrelated
test cases is an intentional, safe convention.
"""
from typing import Any

import rayflow


def run_once(source, **inputs: Any) -> dict[str, Any]:
    """Loads, executes, and unloads a flow — mirrors the old rayflow.run()."""
    from rayflow.schema.loader import load_flow

    flow_def = load_flow(source)
    name = flow_def.name
    rayflow.load(source)
    try:
        result: dict[str, Any] = {}
        for evt in rayflow.execute(name, inputs):
            if evt.get("event") == "flow_done":
                result = evt.get("result", {})
            elif evt.get("event") == "flow_error":
                raise RuntimeError(evt.get("error", "Unknown error"))
        return result
    finally:
        rayflow.unload(name)
