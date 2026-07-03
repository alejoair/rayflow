#!/usr/bin/env python3
"""commit-msg stage hook (wired via .pre-commit-config.yaml, framework
`pre-commit`): if RAYFLOW_SOURCE_OF_TRUTH.json is part of this commit's
staged changes, requires a `Sot-Change: <reason>` trailer in the commit
message, or rejects the commit.

Layer 2 of 2 in the SOT edit-blocking design (see docs/issues_system.md
§6.3) — the real enforcement layer, unlike .claude/hooks/sot_guard.py (which
only gates Claude Code's own Edit/Write tool calls within a session). This
one runs at commit time against git's staged state, so it applies no matter
how the file was edited: Claude Code, a text editor, a script, `sed`,
anything. There is no env-var bypass here on purpose — the trailer has to be
typed fresh into the commit message every time, so it can't be left "on" by
accident for unrelated future commits the way an env var could.

Usage: python3 scripts/check_sot_commit_message.py <path-to-commit-msg-file>
(pre-commit supplies the path automatically for commit-msg stage hooks.)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

GUARDED_FILE = "RAYFLOW_SOURCE_OF_TRUTH.json"
TRAILER_RE = re.compile(r"^Sot-Change:\s*\S.*$", re.MULTILINE)


def staged_files() -> set[str]:
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, check=True,
        ).stdout
    except Exception:
        # If we can't tell what's staged, fail open — this check is a
        # deliberate-change gate, not a security boundary; don't block
        # unrelated commits over a git invocation glitch.
        return set()
    return {line.strip() for line in out.splitlines() if line.strip()}


def main() -> int:
    if len(sys.argv) < 2:
        return 0  # wiring problem (no message file path) — don't block on it

    if GUARDED_FILE not in staged_files():
        return 0  # this commit doesn't touch the SOT, nothing to check

    msg_path = Path(sys.argv[1])
    try:
        message = msg_path.read_text(encoding="utf-8")
    except Exception:
        return 0

    if TRAILER_RE.search(message):
        return 0

    sys.stderr.write(
        f"\n[sot-guard] This commit changes {GUARDED_FILE} but the commit "
        f"message has no `Sot-Change: <reason>` trailer.\n"
        f"RAYFLOW_SOURCE_OF_TRUTH.json is meant to change deliberately, not "
        f"as a side effect of unrelated work. If this change is intentional "
        f"and reviewed, add a trailer and re-commit, e.g.:\n\n"
        f"    Sot-Change: corrected the OnStart entry-pin claim after the "
        f"@entry_node refactor\n\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
