---
name: rayflow-packaging-specialist
description: "Especialista en el sistema `packaging` de rayflow. Controls what actually ships: pyproject.toml package metadata/dependencies, MANIFEST.in inclusion/exclusion rules, and the built frontend bundle (rayflow/editor/static/dist/) that server.py serves. Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
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

# Especialista: sistema `packaging`

Controls what actually ships: pyproject.toml package metadata/dependencies, MANIFEST.in inclusion/exclusion rules, and the built frontend bundle (rayflow/editor/static/dist/) that server.py serves.

## Archivos (`rayflow_file_map.json` → `systems.packaging.files`)

| archivo | descripción |
|---|---|
| `MANIFEST.in` | setuptools sdist manifest: excludes CLAUDE.md (a generated file, see docs/claude_md_generation.md) and its hand-maintained source rayflow_system_prompt.md, docs/, and the five generated LLM-orientation JSONs (rayflow_file_map.json, rayflow_workflows.json, rayflow_scenarios.json, RAYFLOW_SOURCE_OF_TRUTH.json, rayflow_issues.json) from the published PyPI package — all internal tooling artifacts, not user docs. |
| `pyproject.toml` | Python package metadata: dependencies, build system, author/license info, pytest config, and package-data inclusion rules. |
| `rayflow/editor/static/dist/assets/index-CvkE1x42.css` | Generated build artifact (hashed bundle output of `npm run build`); not hand-edited. |
| `rayflow/editor/static/dist/assets/index-DtPeFQWl.js` | Generated build artifact (hashed bundle output of `npm run build`); not hand-edited. |
| `rayflow/editor/static/dist/favicon.svg` | Generated build asset, copied from the frontend's public/ directory. |
| `rayflow/editor/static/dist/icons.svg` | Generated build asset, copied from the frontend's public/ directory. |
| `rayflow/editor/static/dist/index.html` | Generated production build output of the editor frontend (run `npm run build`); not meant to be edited by hand. |

## Dependencias entre sistemas

Depende de: _(ningún otro sistema)_

Es dependencia de: _(ningún otro sistema)_

## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)

### Comandos de desarrollo

- **comandos-de-desarrollo#pip-install-e-instala-paquete-modo**: `pip install -e .` instala el paquete en modo editable. — evidencia: `pyproject.toml`, `rayflow/cli/main.py`, `rayflow/server.py`, `.claude/hooks/ty_diff_pre.py`, `.claude/hooks/ty_diff_post.py`, `.claude/hooks/_ty_check.py`
- **comandos-de-desarrollo#rayflow-serve-port-8000-python-m**: `rayflow serve --port 8000` (o `python -m rayflow serve --port 8000`) lanza el servidor. — evidencia: `pyproject.toml`, `rayflow/cli/main.py`, `rayflow/server.py`, `.claude/hooks/ty_diff_pre.py`, `.claude/hooks/ty_diff_post.py`, `.claude/hooks/_ty_check.py`
- **comandos-de-desarrollo#rayflow-serve-file-flows-suma-json**: `rayflow serve --file flows/suma.json --port 8000` precarga un flow. — evidencia: `pyproject.toml`, `rayflow/cli/main.py`, `rayflow/server.py`, `.claude/hooks/ty_diff_pre.py`, `.claude/hooks/ty_diff_post.py`, `.claude/hooks/_ty_check.py`
- **comandos-de-desarrollo#rayflow-serve-port-8000-debug-redirige**: `rayflow serve --port 8000 --debug` redirige logs de actores Ray (incluidos prints) a consola. — evidencia: `pyproject.toml`, `rayflow/cli/main.py`, `rayflow/server.py`, `.claude/hooks/ty_diff_pre.py`, `.claude/hooks/ty_diff_post.py`, `.claude/hooks/_ty_check.py`
- **comandos-de-desarrollo#tests-pip-install-e-dev-pytest**: Tests: `pip install -e ".[dev]"` + `pytest tests/`. — evidencia: `pyproject.toml`, `rayflow/cli/main.py`, `rayflow/server.py`, `.claude/hooks/ty_diff_pre.py`, `.claude/hooks/ty_diff_post.py`, `.claude/hooks/_ty_check.py`
- **comandos-de-desarrollo#type-check-ty-check-rayflow-astral**: Type-check: `ty check rayflow/` (Astral, ~0.3s para todo rayflow/). — evidencia: `pyproject.toml`, `rayflow/cli/main.py`, `rayflow/server.py`, `.claude/hooks/ty_diff_pre.py`, `.claude/hooks/ty_diff_post.py`, `.claude/hooks/_ty_check.py`
- **comandos-de-desarrollo#ty-produce-falsos-positivos-conocidos-archivos**: `ty` produce falsos positivos conocidos en archivos con actores Ray (`@ray.remote` inyecta `.remote()` en runtime, invisible al analizador estático) — se consideran ruido esperado, no bugs reales. — evidencia: `pyproject.toml`, `rayflow/cli/main.py`, `rayflow/server.py`, `.claude/hooks/ty_diff_pre.py`, `.claude/hooks/ty_diff_post.py`, `.claude/hooks/_ty_check.py`
- **comandos-de-desarrollo#hooks-ty-diff-pre-py-ty**: Los hooks `ty_diff_pre.py`/`ty_diff_post.py` en `.claude/hooks/` filtran ese ruido automáticamente comparando diagnósticos antes/después de cada edit. — evidencia: `pyproject.toml`, `rayflow/cli/main.py`, `rayflow/server.py`, `.claude/hooks/ty_diff_pre.py`, `.claude/hooks/ty_diff_post.py`, `.claude/hooks/_ty_check.py`
- **comandos-de-desarrollo#servidor-sirve-editor-visual-editor-api**: El servidor sirve: editor visual en /editor, API REST en /flows, health check en /health. — evidencia: `pyproject.toml`, `rayflow/cli/main.py`, `rayflow/server.py`, `.claude/hooks/ty_diff_pre.py`, `.claude/hooks/ty_diff_post.py`, `.claude/hooks/_ty_check.py`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `ed47003`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
