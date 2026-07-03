#!/usr/bin/env python3
"""Generates one Claude Code subagent .md per system in
rayflow_file_map.json's `systems` object, at
`.claude/agents/rayflow-<system>-specialist.md`.

Same philosophy as scripts/generate_claude_md.py (see
docs/claude_md_generation.md): deterministic, no LLM, no network — pure
templating over already-existing, already-maintained sources:

  - rayflow_file_map.json  -> system description, file list + per-file
                               description, depends_on_systems/dependents_systems.
  - RAYFLOW_SOURCE_OF_TRUTH.json -> claims whose `evidence` overlaps the
                               system's files (reusing the same matching
                               logic _sot_scope.py uses to scope the
                               auditor to a diff), rendered as real prose
                               (text + evidence), not just pointers.
  - rayflow_issues.json    -> open issues whose `files` overlap the system's
                               files, or whose `claim_ids` belong to a claim
                               already surfaced above.

Earlier design (rayflow_agents_system.md §2-3) recommended AGAINST
embedding content in these files, specifically to avoid the staleness risk
of a hand-copied snapshot going stale the moment the source changes. That
concern doesn't apply here: this content is regenerated and re-staged on
every commit (same mechanism as CLAUDE.md), so it's never more than one
commit behind whatever it's summarizing — the risk that motivated "don't
embed" is exactly the risk this generator removes.

Wired at the pre-commit stage in .pre-commit-config.yaml (hook id
`agents-generate`). Never blocks: if a generated file's content differs
from what's on disk, it's overwritten and `git add`ed so the fresh version
rides along in the commit being made, same pattern as
scripts/generate_claude_md.py.

Usage: python3 scripts/generate_specialist_agents.py
(no args; regenerates every system's specialist unconditionally, but only
rewrites/stages files whose content actually changed.)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".claude" / "hooks"))

import _sot_scope  # noqa: E402

FILE_MAP_PATH = REPO_ROOT / "rayflow_file_map.json"
SOT_PATH = REPO_ROOT / "RAYFLOW_SOURCE_OF_TRUTH.json"
ISSUES_PATH = REPO_ROOT / "rayflow_issues.json"
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"

BANNER = """<!--
  ARCHIVO GENERADO — no editar a mano, se sobreescribe en cada commit.
  Fuente: rayflow_file_map.json (archivos, descripciones, dependencias entre
  sistemas) + RAYFLOW_SOURCE_OF_TRUTH.json (claims cuya evidencia cae en
  este sistema) + rayflow_issues.json (issues abiertos que lo mencionan).
  Regenerado por scripts/generate_specialist_agents.py, wireado como hook
  `agents-generate` en .pre-commit-config.yaml (stage pre-commit). Ver
  rayflow_agents_system.md.
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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _md_table_cell(text: str) -> str:
    """Escapes characters that would break a markdown table row: literal
    pipes (a real one in the source text would otherwise be read as a new
    column boundary) and newlines (collapsed to spaces)."""
    return text.replace("\n", " ").replace("|", "\\|")


def _files_section(system: str, info: dict, files: dict) -> str:
    lines = ["| archivo | descripción |", "|---|---|"]
    for path in sorted(info.get("files", [])):
        desc = _md_table_cell(files.get(path, {}).get("description", ""))
        lines.append(f"| `{path}` | {desc} |")
    return "\n".join(lines) + "\n"


def _dependencies_section(info: dict) -> str:
    deps_on = info.get("depends_on_systems", [])
    deps_by = info.get("dependents_systems", [])
    lines = []
    lines.append(
        "Depende de: " + (", ".join(f"`{s}`" for s in deps_on) if deps_on else "_(ningún otro sistema)_")
    )
    lines.append(
        "Es dependencia de: " + (", ".join(f"`{s}`" for s in deps_by) if deps_by else "_(ningún otro sistema)_")
    )
    return "\n\n".join(lines) + "\n"


