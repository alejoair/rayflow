---
name: rayflow-docs-specialist
description: "Especialista en el sistema `docs` de rayflow. Long-form prose: README, CLAUDE.md (this repo's own agent-facing architecture guide), design-decision docs, and licensing/contribution documents (LICENSE, CLA.md, COMMERCIAL-LICENSE.md, CONTRIBUTING.md). Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
tools: Read, Grep, Glob, Edit, Agent, SendMessage
model: inherit
---

<!--
  ARCHIVO GENERADO — no editar a mano, se sobreescribe en cada commit.
  Fuente: rayflow_file_map.json (archivos, descripciones, dependencias entre
  sistemas) + RAYFLOW_SOURCE_OF_TRUTH.json (claims cuya evidencia cae en
  este sistema) + rayflow_issues.json (issues abiertos que lo mencionan).
  Regenerado por scripts/generate_specialist_agents.py, wireado como hook
  `agents-generate` en .pre-commit-config.yaml (stage pre-commit). Ver
  rayflow_agents_system.md.
-->

# Especialista: sistema `docs`

Long-form prose: README, CLAUDE.md (this repo's own agent-facing architecture guide), design-decision docs, and licensing/contribution documents (LICENSE, CLA.md, COMMERCIAL-LICENSE.md, CONTRIBUTING.md).

## Archivos (`rayflow_file_map.json` → `systems.docs.files`)

| archivo | descripción |
|---|---|
| `.gitignore` | Patterns for files/directories git should not track (build artifacts, virtualenvs, caches, etc.). |
| `CLA.md` | Contributor License Agreement: contributors keep copyright but grant the maintainer the right to relicense their contributions, including commercially. |
| `CLAUDE.md` | GENERATED FILE (scripts/generate_claude_md.py, pre-commit hook `claude-md-generate`, re-staged automatically on every commit if changed — never edit by hand, edits are silently overwritten at the next commit). Banner + rayflow_system_prompt.md verbatim + an index of RAYFLOW_SOURCE_OF_TRUTH.json's sections (heading + claim count + pointer, not the claim text) + an index of rayflow_file_map.json's systems. See docs/claude_md_generation.md for the full design. |
| `COMMERCIAL-LICENSE.md` | Explains Rayflow's dual-license model (AGPL-3.0-or-later free for non-commercial use; a separate commercial license is required otherwise) and how to obtain one. |
| `CONTRIBUTING.md` | Contributor guide: dev setup, how the CLA bot signing flow works, PR guidelines. |
| `LICENSE` | Full text of the GNU Affero General Public License v3.0, Rayflow's open-source license. |
| `RAYFLOW_SOURCE_OF_TRUTH.json` | Structured, section-organized claims about the rayflow codebase (schema_version 2), extracted from rayflow_system_prompt.md (its source_file) — each claim an object {id, text, evidence, docs}. id is '<section_id>#<slug>', stable and referenced by rayflow_issues.json's claim_ids. evidence is a best-effort array of repo-relative code paths (optionally '#symbol') supporting the claim. docs is a best-effort array of OTHER documentation files (README.md, a SKILL.md, guide.py, ...) that independently restate the same fact — CLAUDE.md and rayflow_system_prompt.md are both deliberately excluded from every claim's docs: CLAUDE.md because it's a generated mechanical re-render (scripts/generate_claude_md.py), rayflow_system_prompt.md because it's the source the claims were extracted FROM, not an independent restatement. Both evidence and docs empty mean 'not yet located', not 'false'. No known_issues array anymore (migrated to rayflow_issues.json) and no per-claim verification timestamps (would churn every audit run). Not auto-derived or hook-consumed by itself — read by scripts/generate_claude_md.py (index only, not full dump), read/written by the audit agent (.claude/agents/rayflow-auditor.md), and by hand. |
| `README.md` | Project overview, installation, quickstart, and license summary shown on GitHub and PyPI. |
| `docs/analisis-conceptual.md` | Long-form conceptual analysis (in Spanish) of Rayflow's execution model: the two superimposed planes (control/exec and data) and the core mental model behind the engine. |
| `docs/claude_md_generation.md` | Design doc (in Spanish, self-contained) for the CLAUDE.md generation mechanism: why CLAUDE.md became a generated file (banner + rayflow_system_prompt.md verbatim + SOT/file-map indices), why it stays git-tracked rather than gitignored (avoids a fresh-clone bootstrap problem entirely), why no edit-blocking was needed (unlike the SOT — CLAUDE.md just gets silently overwritten on the next commit, so blocking would be redundant), and the scripts/generate_claude_md.py mechanism wired as the `claude-md-generate` pre-commit hook. |
| `docs/frontend.md` | Quick-reference (in Spanish) inventory of the editor frontend's tech stack and component responsibilities. |
| `docs/issues_system.md` | Design doc (in Spanish, self-contained) for a documentation-audit system. RAYFLOW_SOURCE_OF_TRUTH.json (v2, implemented: claims as {id, text, evidence, docs} — evidence links code, docs links OTHER documentation that duplicates the fact, CLAUDE.md deliberately excluded since it's slated to become a generated rendering of the SOT) and rayflow_issues.json (v1, implemented: open-issues-only queue, no resolved history in-file — git log is the log) linked by stable ids. The audit agent (.claude/agents/rayflow-auditor.md) is implemented and confirmed working end-to-end via `claude -p --agent rayflow-auditor` (§6.1). SOT direct-edit blocking is two layers: .claude/hooks/sot_guard.py (PreToolUse, session-scoped, bypassable) and scripts/check_sot_commit_message.py (pre-commit commit-msg stage, Sot-Change trailer, no bypass — §6.3). The pre-commit wiring for the auditor itself is also implemented: scripts/run_sot_audit.py (pre-commit stage, id sot-audit) scopes the staged diff via _sot_scope.py (exits free if nothing in scope), runs the auditor, and blocks the commit (exit 1) only if it wrote to rayflow_issues.json — fails open on infra problems (claude missing, timeout), never on the LLM simply finding nothing (§6.2). Explains why these stay separate files rather than merging with rayflow_file_map.json. |
| `docs/propuesta-runcontext.md` | Design proposal (in Spanish) that motivated reifying a flow execution as a `RunContext` object to isolate concurrent runs. |
| `docs/rayflow.md` | Historical v1 design document (in Spanish, explicitly marked obsolete) describing the original workflow-orchestration model, kept as an intent record. |
| `rayflow_agents_system.md` | Design doc (in Spanish, self-contained) for programmatically generated per-system specialist subagents in .claude/agents/. IMPLEMENTED: scripts/generate_specialist_agents.py (pre-commit hook `agents-generate`) produces one rayflow-<system>-specialist.md per system in rayflow_file_map.json.systems (21, no curation), WITH embedded content (file descriptions, inter-system deps, relevant SOT claims text+evidence, open issues) — reversing the doc's original §2/§3 recommendation against embedding, since regenerating on every commit (same mechanism as CLAUDE.md, docs/claude_md_generation.md) removes the staleness risk that motivated it. Distinguishes this repo-dev tooling (.claude/agents/) from the shipped rayflow-debugger.md product template (rayflow/claude_tools/agents/). Frames synchronous multi-agent 'meetings' as an explicitly deferred future direction (§8). Open: per-specialist tool-access levels (§9). |
| `rayflow_file_map.json` | Generated flat map of every tracked repo file to a short English description plus depends_on/dependents edges (computed from real imports). Not shipped in the PyPI package. Consumed by the .claude/hooks/*.py scripts to give Claude Code per-file context automatically. |
| `rayflow_issues.json` | Open-issues-only queue produced by comparing RAYFLOW_SOURCE_OF_TRUTH.json claims against the real repo state. Each issue links claim_ids (SOT), files (affected source), and docs (prose docs also out of date). No status/resolved_* fields and no suggested_fix (avoids biasing whoever picks it up) — 'resolving' an issue means deleting it from the array in the fixing commit; git history is the log, not this file. next_id is a monotonic counter, never reused even as the array shrinks. See docs/issues_system.md for the full design. |
| `rayflow_scenarios.json` | End-to-end scenario narratives describing how systems cooperate to accomplish something a user or LLM agent actually cares about (running a flow from the editor, an agent authoring via MCP, event-reactive flows, custom-node hot reload, CallFlow subflow splicing). Unlike depends_on_systems/dependents_systems, these can't be derived mechanically — they require an LLM to understand intent, and have no automated correctness check. |
| `rayflow_system_prompt.md` | Hand-maintained source of CLAUDE.md's prose. Deliberately high-level only: workflow conventions (test sandbox), dev commands, and the top-level architecture/design-principles mental map needed to route work to the right specialist — plus instructions for delegating per-system detail to the .claude/agents/rayflow-<system>-specialist subagents (spawn via Agent, then converse via SendMessage instead of re-reading files). Per-system detail (node system, engine internals, REST/MCP API tables, flow JSON schema, UI style rules) now lives only in those specialist agents, not here. CLAUDE.md itself is generated FROM this file — edit this one, not CLAUDE.md. See docs/claude_md_generation.md. |
| `rayflow_workflows.json` | Task-shaped checklists for recurring multi-file changes (adding a node type, changing the SSE event schema, adding an MCP tool, etc.), keyed by trigger phrases. Surfaced by workflow_hints.py when a user prompt matches, so the checklist arrives before the first edit rather than being discovered file-by-file. |
| `signatures/cla.json` | Generated file (written by the CLA Assistant GitHub Action) recording which external contributors have signed the CLA. |

## Dependencias entre sistemas

Depende de: _(ningún otro sistema)_

Es dependencia de: _(ningún otro sistema)_

## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)

_Ningún claim de RAYFLOW_SOURCE_OF_TRUTH.json tiene evidencia en archivos de este sistema todavía (evidencia vacía o no localizada, o el sistema no está cubierto por el SOT)._

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `ba34e98`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
