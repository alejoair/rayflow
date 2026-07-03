#!/usr/bin/env python3
"""Generates CLAUDE.md from rayflow_system_prompt.md (hand-maintained prose)
plus a compact, auto-generated index of RAYFLOW_SOURCE_OF_TRUTH.json and
rayflow_file_map.json.

Wired at the `pre-commit` stage in .pre-commit-config.yaml (hook id
`claude-md-generate`): runs on every commit, and if the regenerated content
differs from what's on disk, overwrites CLAUDE.md and `git add`s it so the
new version rides along in the same commit — no blocking, no approval step,
just always-fresh. See docs/claude_md_generation.md for the full design and
rationale (in particular: why CLAUDE.md stays git-tracked rather than
gitignored — it removes the fresh-clone bootstrap problem entirely, since a
clone always has *some* CLAUDE.md, worst case one commit stale).

The index appended after the system_prompt.md content is deliberately NOT a
full dump of the SOT's ~215 claims (that would make CLAUDE.md's size scale
with the SOT and mostly restate what system_prompt.md's prose already says).
It lists section headings + claim counts + a pointer to read the SOT file
directly, scoped to that section id, when detail is actually needed — same
"pull, not push" pattern already used by .claude/hooks/file_map_context.py.

Usage: python3 scripts/generate_claude_md.py
(no args; always operates on the whole repo from REPO_ROOT.)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_PROMPT_PATH = REPO_ROOT / "rayflow_system_prompt.md"
SOT_PATH = REPO_ROOT / "RAYFLOW_SOURCE_OF_TRUTH.json"
FILE_MAP_PATH = REPO_ROOT / "rayflow_file_map.json"
CLAUDE_MD_PATH = REPO_ROOT / "CLAUDE.md"

BANNER = """<!--
  ARCHIVO GENERADO — no editar a mano, se sobreescribe en cada commit.
  Fuente: rayflow_system_prompt.md (prosa) + RAYFLOW_SOURCE_OF_TRUTH.json +
  rayflow_file_map.json (índices, más abajo). Regenerado por
  scripts/generate_claude_md.py, wireado como hook `claude-md-generate` en
  .pre-commit-config.yaml (stage pre-commit). Ver docs/claude_md_generation.md.
-->
"""


def _git_short_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _sot_index() -> str:
    try:
        sot = json.loads(SOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return "_(RAYFLOW_SOURCE_OF_TRUTH.json no disponible al generar este archivo)_\n"

    lines = [
        "Cada sección abajo corresponde a un heading de este documento y "
        "tiene sus afirmaciones registradas como claims verificables en "
        "`RAYFLOW_SOURCE_OF_TRUTH.json` — leé ese archivo, filtrando por "
        "`section_id`, para el detalle de cada claim (texto + evidencia en "
        "código + docs relacionados). No se listan acá para no duplicar la "
        "prosa de arriba ni hacer que este archivo crezca con cada claim "
        "nuevo.\n",
        "| section_id | heading | claims |",
        "|---|---|---|",
    ]
    for section in sot.get("sections", []):
        n = len(section.get("claims", []))
        heading = section.get("heading", "")
        lines.append(f"| `{section['id']}` | {heading} | {n} |")
    return "\n".join(lines) + "\n"


def _systems_index() -> str:
    try:
        fm = json.loads(FILE_MAP_PATH.read_text(encoding="utf-8"))
    except Exception:
        return "_(rayflow_file_map.json no disponible al generar este archivo)_\n"

    lines = [
        "Agrupación de los archivos del repo en sistemas, con su descripción "
        "y cantidad de archivos — el detalle completo (lista de archivos, "
        "`depends_on`/`dependents`) vive en `rayflow_file_map.json`.\n",
        "| sistema | archivos | descripción |",
        "|---|---|---|",
    ]
    for name, info in sorted(fm.get("systems", {}).items()):
        n = len(info.get("files", []))
        desc = info.get("description", "")
        lines.append(f"| `{name}` | {n} | {desc} |")
    return "\n".join(lines) + "\n"


def generate() -> str:
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    parts = [
        BANNER,
        "# CLAUDE.md\n",
        system_prompt.rstrip() + "\n",
        "\n## Índice de `RAYFLOW_SOURCE_OF_TRUTH.json`\n\n" + _sot_index(),
        "\n## Índice de sistemas (`rayflow_file_map.json`)\n\n" + _systems_index(),
        f"\n---\n_Generado desde el commit `{_git_short_head()}`._\n",
    ]
    return "\n".join(parts)


def main() -> int:
    new_content = generate()
    old_content = CLAUDE_MD_PATH.read_text(encoding="utf-8") if CLAUDE_MD_PATH.exists() else None

    if new_content == old_content:
        return 0

    CLAUDE_MD_PATH.write_text(new_content, encoding="utf-8")

    # Re-stage so the regenerated file rides along in the commit being made
    # right now (pre-commit stage hook — the working tree write above
    # otherwise wouldn't be included in what's about to be committed).
    subprocess.run(["git", "add", str(CLAUDE_MD_PATH)], cwd=REPO_ROOT, check=False)
    sys.stderr.write(f"[claude-md-generate] Regenerated and staged {CLAUDE_MD_PATH.name}.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
