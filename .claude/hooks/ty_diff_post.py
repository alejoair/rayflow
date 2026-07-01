#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write, .py files): re-runs `ty check` on the
file just edited and reports only diagnostics that are NEW compared to
the pre-edit snapshot taken by ty_diff_pre.py.

Diffing (instead of reporting raw ty output) matters on this codebase
specifically: ty can't see through Ray's `@ray.remote` metaprogramming
(it injects `.remote()` at runtime), so a flat `ty check` run is full of
false positives on every ray_node file. Those show up in BOTH the before
and after snapshot and cancel out, leaving only diagnostics the edit
actually introduced. Advisory only — never blocks, silently no-ops if ty
isn't installed.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _file_map import repo_relative  # noqa: E402
from _ty_check import diagnostic_key, ty_diagnostics  # noqa: E402

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

    state_file = _state_path(session_id, rel)
    try:
        before = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        before = []
    try:
        state_file.unlink(missing_ok=True)
    except Exception:
        pass

    after = ty_diagnostics(file_path)
    if after is None:
        return  # ty not available

    before_keys = {diagnostic_key(d) for d in before}
    new_diags = [d for d in after if diagnostic_key(d) not in before_keys]
    if not new_diags:
        return

    lines = [f"[ty] This edit introduced {len(new_diags)} new type diagnostic(s) in {rel}:"]
    for d in new_diags[:10]:
        lines.append(f"  {rel}:{d['line']}:{d['col']} {d['severity']}[{d['rule']}] {d['message']}")
    if len(new_diags) > 10:
        lines.append(f"  ... and {len(new_diags) - 10} more")

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(lines),
        }
    }))


if __name__ == "__main__":
    main()
