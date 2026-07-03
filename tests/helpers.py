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


def _make_entry_with_inputs(input_specs: dict[str, str]):
    """Builds a unique @entry_node class exposing the given inputs.

    Used to migrate legacy tests that declared flow.inputs — now those
    inputs must live on the entry node. Each call produces a fresh class
    so the type system stays happy and catalog registration doesn't
    collide across calls.
    """
    from rayflow.nodes.decorators import entry_node, Input, ExecOutput

    namespace: dict[str, Any] = {"__module__": "tests._dynamic_entries"}
    for name, type_str in input_specs.items():
        namespace[name] = Input(type_str)
    namespace["exec_out"] = ExecOutput()
    cls = type("TestEntry", (), namespace)
    return entry_node(cls)


def run_once(source, **inputs: Any) -> dict[str, Any]:
    """Loads, executes, and unloads a flow — mirrors the old rayflow.run().

    Migration shim: if `source` is a dict with a top-level `inputs` field
    (the legacy `flow.inputs`), a dynamic @entry_node class is generated
    with those inputs, registered under a derived name, and the flow's
    entry node's `type` is rewritten to use it. The `inputs` field is
    then stripped so the loader doesn't warn. This lets the many existing
    tests that wire `entry.x` keep working without rewriting each one.
    """
    from rayflow.schema.loader import load_flow
    from rayflow.nodes.registry import get_catalog

    if isinstance(source, dict) and source.get("inputs"):
        input_specs = source["inputs"]
        EntryCls = _make_entry_with_inputs(input_specs)
        entry_type = EntryCls.__name__
        catalog = get_catalog()
        if entry_type not in catalog:
            catalog.register(EntryCls)
        # Rewrite entry nodes' type to the dynamic entry class.
        for nd in source.get("nodes", []):
            if nd.get("type") in ("FlowInput", "OnStart"):
                nd["type"] = entry_type
        source = {k: v for k, v in source.items() if k != "inputs"}

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
