"""Shared helper (not a hook itself): given a list of changed file paths,
returns which RAYFLOW_SOURCE_OF_TRUTH.json claims are potentially affected —
claims whose `evidence` array references one of those files (ignoring any
'#symbol' suffix on the evidence entry) — and, transitively, which OTHER
documentation files (a claim's `docs` array — README.md, a SKILL.md,
guide.py, ... deliberately excludes CLAUDE.md, which is slated to become a
generated rendering of the SOT rather than an independent doc that can drift)
might need a look too.

Used to scope the audit agent to a commit's actual diff instead of re-checking
all ~215 claims on every commit, and to warn/block on "you touched code that
backs a claim also documented elsewhere, but didn't touch that doc" in a
pre-commit hook. Also usable standalone from the CLI (e.g. from a pre-commit
hook) to decide whether the auditor needs to run at all — no affected claims
means nothing to check.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SOT_PATH = REPO_ROOT / "RAYFLOW_SOURCE_OF_TRUTH.json"


def _evidence_file(entry: str) -> str:
    """Strips an optional '#symbol' suffix from an evidence entry."""
    return entry.split("#", 1)[0]


def load_sot() -> dict | None:
    try:
        return json.loads(SOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def affected_claims(changed_files: list[str], sot: dict | None = None) -> list[dict]:
    """Returns claim dicts (with an added `section_id`) whose evidence
    overlaps with `changed_files`. `changed_files` should be repo-relative
    paths (posix style), matching what's stored in each claim's evidence."""
    if sot is None:
        sot = load_sot()
    if sot is None:
        return []

    changed = set(changed_files)
    hits: list[dict] = []
    for section in sot.get("sections", []):
        for claim in section.get("claims", []):
            evidence_files = {_evidence_file(e) for e in claim.get("evidence", [])}
            if evidence_files & changed:
                hits.append({**claim, "section_id": section["id"]})
    return hits


def affected_docs(changed_files: list[str], sot: dict | None = None) -> list[str]:
    """Returns the sorted, deduped union of `docs` across every claim
    affected by `changed_files` — the OTHER documentation files (never
    CLAUDE.md, see module docstring) that might need a look because the code
    backing one of their claims just changed."""
    docs: set[str] = set()
    for claim in affected_claims(changed_files, sot):
        docs.update(claim.get("docs", []))
    return sorted(docs)


def main() -> None:
    """CLI mode: `python3 _sot_scope.py [--docs] file1.py file2.tsx ...`
    prints the affected claim ids (default) or, with --docs, the affected
    documentation files instead. No file args -> reads paths from stdin (one
    per line), convenient piped from `git diff --name-only`."""
    args = sys.argv[1:]
    want_docs = "--docs" in args
    args = [a for a in args if a != "--docs"]
    changed_files = args if args else [l.strip() for l in sys.stdin if l.strip()]

    if want_docs:
        for doc in affected_docs(changed_files):
            print(doc)
    else:
        for claim in affected_claims(changed_files):
            print(claim["id"])


if __name__ == "__main__":
    main()
