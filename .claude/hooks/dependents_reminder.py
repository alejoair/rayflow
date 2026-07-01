#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): after a mapped file is edited, reminds
the model which other files list it as a dependent, so it doesn't forget
knock-on effects (e.g. editing validator.py affects its test file).

Silent no-op if the file isn't in the map or has no dependents.
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

    dependents = entry.get("dependents") or []
    if not dependents:
        return

    context = (
        f"[rayflow_file_map] You just edited {rel}, which is used by: "
        + ", ".join(dependents)
        + ". Consider whether any of those need updating too."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }))


if __name__ == "__main__":
    main()
