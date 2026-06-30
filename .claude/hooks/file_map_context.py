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

HOOK_DIR = Path(__file__).resolve().parent
REPO_ROOT = HOOK_DIR.parent.parent  # .claude/hooks/ -> .claude/ -> repo root
MAP_PATH = REPO_ROOT / "rayflow_file_map.json"


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not file_path:
        return

    try:
        rel = Path(file_path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return  # outside the repo

    try:
        file_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    except Exception:
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
