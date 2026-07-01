#!/usr/bin/env python3
"""UserPromptSubmit hook: matches the prompt against trigger phrases in
rayflow_workflows.json and surfaces the matching workflow's checklist as
additionalContext. Complements prompt_file_hints.py (which matches
individual file names) at a coarser grain: "what kind of change is this"
rather than "which file is this about" — the checklist arrives before
the first edit instead of being discovered file-by-file.

Silent no-op if the workflows file is missing/unreadable or nothing
matches. Never blocks.
"""
import json
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
REPO_ROOT = HOOK_DIR.parent.parent
WORKFLOWS_PATH = REPO_ROOT / "rayflow_workflows.json"

_MAX_MATCHES = 2


def _load_workflows() -> list[dict]:
    try:
        return json.loads(WORKFLOWS_PATH.read_text(encoding="utf-8")).get("workflows", [])
    except Exception:
        return []


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    prompt = (payload.get("prompt") or "").lower()
    if not prompt:
        return

    workflows = _load_workflows()
    if not workflows:
        return

    matched = []
    for wf in workflows:
        if any(trigger.lower() in prompt for trigger in wf.get("triggers", [])):
            matched.append(wf)
        if len(matched) >= _MAX_MATCHES:
            break

    if not matched:
        return

    blocks = []
    for wf in matched:
        lines = [f"[rayflow_workflows] {wf.get('title', wf.get('id', ''))} — checklist:"]
        for step in wf.get("checklist", []):
            lines.append(f"  - {step}")
        systems = wf.get("systems") or []
        if systems:
            lines.append(f"  Systems typically involved: {', '.join(systems)}")
        blocks.append("\n".join(lines))

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n\n".join(blocks),
        }
    }))


if __name__ == "__main__":
    main()
