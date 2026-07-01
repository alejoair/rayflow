#!/usr/bin/env python3
"""SessionStart hook: injects a one-line pointer to rayflow_file_map.json
so a fresh session knows it exists without having to discover it on its
own. Silent no-op if the map is missing.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _file_map import load_map  # noqa: E402


def main() -> None:
    file_map = load_map()
    if file_map is None:
        return

    count = file_map.get("file_count", len(file_map.get("files", {})))
    root = file_map.get("root", "")
    context = (
        f"[rayflow_file_map] This repo has a generated file map at "
        f"rayflow_file_map.json ({count} files) — {root}. Each entry has a "
        f"short description plus depends_on/dependents edges computed from "
        f"real imports. It's auto-surfaced per-file by other hooks here; "
        f"look it up directly for a repo-wide overview."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }))


if __name__ == "__main__":
    main()
