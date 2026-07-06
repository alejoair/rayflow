#!/usr/bin/env python3
"""Generates one Claude Code subagent .md per macrosistema (as declared in
rayflow_file_map.json's `systems.<system>.macrosistemas` field) at
`.claude/agents/rayflow-macro-<macrosistema>.md`.

Fase 3 of the macrosistemas project (see rayflow_agents_system.md history):
Fase 1 added a `macrosistemas` list per system to rayflow_file_map.json,
preserved across regenerations by scripts/generate_file_map.py. Fase 2 added
a "## Contactos" section to scripts/generate_specialist_agents.py's output.
This script is the Fase 3 counterpart one level up: instead of one agent per
system, one agent per macrosistema, grouping systems purely by reading their
`macrosistemas` field (a system can belong to more than one macro — e.g.
`packaging` is in both `interfaces` and `frontend` — so this is a
many-to-many grouping, not a partition; the grouping itself is never
hardcoded here).

Same philosophy as scripts/generate_claude_md.py and
scripts/generate_specialist_agents.py: deterministic, no LLM, no network.
Reuses scripts/generate_specialist_agents.py's helpers directly (imported as
`gsa`) instead of duplicating logic: `short_description`,
`specialist_frontmatter_description`, `CONTACTS_PHRASE`, `_md_table_cell`.

Wired at the pre-commit stage in .pre-commit-config.yaml (hook id
`macro-agents-generate`), BEFORE `agents-generate`. This script only reads
rayflow_file_map.json (never any generated specialist .md file) for its own
content, so it has no ordering dependency on agents-generate having already
run in this same commit — the two generators are independent of each other,
same as claude-md-generate/agents-generate already are.

Usage: python3 scripts/generate_macro_agents.py
(no args; regenerates every macrosistema's agent unconditionally, but only
rewrites/stages files whose content actually changed.)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_specialist_agents as gsa  # noqa: E402

FILE_MAP_PATH = REPO_ROOT / "rayflow_file_map.json"
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"

BANNER = """<!--
  ARCHIVO GENERADO — no editar a mano, se sobreescribe en cada commit.
  Fuente: rayflow_file_map.json (campo `macrosistemas` de cada sistema).
  Regenerado por scripts/generate_macro_agents.py, wireado como hook
  `macro-agents-generate` en .pre-commit-config.yaml (stage pre-commit,
  antes de `agents-generate`). Ver rayflow_agents_system.md.
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


def _group_systems_by_macro(file_map: dict) -> dict[str, list[str]]:
    """Groups system names by their `macrosistemas` field. Many-to-many, not
    a partition: a system can list more than one macro (e.g. `packaging` is
    in both `interfaces` and `frontend`)."""
    groups: dict[str, list[str]] = {}
    for system, info in file_map.get("systems", {}).items():
        for macro in info.get("macrosistemas", []):
            groups.setdefault(macro, []).append(system)
    return {macro: sorted(systems) for macro, systems in sorted(groups.items())}


def _systems_section(systems: list[str], file_map: dict) -> str:
    lines = ["| sistema | descripción |", "|---|---|"]
    for system in systems:
        desc = gsa._md_table_cell(file_map["systems"][system].get("description", ""))
        lines.append(f"| `{system}` | {desc} |")
    return "\n".join(lines) + "\n"


def macro_frontmatter_description(macro: str, systems: list[str]) -> str:
    """Builds the frontmatter `description:` for a rayflow-macro-<macro>
    agent — factored out (not just inlined in generate_one) so it can be
    reused verbatim when a SIBLING macro-agent lists this one in its own
    "## Contactos" section, the same way
    gsa.specialist_frontmatter_description is reused for specialists."""
    joined = ", ".join(f"`{s}`" for s in systems)
    return (
        f"Macro-agente del macrosistema `{macro}` de rayflow, que agrupa los "
        f"sistemas {joined}. Delega en el rayflow-<sistema>-specialist "
        f"correspondiente para trabajo concreto en uno de ellos, o en otro "
        f"macro-agente si la tarea cae fuera de este macrosistema; usar para "
        f"preguntas/tareas que abarcan varios sistemas de este macrosistema o "
        f"que todavía no tienen un sistema puntual asignado dentro de él."
    )


def _contacts_section(macro: str, systems: list[str], groups: dict[str, list[str]], file_map: dict) -> str:
    lines = ["| agente | descripción |", "|---|---|"]
    for system in systems:
        desc = gsa._md_table_cell(
            gsa.specialist_frontmatter_description(system, file_map["systems"][system].get("description", ""))
        )
        lines.append(f"| `rayflow-{system}-specialist` | {desc} |")
    for other_macro, other_systems in groups.items():
        if other_macro == macro:
            continue
        desc = gsa._md_table_cell(macro_frontmatter_description(other_macro, other_systems))
        lines.append(f"| `rayflow-macro-{other_macro}` | {desc} |")
    lines.append("")
    lines.append(gsa.CONTACTS_PHRASE)
    return "\n".join(lines) + "\n"


def generate_one(macro: str, systems: list[str], groups: dict[str, list[str]], file_map: dict) -> str:
    frontmatter_desc = macro_frontmatter_description(macro, systems)

    parts = [
        "---",
        f"name: rayflow-macro-{macro}",
        # Same reasoning as generate_specialist_agents.py: json.dumps()
        # produces a valid YAML double-quoted scalar, needed because this
        # description routinely contains ":" from system descriptions.
        f"description: {json.dumps(frontmatter_desc, ensure_ascii=False)}",
        "tools: Agent, SendMessage",
        "model: inherit",
        "---",
        "",
        BANNER,
        f"# Macro-agente: `{macro}`",
        "",
        frontmatter_desc,
        "",
        "## Sistemas de este macrosistema (`rayflow_file_map.json` → "
        f"sistemas cuyo campo `macrosistemas` incluye `{macro}`)",
        "",
        _systems_section(systems, file_map),
        "## Contactos",
        "",
        _contacts_section(macro, systems, groups, file_map),
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
    groups = _group_systems_by_macro(file_map)

    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    changed = []
    for macro, systems in groups.items():
        target = AGENTS_DIR / f"rayflow-macro-{macro}.md"
        new_content = generate_one(macro, systems, groups, file_map)
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
            f"[macro-agents-generate] Regenerated and staged {len(changed)} "
            f"macro agent(s): {', '.join(p.name for p in changed)}.\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
