#!/usr/bin/env python3
"""PreToolUse hook (Read|Edit|Write): looks up the file about to be
touched in rayflow_file_map.json and surfaces its description plus
depends_on/dependents edges as additionalContext, so the model knows
upfront what the file does and what else might need checking. For .py
files, also lists real function/class signatures extracted live via
`ast` — unlike the hand-written description, this can never go stale
since it's recomputed from the actual file on disk every time. Also
surfaces the file's architectural "system" (a coarser grouping than
individual files, e.g. "engine", "editor-api") and which other systems
depend on it — the file-level graph answers "which files import this,"
this answers "which parts of the architecture care about this."

Silent no-op if the file isn't in the map, the map is missing, or the
input is malformed — never blocks a tool call.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _file_map import extract_python_symbols, load_map, repo_relative, system_context  # noqa: E402


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

    sys_ctx = system_context(rel, file_map)
    if sys_ctx:
        lines.append(sys_ctx)

    symbols = extract_python_symbols(file_path)
    if symbols:
        lines.append("Symbols (live from disk): " + "; ".join(symbols))

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": "\n".join(lines),
        }
    }))


if __name__ == "__main__":
    main()
