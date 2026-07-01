#!/usr/bin/env python3
"""PreToolUse hook (Read|Edit|Write): looks up the file about to be
touched in rayflow_file_map.json and surfaces its description plus
depends_on/dependents edges as additionalContext, so the model knows
upfront what the file does and what else might need checking.

Silent no-op if the file isn't in the map, the map is missing, or the
input is malformed — never blocks a tool call.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _file_map import load_map, repo_relative  # noqa: E402


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return

    rel = repo_relative(file_path)
    if rel is None:
        return

    file_map = load_map()
    if file_map is None:
        return

    entry = file_map.get("files", {}).get(rel)
    if entry is None:
        return

    lines = [f"[rayflow_file_map] {rel}", entry.get("description", "")]
    depends_on = entry.get("depends_on") or []
    dependents = entry.get("dependents") or []
    if depends_on:
        lines.append("Depends on: " + ", ".join(depends_on))
    if dependents:
        lines.append("Used by (review these after editing): " + ", ".join(dependents))

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": "\n".join(lines),
        }
    }))


if __name__ == "__main__":
    main()
