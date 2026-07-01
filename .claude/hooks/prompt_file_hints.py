#!/usr/bin/env python3
"""UserPromptSubmit hook: if the prompt contains a word matching a
file's basename/stem in rayflow_file_map.json (e.g. "validator",
"NodeCard", "guide.py"), surfaces that file's description as
additionalContext.

Conservative by design — literal stem matching only, not fuzzy keyword
scoring, to avoid noise on generic prompts. Capped at 3 matches.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _file_map import load_map  # noqa: E402

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_MAX_MATCHES = 3
_MIN_WORD_LEN = 4


def _stem(path: str) -> str:
    return Path(path).stem.lower()


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    prompt = payload.get("prompt", "")
    if not prompt:
        return

    file_map = load_map()
    if file_map is None:
        return
    files = file_map.get("files", {})

    words = {w.lower() for w in _WORD_RE.findall(prompt) if len(w) >= _MIN_WORD_LEN}
    if not words:
        return

    by_stem: dict[str, list[str]] = {}
    for path in files:
        by_stem.setdefault(_stem(path), []).append(path)

    matched_paths: list[str] = []
    for w in words:
        candidates = by_stem.get(w)
        if not candidates:
            continue
        matched_paths.extend(candidates)
        if len(matched_paths) >= _MAX_MATCHES:
            break

    if not matched_paths:
        return

    lines = ["[rayflow_file_map] Your prompt mentions files in the map:"]
    for path in matched_paths[:_MAX_MATCHES]:
        lines.append(f"- {path}: {files[path].get('description', '')}")

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n".join(lines),
        }
    }))


if __name__ == "__main__":
    main()
