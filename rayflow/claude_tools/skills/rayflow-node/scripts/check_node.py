#!/usr/bin/env python3
"""Locally validates a custom node's source: syntax, AND the decorator/pin
contract (does it actually decorate without raising, what pins does it
declare) — without touching the running server's live catalog. Run this
before create_custom_node/update_custom_node_source (which hot-reload the
real catalog immediately) to catch a bad node in isolation.

This executes the given source as a Python module to inspect it — the
same thing the server's own hot-reload does when it imports a node file
(see rayflow/editor/custom_nodes_routes.py's _reload_catalog). No new
trust boundary is crossed: only run it on source you're about to install
into this same project anyway. Requires `rayflow` importable (pip install
rayflow).

Usage:
    python3 .claude/skills/rayflow-node/scripts/check_node.py custom_nodes/my_node.py
    python3 .../check_node.py -   # reads source from stdin

Prints {"ok": bool, "errors": [...], "nodes": [...]} as JSON. `errors`
surfaces things like "@entry_node must not declare exec_in" or "@entry_node
must declare at least one ExecOutput" — those decorators raise ValueError
immediately when the class contract is wrong, which this script catches as
a top-level error rather than a silent failure to register.
Exit code 0 if ok, 1 otherwise.
"""
import ast
import json
import sys
import types


def _load_module(source: str, module_name: str = "_rayflow_check_node"):
    module = types.ModuleType(module_name)
    exec(compile(source, "<node>", "exec"), module.__dict__)
    return module


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_node.py <node.py | ->", file=sys.stderr)
        return 1

    src_arg = sys.argv[1]
    try:
        source = sys.stdin.read() if src_arg == "-" else open(src_arg, encoding="utf-8").read()
    except OSError as e:
        print(json.dumps({"ok": False, "errors": [f"Could not read '{src_arg}': {e}"], "nodes": []}, indent=2))
        return 1

    try:
        ast.parse(source)
    except SyntaxError as e:
        print(json.dumps({"ok": False, "errors": [f"SyntaxError on line {e.lineno}: {e.msg}"], "nodes": []}, indent=2))
        return 1

    try:
        from rayflow.nodes.decorators import get_node_meta
    except ImportError as e:
        print(json.dumps({"ok": False, "errors": [f"Could not import rayflow ({e})"], "nodes": []}, indent=2))
        return 1

    try:
        module = _load_module(source)
    except Exception as e:
        # Catches decorator-time contract violations too (e.g. @entry_node
        # raising ValueError for a class that declares exec_in), not just
        # plain runtime errors in top-level code.
        print(json.dumps({"ok": False, "errors": [f"Error executing the module: {e}"], "nodes": []}, indent=2))
        return 1

    nodes_found = []
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if isinstance(obj, type) and get_node_meta(obj) is not None:
            meta = get_node_meta(obj)
            decorator = "parallel_node" if meta.is_parallel else (
                "engine_node" if meta.is_engine_node else "ray_node"
            )
            nodes_found.append({
                "class": attr_name,
                "decorator": decorator,
                "is_entry": meta.is_entry,
                "has_exec_in": meta.has_exec_in,
                "has_exec_out": meta.has_exec_out,
                "inputs": [{"name": p.name, "type": p.type, "required": p.required} for p in meta.inputs],
                "outputs": [{"name": p.name, "type": p.type} for p in meta.outputs],
                "exec_outputs": meta.exec_outputs,
            })

    errors = []
    if not nodes_found:
        errors.append(
            "No decorated node class found (@ray_node/@engine_node/@parallel_node/"
            "@entry_node). Did you forget the decorator, or is the class "
            "defined conditionally / inside a function instead of at module "
            "top level?"
        )

    result = {"ok": not errors, "errors": errors, "nodes": nodes_found}
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
