"""Shared helpers for Claude Code hooks that read rayflow_file_map.json.

Not a hook itself — imported by the hook scripts in this directory.
"""
import json
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
REPO_ROOT = HOOK_DIR.parent.parent  # .claude/hooks/ -> .claude/ -> repo root
MAP_PATH = REPO_ROOT / "rayflow_file_map.json"


def load_map() -> dict | None:
    """Returns the parsed file map, or None if it's missing/unreadable."""
    try:
        return json.loads(MAP_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def repo_relative(file_path: str) -> str | None:
    """Resolves an absolute file_path to a repo-relative posix path, or
    None if it can't be resolved or falls outside the repo."""
    try:
        return Path(file_path).resolve().relative_to(REPO_ROOT).as_posix()
    except (ValueError, OSError):
        return None
