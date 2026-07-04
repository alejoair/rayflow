---
name: rayflow-frontend-build-specialist
description: "Especialista en el sistema `frontend-build` de rayflow. Frontend build/tooling config: Vite, TypeScript project references, ESLint, npm package manifest — governs how src/ compiles into rayflow/editor/static/dist/. Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
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

### Frontend (editor visual)

- **frontend-editor-visual#typescript-strict-no-habilitado**: Ni tsconfig.app.json ni tsconfig.node.json declaran "strict": true — el proyecto corre solo con linting parcial (noUnusedLocals, noUnusedParameters, erasableSyntaxOnly, noFallthroughCasesInSwitch), no con TypeScript strict mode; el propio README.md del frontend sugiere tseslint.configs.strictTypeChecked como alternativa 'más estricta', confirmando que no está activada por defecto. — evidencia: `rayflow/editor/frontend/tsconfig.app.json`, `rayflow/editor/frontend/tsconfig.node.json`
- **frontend-editor-visual#build-script-tsc-b-project-references-antes-de-vite**: package.json define "build": "tsc -b && vite build" — el type-check corre en modo build de project references antes de que Vite empaquete; un error de tipos hace fallar el build completo antes de invocar Vite. — evidencia: `rayflow/editor/frontend/package.json#scripts.build`
- **frontend-editor-visual#vite-proxy-dev-solo-4-rutas-editor**: vite.config.ts solo proxea 4 rutas específicas del servidor de desarrollo hacia http://127.0.0.1:8000 — /editor/nodes, /editor/flows, /editor/validate, /editor/type-check — no un catch-all de /editor/*; cualquier otra ruta de API del editor (custom-nodes, guía, load-flow) no está proxeada explícitamente. — evidencia: `rayflow/editor/frontend/vite.config.ts#server.proxy`
- **frontend-editor-visual#base-editor-alinea-con-mount-fastapi**: vite.config.ts fija base: '/editor/', lo que hace que las referencias a assets generadas en el build de producción usen ese prefijo — debe coincidir con el path bajo el cual server.py monta los archivos estáticos servidos desde rayflow/editor/static/dist/. — evidencia: `rayflow/editor/frontend/vite.config.ts#base`
- **frontend-editor-visual#versiones-bleeding-edge-vite8-react19-ts6**: package.json fija versiones bleeding-edge: vite ^8.0.12, react/react-dom ^19.2.6, typescript ~6.0.2 y eslint ^10.3.0 — todas majors recientes, no LTS conservadoras (relacionado con el issue ya existente sobre React 18 vs 19: información complementaria sobre el resto del stack). — evidencia: `rayflow/editor/frontend/package.json#dependencies`
- **frontend-editor-visual#eslint-flat-config-solo-ignora-dist**: eslint.config.js usa flat config con globalIgnores(['dist']) como única exclusión — no ignora node_modules explícitamente, ni excluye vite.config.ts del set de reglas de navegador, con tseslint.configs.recommended sin la variante typeChecked/strictTypeChecked que sí menciona el README como alternativa no adoptada. — evidencia: `rayflow/editor/frontend/eslint.config.js#globalIgnores`

### Frontend > Primitivas de UI (shadcn/ui adaptado)

- **frontend-ui-kit#tailwind-v4-esta-cableado-en-el-build-pese-a-regla-de-no-usarlo**: Tailwind v4 (@tailwindcss/vite + tailwindcss) está activamente cableado en vite.config.ts (plugin tailwindcss()) y se importa en src/index.css (@import "tailwindcss") — el build sigue procesando Tailwind pese a que reglas-de-ui documenta que 'no genera clases de forma fiable'. Complementa (no contradice) esa claim ya existente: dialog.tsx (única primitiva no migrada en uso real) compensa pasando className con utilidades Tailwind de valor entre corchetes (ej. "bg-[var(--card)]"), que sí se generan de forma fiable en build time, en vez de migrar la primitiva. — evidencia: `rayflow/editor/frontend/vite.config.ts`, `rayflow/editor/frontend/src/index.css`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

- **ISSUE-0002** (medium): El SOT afirma 'React 18' pero el frontend real corre React 19

---
_Generado desde el commit `c72b1ed`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
