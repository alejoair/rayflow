"""Shared helper for hooks that use `ty` (Astral's Rust type checker) to
give diff-based, advisory-only type-check feedback on edited .py files.

Not a hook itself — imported by ty_diff_pre.py / ty_diff_post.py.
"""
import re
import shutil
import subprocess
from pathlib import Path

_LINE_RE = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\d+):(?P<col>\d+): "
    r"(?P<severity>\w+)\[(?P<rule>[\w-]+)\] (?P<message>.*)$"
)

_TY_AVAILABLE = shutil.which("ty") is not None


def ty_diagnostics(file_path: str, timeout: float = 4.0) -> list[dict] | None:
    """Runs `ty check` on a single file and returns its parsed diagnostics.
    Returns None if ty isn't installed or the check couldn't run at all
    (distinct from an empty list, which means it ran clean) — callers use
    None to bail out silently rather than reporting a false "no new
    diagnostics"."""
    if not _TY_AVAILABLE or not file_path.endswith(".py"):
        return None
    if not Path(file_path).is_file():
        return []  # e.g. Write creating a brand new file: no prior diagnostics possible
    try:
        proc = subprocess.run(
            ["ty", "check", file_path, "--output-format=concise"],
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception:
        return None
    diags = []
    for line in proc.stdout.splitlines():
        m = _LINE_RE.match(line)
        if m:
            diags.append(m.groupdict())
    return diags


def diagnostic_key(diag: dict) -> tuple:
    """Line/col-independent identity for a diagnostic, so an edit that
    merely shifts line numbers elsewhere in the file doesn't make a
    pre-existing diagnostic look newly introduced."""
    return (diag["rule"], diag["message"])
