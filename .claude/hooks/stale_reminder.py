#!/usr/bin/env python3
"""Stop hook: before ending the turn, scans the session transcript for
Edit/Write calls made since the last check. If any touched a file that's
listed in rayflow_file_map.json, blocks once (via decision:"block") to
remind the model to check whether that file's description still matches
its behavior — content can drift out of sync with the map on an Edit,
unlike a file being added/removed (which staleness_guard already covers).

Uses stop_hook_active to fire at most once per stop cycle, avoiding an
infinite block loop. Tracks a per-session read offset in a state file
outside the repo so re-runs don't re-flag edits already reminded about.

Silent no-op on any parsing failure — never blocks a tool call, and only
blocks the Stop event itself when it has something concrete to report.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _file_map import load_map, repo_relative  # noqa: E402

STATE_DIR = Path(tempfile.gettempdir()) / "rayflow-stale-reminder"


def _state_path(session_id: str) -> Path:
    return STATE_DIR / f"{session_id}.json"


def _read_offset(session_id: str) -> int | None:
    """Returns the last recorded line offset, or None if this is the
    first Stop fire seen for this session — in that case the caller
    should just record a baseline instead of scanning from line 0 (which
    would dump the whole session's history on the very first check)."""
    try:
        return json.loads(_state_path(session_id).read_text(encoding="utf-8")).get("offset")
    except Exception:
        return None


def _write_offset(session_id: str, offset: int) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_path(session_id).write_text(json.dumps({"offset": offset}), encoding="utf-8")
    except Exception:
        pass


def _edited_paths_since(transcript_path: str, offset: int) -> tuple[set[str], int]:
    lines = Path(transcript_path).read_text(encoding="utf-8").splitlines()
    paths: set[str] = set()
    for line in lines[offset:]:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get("isSidechain"):
            continue
        content = (entry.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") not in ("Edit", "Write"):
                continue
            fp = (block.get("input") or {}).get("file_path")
            if fp:
                paths.add(fp)
    return paths, len(lines)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    transcript_path = payload.get("transcript_path")
    session_id = payload.get("session_id")
    if not transcript_path or not session_id:
        return

    offset = _read_offset(session_id)
    try:
        raw_paths, new_offset = _edited_paths_since(transcript_path, offset)
    except Exception:
        return
    _write_offset(session_id, new_offset)

    if payload.get("stop_hook_active"):
        return  # already nudged once this stop cycle; don't loop

    file_map = load_map()
    if file_map is None:
        return
    files = file_map.get("files", {})

    mapped_edits = sorted({
        rel for fp in raw_paths
        if (rel := repo_relative(fp)) is not None and rel in files
    })
    if not mapped_edits:
        return

    reason = (
        "[rayflow_file_map] Before finishing: this turn edited file(s) that are "
        "described in rayflow_file_map.json — " + ", ".join(mapped_edits) + ". "
        "If the edit changed what the file does (not just a comment/formatting "
        "tweak), update its \"description\" in rayflow_file_map.json so the map "
        "stays accurate for future sessions. If the description still holds, "
        "no action needed."
    )
    print(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    main()
