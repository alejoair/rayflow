#!/usr/bin/env python3
"""pre-commit stage hook (wired via .pre-commit-config.yaml, framework
`pre-commit`): runs the rayflow-auditor subagent, scoped to the claims
whose `evidence` overlaps this commit's staged diff, and **blocks the
commit** if the auditor finds a real divergence (i.e. it writes to
rayflow_issues.json).

Design decision (see docs/issues_system.md §6.2): blocking, not
async/informational. Rationale: the alternative (a background/advisory
step) means the audit result routinely arrives after the commit that
should have been flagged, and it's easy to end up training everyone to
just ignore it. Blocking is only paid on commits that actually touch
files backing a claim (see the cheap pre-check below) — commits outside
that scope skip the LLM call entirely, so the added latency is scoped to
where it matters.

This hook is the direct counterpart to scripts/check_sot_commit_message.py
(Layer 2 of the SOT edit-blocking design), but it addresses a different
problem: that script guards *edits to the SOT itself*; this one guards
*code changes that silently invalidate what the SOT already claims*.

Fails OPEN (exit 0, with a stderr warning) on infra problems — the
`claude` binary missing, a timeout, a non-zero exit with no issues
written. Those aren't the auditor "finding something", they're the
auditor failing to run, and blocking every commit in this repo on
infra flakiness would defeat the tool's own purpose. It only fails
CLOSED (exit 1) when the auditor actually produced new content in
rayflow_issues.json — the one signal that means "reviewed, and there's
something for a human to look at before this commit lands".

Usage: python3 scripts/run_sot_audit.py
(no args; reads the staged diff directly via git, like
check_sot_commit_message.py does.)
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".claude" / "hooks"))

import _sot_scope  # noqa: E402  (repo-local helper, see .claude/hooks/_sot_scope.py)

ISSUES_FILE = REPO_ROOT / "rayflow_issues.json"
AUDIT_TIMEOUT_S = 300


def staged_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except Exception:
        # Same fail-open rationale as check_sot_commit_message.py: this is
        # a deliberate-change gate, not a security boundary.
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def build_prompt(claim_ids: list[str]) -> str:
    run_id = f"audit-{datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    return (
        "Auditá RAYFLOW_SOURCE_OF_TRUTH.json contra el código real, "
        "siguiendo tu método normal (ver tu system prompt). El scope de "
        "esta corrida ya está calculado a partir del diff staged de este "
        "commit (no hace falta que lo recalcules corriendo "
        "_sot_scope.py vos mismo, aunque podés si querés doble-chequear "
        "algo puntual): claim_ids = "
        f"{claim_ids}. "
        f'detected_by = {{"agent": "rayflow-auditor", "run_id": "{run_id}", '
        '"trigger": "pre-commit"}.'
    )


def main() -> int:
    files = staged_files()
    if not files:
        return 0

    claims = _sot_scope.affected_claims(files)
    if not claims:
        return 0  # nothing in the SOT is backed by these files — skip the LLM call entirely

    claim_ids = sorted({c["id"] for c in claims})
    prompt = build_prompt(claim_ids)

    before = ISSUES_FILE.read_bytes() if ISSUES_FILE.exists() else b""

    try:
        result = subprocess.run(
            ["claude", "-p", "--agent", "rayflow-auditor", prompt],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=AUDIT_TIMEOUT_S,
        )
    except FileNotFoundError:
        sys.stderr.write(
            "\n[sot-audit] `claude` binary not found on PATH — skipping the "
            f"audit for {len(claim_ids)} claim(s) in scope. Not blocking the "
            "commit on this (infra problem, not a content problem).\n"
        )
        return 0
    except subprocess.TimeoutExpired:
        sys.stderr.write(
            f"\n[sot-audit] rayflow-auditor timed out after {AUDIT_TIMEOUT_S}s "
            f"auditing {len(claim_ids)} claim(s) — skipping, not blocking the "
            "commit on this.\n"
        )
        return 0

    after = ISSUES_FILE.read_bytes() if ISSUES_FILE.exists() else b""

    if after == before:
        if result.returncode != 0:
            sys.stderr.write(
                "\n[sot-audit] rayflow-auditor exited non-zero but didn't "
                f"write any issue (stderr below) — not blocking the commit "
                f"on this:\n{result.stderr}\n"
            )
        return 0

    sys.stderr.write(
        "\n[sot-audit] rayflow-auditor found a divergence between "
        f"RAYFLOW_SOURCE_OF_TRUTH.json and the code in this commit, and "
        f"wrote to {ISSUES_FILE.name}. Review the new issue(s), then "
        f"`git add {ISSUES_FILE.name}` and re-commit.\n\n"
        f"{result.stdout}\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
