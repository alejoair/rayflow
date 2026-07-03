---
name: rayflow-frontend-build-specialist
description: "Especialista en el sistema `frontend-build` de rayflow. Frontend build/tooling config: Vite, TypeScript project references, ESLint, npm package manifest — governs how src/ compiles into rayflow/editor/static/dist/. Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
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

# Especialista: sistema `frontend-build`

Frontend build/tooling config: Vite, TypeScript project references, ESLint, npm package manifest — governs how src/ compiles into rayflow/editor/static/dist/.

## Archivos (`rayflow_file_map.json` → `systems.frontend-build.files`)

| archivo | descripción |
|---|---|
| `rayflow/editor/frontend/.gitignore` | Standard Git ignore for Node.js projects, excludes build artifacts, node_modules, and editor temp files. |
| `rayflow/editor/frontend/README.md` | Project documentation describing the React + TypeScript + Vite template setup and ESLint configuration guidance. |
| `rayflow/editor/frontend/components.json` | shadcn/ui configuration file specifying component paths, aliases, and Tailwind CSS settings. |
| `rayflow/editor/frontend/eslint.config.js` | ESLint configuration enforcing TypeScript, React best practices, and React hooks linting rules. |
| `rayflow/editor/frontend/package-lock.json` | Generated npm lockfile pinning exact frontend dependency versions; not hand-edited. |
| `rayflow/editor/frontend/package.json` | Dependency manifest with React, xyflow, shadcn/ui, CodeMirror, Tailwind CSS, and build/lint scripts. |
| `rayflow/editor/frontend/tsconfig.app.json` | TypeScript compiler config for the application source code with path aliases and strict type checking. |
| `rayflow/editor/frontend/tsconfig.json` | Root TypeScript config referencing app and node build configs. |
| `rayflow/editor/frontend/tsconfig.node.json` | TypeScript config for build tools and Vite configuration files. |
| `rayflow/editor/frontend/vite.config.ts` | Vite build configuration with React plugin, path aliases, API proxying, and build output to ../static/dist. |

## Dependencias entre sistemas

Depende de: _(ningún otro sistema)_

Es dependencia de: _(ningún otro sistema)_

## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)

### Arquitectura general

- **arquitectura-general#diagrama-editor-visual-browser-fastapi-rayflow**: Diagrama: editor visual (browser) <-> FastAPI (rayflow/server.py) <-> Ray actors/tasks; editor/frontend/ (React+Vite) compila a editor/static/dist/, que es lo que sirve el server; el motor vive en rayflow/engine/executor.py. — evidencia: `rayflow/server.py`, `rayflow/engine/executor.py`, `rayflow/editor/frontend/vite.config.ts`
- **arquitectura-general#principio-diseno-1-nodo-clase-python**: Principio de diseño 1: un nodo = una clase Python decorada con @ray_node o @engine_node. — evidencia: `rayflow/server.py`, `rayflow/engine/executor.py`, `rayflow/editor/frontend/vite.config.ts`
- **arquitectura-general#principio-diseno-2-namespace-plano-flatten**: Principio de diseño 2: namespace plano — flatten() expande subflows inline en build time (ids tipo padre/sub/nodo). — evidencia: `rayflow/server.py`, `rayflow/engine/executor.py`, `rayflow/editor/frontend/vite.config.ts`
- **arquitectura-general#principio-diseno-3-ejecucion-secuencial-control**: Principio de diseño 3: ejecución secuencial de control, paralela de datos — exec pins secuenciales, data pins evaluados en paralelo vía Ray. — evidencia: `rayflow/server.py`, `rayflow/engine/executor.py`, `rayflow/editor/frontend/vite.config.ts`
- **arquitectura-general#principio-diseno-4-tipos-siempre-son**: Principio de diseño 4: los tipos siempre son strings canónicos ("int", "str", "list[str]"), nunca clases Python. — evidencia: `rayflow/server.py`, `rayflow/engine/executor.py`, `rayflow/editor/frontend/vite.config.ts`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `98b81d6`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
