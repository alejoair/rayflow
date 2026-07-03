---
name: rayflow-ci-specialist
description: "Especialista en el sistema `ci` de rayflow. GitHub Actions workflows: CLA enforcement, test suite, and PyPI publishing. Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
tools: Read, Grep, Glob, Edit
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

# Especialista: sistema `ci`

GitHub Actions workflows: CLA enforcement, test suite, and PyPI publishing.

## Archivos (`rayflow_file_map.json` → `systems.ci.files`)

| archivo | descripción |
|---|---|
| `.github/workflows/cla.yml` | CLA Assistant workflow: asks external contributors to sign the CLA before a PR can merge; skips the check entirely for PRs opened by the maintainer. |
| `.github/workflows/pypi.yaml` | CI workflow that builds and publishes the package to PyPI on release. |
| `.github/workflows/test.yml` | CI workflow that runs the pytest suite on pushes/PRs. |

## Dependencias entre sistemas

Depende de: _(ningún otro sistema)_

Es dependencia de: _(ningún otro sistema)_

## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)

_Ningún claim de RAYFLOW_SOURCE_OF_TRUTH.json tiene evidencia en archivos de este sistema todavía (evidencia vacía o no localizada, o el sistema no está cubierto por el SOT)._

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `a4bce82`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
