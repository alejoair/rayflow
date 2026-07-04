#!/usr/bin/env python3
"""Offline flow validator — the SAME logic the MCP `validate_flow` tool
uses (rayflow.schema.loader + rayflow.build.validator.validate_all), run
locally with no `rayflow serve` round-trip. Use this while iterating on a
flow's JSON; still call the live `mcp__rayflow__validate_flow` once before
saving, since the running server's catalog (custom nodes especially) can
drift from what this script sees if a node file changed without a reload.

Must be run from the project root (the same directory you'd run
`rayflow serve` from) so custom_nodes/ is discovered the same way the live
server discovers it. Requires `rayflow` importable (pip install rayflow —
already true if this project runs `rayflow serve`).

Usage:
    python3 .claude/skills/rayflow-flow/scripts/validate_flow.py my_flow.json
    cat my_flow.json | python3 .../validate_flow.py -

Prints {"valid": bool, "errors": [...], "warnings": [...]} as JSON.
`warnings` flags unknown/typo'd schema keys (e.g. "input" instead of
"inputs") that the parser silently drops — check it even when valid=true,
since a dropped key doesn't fail validation, it just quietly does nothing.
Exit code 0 if valid, 1 otherwise (including on a usage/parse error).
"""
import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_flow.py <flow.json | ->", file=sys.stderr)
        return 1

    src = sys.argv[1]
    try:
        raw = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    except OSError as e:
        print(json.dumps({"valid": False, "errors": [f"Could not read '{src}': {e}"], "warnings": []}, indent=2))
        return 1

    try:
        flow_data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"valid": False, "errors": [f"Invalid JSON: {e}"], "warnings": []}, indent=2))
        return 1

    if not isinstance(flow_data, dict):
        print(json.dumps({"valid": False, "errors": ["The flow must be a JSON object"], "warnings": []}, indent=2))
        return 1

    try:
        from rayflow.schema.loader import load_flow, unknown_keys
        from rayflow.build.validator import validate_all
        from rayflow.nodes.registry import get_catalog
    except ImportError as e:
        print(json.dumps({
            "valid": False,
            "errors": [
                f"Could not import rayflow ({e}) — run this from the project root "
                f"where rayflow is installed, the same directory you'd run "
                f"'rayflow serve' from (so custom_nodes/ resolves the same way)."
            ],
            "warnings": [],
        }, indent=2))
        return 1

    warnings = unknown_keys(flow_data)
    try:
        flow_def = load_flow(flow_data)
        errors = validate_all(flow_def, get_catalog())
    except Exception as e:
        print(json.dumps({"valid": False, "errors": [f"Parse error: {e}"], "warnings": warnings}, indent=2))
        return 1

    result = {"valid": not errors, "errors": errors, "warnings": warnings}
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
