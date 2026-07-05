#!/usr/bin/env python3
"""pre-commit stage hook (wired via .pre-commit-config.yaml, id
`file-map-draft`): confirms-or-corrects the cheap, no-LLM candidate
description/system that scripts/generate_file_map.py (hook `file-map-generate`,
which must run first) stubs onto any file it has no prior map entry for --
never generates from scratch, always starts from that candidate and either
confirms it or corrects it, via a single batched `claude -p --agent
rayflow-router` call covering every currently-pending draft in
rayflow_file_map.json (see below for why "currently pending" rather than
strictly "new in this commit").

Same early-exit-if-nothing-to-do shape as scripts/run_sot_audit.py: if
rayflow_file_map.json has no file entry with a `_draft_candidate` key, exits
0 without ever invoking an LLM.

A resolved entry's `description` gets prefixed "[DRAFT sin revisar] " (never
a bare, un-marked string) and its `_draft_candidate` key is removed -- still
marked as LLM-authored-but-not-yet-human-reviewed, just one step further
along than the "[SIN VERIFICAR]" no-LLM stub. No new JSON schema field for
the final result: existing consumers (.claude/hooks/_file_map.py,
scripts/generate_specialist_agents.py) keep working unmodified, since
`description`/`system` are always plain strings either way.

Note on scope: this hook does not itself compute "which files are new in
this commit" via git -- it simply looks at whatever rayflow_file_map.json
currently has a `_draft_candidate` for. In the normal case that's exactly
"the files file-map-generate just stubbed a moment ago in this same
pre-commit run" (nothing else could have put a `_draft_candidate` there). It
also means a draft that failed to resolve on a previous commit (claude
unavailable, timeout, bad response) is automatically retried here rather
than staying stuck forever -- a deliberate, more robust superset of "just
this commit's new files".

Fails OPEN (exit 0), same rationale/pattern as scripts/run_sot_audit.py: if
`claude` isn't on PATH, times out, or returns something unparsable, every
pending draft is simply left as-is (still usable -- the cheap candidate is
already a real, if unverified, string) and a stderr warning is printed.
Never blocks the commit.

Usage: python3 scripts/draft_file_map_entries.py
(no args; always operates on the whole repo from REPO_ROOT.)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FILE_MAP_PATH = REPO_ROOT / "rayflow_file_map.json"
DRAFT_TIMEOUT_S = 300


def _load_map() -> dict:
    return json.loads(FILE_MAP_PATH.read_text(encoding="utf-8"))


def _pending_drafts(file_map: dict) -> dict[str, dict]:
    return {
        path: entry["_draft_candidate"]
        for path, entry in file_map.get("files", {}).items()
        if "_draft_candidate" in entry
    }


def build_prompt(pending: dict[str, dict], known_systems: list[str]) -> str:
    items = []
    for path, candidate in sorted(pending.items()):
        items.append({
            "path": path,
            "description_candidate": candidate.get("description", ""),
            "system_candidate": candidate.get("system"),
            "system_confidence": candidate.get("system_confidence", "no_precedent"),
        })
    return (
        "Estos archivos son NUEVOS en rayflow_file_map.json y tienen un "
        "candidato barato calculado sin LLM (heuristica, no una generacion "
        "tuya desde cero). Tu tarea es VERIFICAR/CORREGIR cada uno, no "
        "inventar: lee el archivo real (path relativo al repo) y confirma o "
        "corrige su description_candidate (una frase objetiva sobre que "
        "hace el archivo, no la marques vos con ningun prefijo -- eso lo "
        "agrega el script que te invoca) y su system_candidate "
        "(system_confidence te dice si hubo precedente unanime, dividido, o "
        "ninguno entre los archivos hermanos del mismo directorio -- usalo "
        "de guia, no como verdad absoluta). El campo `system` de tu "
        "respuesta DEBE ser exactamente uno de estos nombres existentes: "
        f"{json.dumps(known_systems)}, o el string \"UNASSIGNED\" si "
        "ninguno encaja de verdad -- nunca inventes un sistema nuevo, eso "
        "es taxonomia y queda fuera de tu alcance aca.\n\n"
        f"Archivos a verificar:\n{json.dumps(items, indent=2, ensure_ascii=False)}\n\n"
        "Responde UNICAMENTE con un array JSON (nada de texto antes/"
        "despues), un objeto por archivo, con exactamente estas claves: "
        '[{"path": "...", "description": "...", "system": "..."}, ...]'
    )


_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _parse_response(stdout: str) -> list[dict] | None:
    m = _JSON_ARRAY_RE.search(stdout)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(data, list):
        return None
    return data


def main() -> int:
    try:
        file_map = _load_map()
    except Exception as exc:
        sys.stderr.write(f"[file-map-draft] couldn't read {FILE_MAP_PATH.name} ({exc!r}) -- skipping.\n")
        return 0

    pending = _pending_drafts(file_map)
    if not pending:
        return 0

    known_systems = sorted(file_map.get("systems", {}).keys())
    prompt = build_prompt(pending, known_systems)

    try:
        result = subprocess.run(
            ["claude", "-p", "--agent", "rayflow-router", prompt],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=DRAFT_TIMEOUT_S,
        )
    except FileNotFoundError:
        sys.stderr.write(
            f"\n[file-map-draft] `claude` binary not found on PATH -- leaving "
            f"{len(pending)} draft(s) as unverified stubs. Not blocking the "
            "commit on this (infra problem, not a content problem).\n"
        )
        return 0
    except subprocess.TimeoutExpired:
        sys.stderr.write(
            f"\n[file-map-draft] rayflow-router timed out after "
            f"{DRAFT_TIMEOUT_S}s verifying {len(pending)} draft(s) -- "
            "leaving them as unverified stubs, not blocking the commit.\n"
        )
        return 0

    items = _parse_response(result.stdout)
    if items is None:
        sys.stderr.write(
            f"\n[file-map-draft] couldn't parse rayflow-router's response as "
            f"JSON -- leaving {len(pending)} draft(s) as unverified stubs. "
            f"Raw stdout below:\n{result.stdout}\n"
        )
        return 0

    resolved = 0
    for item in items:
        path = item.get("path")
        if path not in pending:
            continue
        entry = file_map["files"][path]
        description = str(item.get("description") or entry["_draft_candidate"].get("description", "")).strip()
        system = item.get("system")
        if system not in file_map.get("systems", {}) and system != "UNASSIGNED":
            system = "UNASSIGNED"
        entry["description"] = f"[DRAFT sin revisar] {description}"
        entry["system"] = system
        del entry["_draft_candidate"]
        resolved += 1

    if resolved == 0:
        sys.stderr.write(
            f"\n[file-map-draft] rayflow-router responded but resolved none "
            f"of the {len(pending)} pending draft(s) -- leaving them as "
            f"unverified stubs.\n"
        )
        return 0

    FILE_MAP_PATH.write_text(json.dumps(file_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", str(FILE_MAP_PATH)], cwd=REPO_ROOT, check=False)
    still_pending = len(pending) - resolved
    sys.stderr.write(
        f"[file-map-draft] Resolved {resolved}/{len(pending)} draft(s) via "
        f"rayflow-router" + (f" ({still_pending} still pending)" if still_pending else "") + ".\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
