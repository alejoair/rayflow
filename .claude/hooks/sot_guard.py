#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write): blocks direct edits to
RAYFLOW_SOURCE_OF_TRUTH.json unless RAYFLOW_SOT_UNLOCK=1 is set in this
session's environment.

Layer 1 of 2 in the SOT edit-blocking design (see docs/issues_system.md
§6.3): fast, in-session feedback against the common case (a session working
on something unrelated casually "fixing" a claim in passing). It is NOT the
real guarantee — a Bash command can still write the file directly, bypassing
this hook entirely, since it only matches the Edit/Write tools. Layer 2
(scripts/check_sot_commit_message.py, wired via .pre-commit-config.yaml) is
the actual enforcement: it runs at commit time against git's staged state,
regardless of how the file got there.

The env var is deliberately session-scoped and not persisted anywhere — it
has to be set fresh for a session that's doing deliberate SOT maintenance,
so it can't get left on by accident for unrelated future sessions.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _file_map import repo_relative  # noqa: E402

GUARDED_FILE = "RAYFLOW_SOURCE_OF_TRUTH.json"
UNLOCK_VAR = "RAYFLOW_SOT_UNLOCK"


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return

    if repo_relative(file_path) != GUARDED_FILE:
        return

    if os.environ.get(UNLOCK_VAR) == "1":
        return  # deliberately unlocked for this session

    reason = (
        f"[rayflow-sot-guard] Direct edits to {GUARDED_FILE} are blocked by "
        f"default — it's meant to change deliberately, not as a side effect "
        f"of unrelated work (see docs/issues_system.md §6.3). If this edit "
        f"is intentional and reviewed, set {UNLOCK_VAR}=1 in this session's "
        f"environment and retry. Note this only unlocks the tool call: the "
        f"commit itself will still be rejected unless the commit message "
        f"has a `Sot-Change: <reason>` trailer (Layer 2, enforced at commit "
        f"time no matter how the file was edited)."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


if __name__ == "__main__":
    main()
