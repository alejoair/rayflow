#!/usr/bin/env python3
"""Standalone diagnostic script — NOT a hook, NOT wired into pre-commit or
any Claude Code hook. Reports RAYFLOW_SOURCE_OF_TRUTH.json claims whose
`evidence` is 100% orphaned: every repo-relative file path it cites no
longer exists in the repo. These are strong candidates for describing code
that was removed/renamed and never updated in the SOT.

A claim only gets flagged if EVERY evidence entry is missing. Per
docs/issues_system.md §4, an empty `evidence` array means "not located
yet", not "false" — claims with empty evidence are skipped entirely (not
orphaned, just unaudited), and a claim with a mix of existing and missing
evidence still has *something* to stand on, so it's not reported either.

This script never writes, edits, or deletes anything, and it never blocks
a commit — it's a manual tool to run by hand when someone wants to clean
up the SOT, the mechanical/no-LLM counterpart to the `orphan_claim` kind
that `rayflow-auditor` can also produce (see .claude/agents/rayflow-auditor.md
and docs/issues_system.md), except this one only checks path existence —
it doesn't judge whether a claim's *text* is still true.

Reuses the evidence-path parsing (stripping an optional '#symbol' suffix)
and SOT-loading helpers already implemented in .claude/hooks/_sot_scope.py
instead of reimplementing them.

Usage (no arguments, no flags):

    python3 scripts/find_orphaned_claims.py

Checks each evidence path against `git ls-files` (the tracked file set) by
default; falls back to a plain filesystem existence check under the repo
root if `git` isn't available (e.g. running outside a checkout). Prints a
human-readable report to stdout. Always exits 0 — this is a read-only
report, not a gate.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".claude" / "hooks"))

import _sot_scope  # noqa: E402  (repo-local helper; reuses its evidence-path parsing/SOT loading — see .claude/hooks/_sot_scope.py)


def tracked_files() -> set[str] | None:
    """Returns the set of repo-relative paths tracked by git, or None if
    `git` isn't available / this isn't a git checkout — caller falls back
    to a plain filesystem existence check in that case."""
    try:
        out = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except Exception:
        return None
    return {line.strip() for line in out.splitlines() if line.strip()}


def file_exists(rel_path: str, tracked: set[str] | None) -> bool:
    if tracked is not None:
        return rel_path in tracked
    return (REPO_ROOT / rel_path).exists()


def main() -> None:
    sot = _sot_scope.load_sot()
    if sot is None:
        print("Could not read RAYFLOW_SOURCE_OF_TRUTH.json — aborting.", file=sys.stderr)
        return

    tracked = tracked_files()
    if tracked is None:
        print(
            "Warning: `git ls-files` unavailable — falling back to a plain "
            "filesystem existence check (current working tree, not git's "
            "tracked index).\n",
            file=sys.stderr,
        )

    orphaned: list[tuple[str, str, list[str]]] = []  # (claim_id, text, evidence)

    for section in sot.get("sections", []):
        for claim in section.get("claims", []):
            evidence = claim.get("evidence", [])
            if not evidence:
                continue  # empty evidence = "not located yet", not orphaned — see docs/issues_system.md §4
            missing = [
                e for e in evidence
                if not file_exists(_sot_scope._evidence_file(e), tracked)
            ]
            if len(missing) == len(evidence):
                orphaned.append((claim["id"], claim.get("text", ""), evidence))

    if not orphaned:
        print(
            "No orphaned claims found — every claim with evidence has at "
            "least one cited file that still exists in the repo."
        )
        return

    print(
        f"Found {len(orphaned)} claim(s) whose evidence is 100% orphaned "
        "(every cited file is gone):\n"
    )
    for claim_id, text, evidence in orphaned:
        print(f"- {claim_id}")
        print(f"    text: {text}")
        print(f"    evidence (all missing): {evidence}")
        print()

    print(
        "These are candidates to be describing code that no longer exists "
        "in the repo — review manually and, if confirmed, resolve via the "
        "normal rayflow-issue-writer flow (this script itself never edits "
        "or deletes anything)."
    )


if __name__ == "__main__":
    main()