def _sot_section(system_files: list[str], sot: dict) -> tuple[str, list[dict]]:
    claims = _sot_scope.affected_claims(system_files, sot=sot)
    if not claims:
        return (
            "_Ningún claim de RAYFLOW_SOURCE_OF_TRUTH.json tiene evidencia "
            "en archivos de este sistema todavía (evidencia vacía o no "
            "localizada, o el sistema no está cubierto por el SOT)._\n"
        ), []

    by_section: dict[str, list[dict]] = {}
    for c in claims:
        by_section.setdefault(c["section_id"], []).append(c)

    lines = []
    for section_id, section_claims in by_section.items():
        heading = section_claims[0].get("_heading", section_id)
        lines.append(f"### {heading}\n")
        for c in section_claims:
            evidence = ", ".join(f"`{e}`" for e in c.get("evidence", [])) or "_(sin evidencia registrada)_"
            lines.append(f"- **{c['id']}**: {c['text']} — evidencia: {evidence}")
        lines.append("")
    return "\n".join(lines), claims


def _issues_section(system_files: list[str], relevant_claims: list[dict], issues: dict) -> str:
    system_files_set = set(system_files)
    claim_ids = {c["id"] for c in relevant_claims}
    hits = []
    for issue in issues.get("issues", []):
        if set(issue.get("files", [])) & system_files_set or set(issue.get("claim_ids", [])) & claim_ids:
            hits.append(issue)

    if not hits:
        return "_Ningún issue abierto en rayflow_issues.json menciona este sistema._\n"

    lines = []
    for issue in hits:
        lines.append(f"- **{issue['id']}** ({issue['severity']}): {issue['title']}")
    return "\n".join(lines) + "\n"


def generate_one(system: str, info: dict, file_map: dict, sot: dict, issues: dict) -> str:
    files = file_map["files"]
    description = info.get("description", "").strip()
    sot_body, relevant_claims = _sot_section(info.get("files", []), sot)

    short_desc = description if len(description) <= 220 else description[:217].rsplit(" ", 1)[0] + "..."
    frontmatter_desc = (
        f"Especialista en el sistema `{system}` de rayflow. {short_desc} "
        f"Usar para tareas/issues que el file map o rayflow_issues.json marcan "
        f"como pertenecientes a este sistema."
    )

    parts = [
        "---",
        f"name: rayflow-{system}-specialist",
        # json.dumps produces a valid YAML double-quoted scalar (subset of
        # JSON string syntax) — needed because file-map descriptions
        # routinely contain ":" (e.g. "lifecycle: executes a..."), which a
        # bare/plain YAML scalar would parse as a new mapping key and break
        # the frontmatter.
        f"description: {json.dumps(frontmatter_desc, ensure_ascii=False)}",
        "tools: Read, Grep, Glob, Edit",
        "model: inherit",
        "---",
        "",
        BANNER,
        f"# Especialista: sistema `{system}`",
        "",
        description,
        "",
        f"## Archivos (`rayflow_file_map.json` → `systems.{system}.files`)",
        "",
        _files_section(system, info, files),
        "## Dependencias entre sistemas",
        "",
        _dependencies_section(info),
        "## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)",
        "",
        sot_body,
        "## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)",
        "",
        _issues_section(info.get("files", []), relevant_claims, issues),
        "---",
        f"_Generado desde el commit `{_git_short_head()}`. No asumas que conocés el "
        f"contenido de tus archivos de memoria — leélos con tus propios tools, "
        f"siempre, porque pueden haber cambiado desde la última vez que este "
        f"archivo se regeneró._",
        "",
    ]
    return "\n".join(parts)


def main() -> int:
    file_map = _load_json(FILE_MAP_PATH)
    sot = _load_json(SOT_PATH)
    # _sot_scope.affected_claims needs section headings for grouping; stash
    # them onto each claim before generating (mirrors what the CLI mode of
    # _sot_scope.py itself doesn't need, since it only prints ids).
    for section in sot.get("sections", []):
        for claim in section.get("claims", []):
            claim["_heading"] = section.get("heading", section["id"])
    issues = _load_json(ISSUES_PATH)

    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    changed = []
    for system, info in sorted(file_map.get("systems", {}).items()):
        target = AGENTS_DIR / f"rayflow-{system}-specialist.md"
        new_content = generate_one(system, info, file_map, sot, issues)
        old_content = target.read_text(encoding="utf-8") if target.exists() else None
        if new_content != old_content:
            target.write_text(new_content, encoding="utf-8")
            changed.append(target)

    if changed:
        subprocess.run(
            ["git", "add", *[str(p) for p in changed]],
            cwd=REPO_ROOT, check=False,
        )
        sys.stderr.write(
            f"[agents-generate] Regenerated and staged {len(changed)} "
            f"specialist agent(s): {', '.join(p.name for p in changed)}.\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
