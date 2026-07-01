#!/usr/bin/env python3
"""PostToolUse hook (Write|Bash): heuristically detects when
rayflow_file_map.json may have gone stale — a new file was written that
isn't in the map, or a shell command looks like it deletes a file that
IS in the map.

Best-effort and silent by default; only speaks up when it has something
concrete to flag. Never blocks the underlying tool call.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _file_map import load_map, repo_relative  # noqa: E402

_DELETE_RE = re.compile(r"\b(?:rm\s+(?:-\w+\s+)*|git\s+rm\s+(?:-\w+\s+)*)(\S+)")


def _emit(msg: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"[rayflow_file_map] {msg}",
        }
    }))


def _check_write(payload: dict, file_map: dict) -> None:
    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return
    rel = repo_relative(file_path)
    if rel is None:
        return
    if rel in file_map.get("files", {}):
        return
    if rel.startswith("rayflow/editor/static/dist/"):
        return  # generated build output, not expected to be individually mapped
    _emit(
        f"{rel} isn't listed in rayflow_file_map.json. If this is a real "
        f"source file (not a scratch/temp file), the map may need regenerating."
    )


def _check_bash(payload: dict, file_map: dict) -> None:
    command = (payload.get("tool_input") or {}).get("command", "")
    files = file_map.get("files", {})
    for m in _DELETE_RE.finditer(command):
        candidate = m.group(1).strip("\"'")
        for rel in files:
            if rel == candidate or rel.endswith("/" + candidate):
                _emit(
                    f"This command appears to delete {rel}, which is still "
                    f"listed in rayflow_file_map.json. The map may need regenerating."
                )
                return


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    file_map = load_map()
    if file_map is None:
        return

    tool_name = payload.get("tool_name")
    if tool_name == "Write":
        _check_write(payload, file_map)
    elif tool_name == "Bash":
        _check_bash(payload, file_map)


if __name__ == "__main__":
    main()
