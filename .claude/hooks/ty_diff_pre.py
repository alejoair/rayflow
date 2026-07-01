#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write, .py files): snapshots `ty`'s diagnostics
for the file about to be touched, so the paired PostToolUse hook
(ty_diff_post.py) can report only diagnostics newly introduced by this
edit. Advisory only — never blocks, and silently no-ops if ty isn't
installed.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _file_map import repo_relative  # noqa: E402
from _ty_check import ty_diagnostics  # noqa: E402

STATE_DIR = Path(tempfile.gettempdir()) / "rayflow-ty-check"


def _state_path(session_id: str, rel: str) -> Path:
    return STATE_DIR / f"{session_id}__{rel.replace('/', '__')}.json"


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    file_path = (payload.get("tool_input") or {}).get("file_path")
    session_id = payload.get("session_id")
    if not file_path or not session_id or not file_path.endswith(".py"):
        return

    rel = repo_relative(file_path)
    if rel is None:
        return

    diags = ty_diagnostics(file_path)
    if diags is None:
        return  # ty not available

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_path(session_id, rel).write_text(json.dumps(diags), encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    main()
