"""Shared helpers for Claude Code hooks that read rayflow_file_map.json.

Not a hook itself — imported by the hook scripts in this directory.
"""
import ast
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


_MAX_SYMBOLS = 30


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    try:
        args = ast.unparse(node.args)
    except Exception:
        args = "..."
    ret = f" -> {ast.unparse(node.returns)}" if node.returns is not None else ""
    return f"{prefix} {node.name}({args}){ret}"


def _class_header(node: ast.ClassDef) -> str:
    try:
        bases = [ast.unparse(b) for b in node.bases]
    except Exception:
        bases = []
    return f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"


def extract_python_symbols(file_path: str, max_symbols: int = _MAX_SYMBOLS) -> list[str]:
    """Computed live from the file on disk (never cached, never stale,
    unlike the hand-written prose description) — top-level functions and
    classes with their real signatures, plus one indent level of class
    methods. Returns [] for non-.py files or on any parse failure."""
    if not file_path.endswith(".py"):
        return []
    try:
        src = Path(file_path).read_text(encoding="utf-8")
        tree = ast.parse(src, filename=file_path)
    except Exception:
        return []

    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(_signature(node))
        elif isinstance(node, ast.ClassDef):
            symbols.append(_class_header(node))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append("    " + _signature(child))
        if len(symbols) >= max_symbols:
            symbols.append(f"... ({len(tree.body)} top-level definitions total, truncated)")
            break
    return symbols
