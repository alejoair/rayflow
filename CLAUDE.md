<!--
  ARCHIVO GENERADO — no editar a mano, se sobreescribe en cada commit.
  Fuente: rayflow_system_prompt.md (prosa) + RAYFLOW_SOURCE_OF_TRUTH.json +
  rayflow_file_map.json (índices, más abajo). Regenerado por
  scripts/generate_claude_md.py, wireado como hook `claude-md-generate` en
  .pre-commit-config.yaml (stage pre-commit). Ver docs/claude_md_generation.md.
-->

# CLAUDE.md

> `rayflow_system_prompt.md` — fuente hand-maintained de `CLAUDE.md`.
> `CLAUDE.md` en sí es un archivo **generado**
> (`scripts/generate_claude_md.py`) que envuelve este contenido verbatim más
> un índice de `RAYFLOW_SOURCE_OF_TRUTH.json` y `rayflow_file_map.json`, y se
> regenera y sobreescribe automáticamente en cada commit (hook
> `claude-md-generate` en `.pre-commit-config.yaml`) — así que editar
> `CLAUDE.md` directamente no sirve de nada a partir del próximo commit.
> Editá este archivo en su lugar. Ver `docs/claude_md_generation.md` para el
> diseño completo.

Guía para Claude Code (o cualquier agente LLM) al trabajar en este repositorio.

Este documento se mantiene deliberadamente corto: solo cubre lo que ningún
subagente especializado posee por sí solo (convenciones de workflow, comandos
de desarrollo, y el mapa mental de alto nivel para decidir a quién delegar).
El detalle de cada sistema — arquitectura interna, contratos, API, convenciones
específicas — vive en los subagentes `.claude/agents/rayflow-<sistema>-specialist.md`,
uno por sistema listado en el "Índice de sistemas" al final de este documento
(regenerado automáticamente en cada commit desde `rayflow_file_map.json` +
`RAYFLOW_SOURCE_OF_TRUTH.json` + `rayflow_issues.json`). Ver "Trabajar con los
especialistas" más abajo.

## Carpeta de pruebas

Los flows y nodos custom de prueba viven en un directorio de sandbox **fuera del
repo** (configúralo en tu máquina, p.ej. `~/rayflow_sandbox/`):
- `flows/` — flows JSON de prueba (no en el repo de Rayflow)
- `custom_nodes/` — nodos custom de prueba del usuario

Al lanzar el servidor desde el sandbox, Ray y el editor los detectan automáticamente:
```bash
cd <tu-directorio-sandbox>
rayflow serve --port 8000
```

## Comandos de desarrollo

```bash
# Instalar en modo editable
pip install -e .

# Lanzar el servidor (editor visual + API REST)
rayflow serve --port 8000
# o equivalentemente:
python -m rayflow serve --port 8000

# Con flows precargados
rayflow serve --file flows/suma.json --port 8000

# Con logs de actores Ray (prints incluidos) redirigidos a consola
rayflow serve --port 8000 --debug

# Ejecutar tests
pip install -e ".[dev]"
pytest tests/

# Type-check el backend (ty, de Astral — muy rápido, ~0.3s para todo rayflow/)
ty check rayflow/

# Activar los git hooks de pre-commit (una sola vez por clon; ver .pre-commit-config.yaml)
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

`ty` marca falsos positivos conocidos en archivos con actores Ray (`@ray.remote`
inyecta `.remote()` en tiempo de ejecución, invisible para el analizador estático) —
son ruido esperado, no bugs reales. Los hooks `ty_diff_pre.py`/`ty_diff_post.py`
en `.claude/hooks/` ya filtran ese ruido automáticamente comparando diagnósticos
antes/después de cada edit; correr `ty check` a mano es útil para una revisión
manual amplia del estado actual de tipos.

El servidor sirve:
- Editor visual en `http://localhost:8000/editor`
- API REST en `http://localhost:8000/flows`
- Health check en `http://localhost:8000/health`

## Arquitectura general

```
Editor visual (browser) ←→ FastAPI (rayflow/server.py) ←→ Ray actors/tasks
         ↓                           ↓
  editor/frontend/ (React+Vite)   rayflow/engine/executor.py
   → build a editor/static/dist/  (lo que sirve el server)
```

### Principios de diseño

1. **Un nodo = una clase Python** decorada con `@ray_node` o `@engine_node`
2. **Namespace plano**: `flatten()` expande subflows inline en build time (ids tipo `padre/sub/nodo`)
3. **Ejecución secuencial de control, paralela de datos**: exec pins son secuenciales; data pins se evalúan en paralelo vía Ray
4. **Tipos siempre strings canónicos**: `"int"`, `"str"`, `"list[str]"` — nunca clases Python

## Trabajar con los especialistas de cada sistema

Cada sistema del repo (ver "Índice de sistemas" al final de este documento, o
`rayflow_file_map.json` directamente) tiene un subagente
`rayflow-<sistema>-specialist` regenerado en cada commit con el detalle real
de ese sistema: descripciones de archivos, dependencias entre sistemas, las
claims de `RAYFLOW_SOURCE_OF_TRUTH.json` cuya evidencia cae ahí, e issues
abiertos que lo mencionan.

- **Para trabajo o preguntas acotadas a un sistema, delegá con la tool Agent**
  (`subagent_type: rayflow-<sistema>-specialist`) en lugar de leer los
  archivos del sistema vos mismo — el especialista ya tiene el contexto
  cargado y curado.
- **Para conversar con un especialista ya spawneado — preguntas de
  seguimiento, aclaraciones, "¿y si...?"** — no vuelvas a spawnearlo con
  Agent (un Agent nuevo arranca sin memoria de la conversación previa).
  Usá **SendMessage** dirigido al nombre/id del agente ya activo: retoma la
  misma sesión con todo su contexto, así que puede responder directo sin
  releer archivos. Preferí este camino sobre investigar vos mismo cuando ya
  hay un especialista de ese sistema conversando en la sesión.


## Índice de `RAYFLOW_SOURCE_OF_TRUTH.json`

Cada sección abajo corresponde a un heading de este documento y tiene sus afirmaciones registradas como claims verificables en `RAYFLOW_SOURCE_OF_TRUTH.json` — leé ese archivo, filtrando por `section_id`, para el detalle de cada claim (texto + evidencia en código + docs relacionados). No se listan acá para no duplicar la prosa de arriba ni hacer que este archivo crezca con cada claim nuevo.

| section_id | heading | claims |
|---|---|---|
| `carpeta-de-pruebas` | Carpeta de pruebas | 2 |
| `comandos-de-desarrollo` | Comandos de desarrollo | 9 |
| `arquitectura-general` | Arquitectura general | 5 |
| `frontend-editor-visual` | Frontend (editor visual) | 40 |
| `sistema-de-nodos-decoradores` | Sistema de nodos > Decoradores | 11 |
| `sistema-de-nodos-entrada` | Sistema de nodos > Nodos de entrada (@entry_node) | 18 |
| `sistema-de-nodos-estado` | Sistema de nodos > Estado en nodos | 6 |
| `sistema-de-nodos-ctx-fire` | Sistema de nodos > Cómo funciona ctx.fire() internamente | 2 |
| `sistema-de-nodos-pending-outputs` | Sistema de nodos > Buffer _pending_outputs en engine_nodes | 4 |
| `sistema-de-nodos-runqueue-sse` | Sistema de nodos > RunQueue y eventos de ejecución (SSE) | 23 |
| `sistema-de-nodos-descubrimiento` | Sistema de nodos > Descubrimiento de nodos | 3 |
| `api-rest-flows` | API REST del editor > Flows (rayflow/editor/routes.py) | 28 |
| `api-rest-custom-nodes` | API REST del editor > Nodos custom (rayflow/editor/custom_nodes_routes.py) | 8 |
| `capa-mcp` | Capa MCP (para agentes LLM) | 28 |
| `schema-de-un-flow` | Schema de un flow (JSON) | 17 |
| `reglas-de-ui` | Reglas de UI (frontend Vite) | 9 |
| `ciclo-de-vida-de-un-flow` | Ciclo de vida de un flow en Ray | 14 |
| `sistema-de-eventos` | Sistema de eventos | 12 |
| `triggers-por-cambio-de-variable` | Sistema de eventos > Triggers por cambio de variable (OnVariableChange) | 8 |
| `archivos-clave-del-backend` | Archivos clave del backend | 15 |
| `sistema-de-nodos-pin-descriptors` | Sistema de nodos > Pin descriptors (Input/Output/ExecInput/ExecOutput) | 2 |
| `sistema-de-nodos-catalogo-builtin` | Sistema de nodos > Catálogo builtin | 4 |
| `schema-sistema-de-tipos` | Schema > Sistema de tipos (rayflow/types.py) | 4 |
| `sistema-build` | Sistema de build (validación y BuiltFlow) | 4 |
| `sistema-engine` | Sistema de engine (ejecución interna del FlowEngine) | 9 |
| `sistema-state` | Sistema de state (GraphState) | 3 |
| `sistema-server` | Sistema server (rayflow/server.py, rayflow.api) | 3 |
| `sistema-cli` | Sistema CLI (rayflow/cli, claude_tools) | 5 |
| `frontend-state` | Frontend > Estado y acceso a datos del cliente | 8 |
| `frontend-panels` | Frontend > Paneles del editor (sidebars y footer) | 7 |
| `frontend-ui-kit` | Frontend > Primitivas de UI (shadcn/ui adaptado) | 5 |
| `sistema-packaging` | Sistema de packaging | 6 |
| `sistema-ci` | Sistema de CI | 7 |
| `sistema-tests` | Sistema de tests | 14 |
| `sistema-docs-licenciamiento` | Docs > Licenciamiento (CLA, LICENSE, licencia comercial) | 9 |
| `sistema-docs-repo-meta` | Docs > Meta del repo (.gitignore y similares) | 2 |
| `meta-generacion-claude-md` | Docs > Generación de CLAUDE.md | 4 |
| `sistema-docs-auditoria` | Docs > Sistema de auditoría e issues | 3 |
| `sistema-docs-runcontext` | Docs > Propuesta RunContext (staleness) | 2 |
| `sistema-docs-agentes-especialistas` | Docs > Sistema de agentes especialistas | 3 |
| `sistema-docs-analisis-conceptual` | Docs > Análisis conceptual y docs históricas | 2 |
| `sistema-docs-readme` | Docs > README | 1 |
| `sistema-hooks-infra` | Sistema de hooks-infra | 15 |


## Índice de sistemas (`rayflow_file_map.json`)

Agrupación de los archivos del repo en sistemas, con su descripción y cantidad de archivos — el detalle completo (lista de archivos, `depends_on`/`dependents`) vive en `rayflow_file_map.json`.

| sistema | archivos | descripción |
|---|---|---|
| `build` | 2 | Validates a parsed FlowDef against the node catalog and produces an executable BuiltFlow: flattens CallFlow subflows into one namespace, checks type/wiring/cycle correctness, and either raises on first error or collects every error in one pass for editor/MCP clients. |
| `ci` | 3 | GitHub Actions workflows: CLA enforcement, test suite, and PyPI publishing. |
| `cli` | 7 | The `rayflow` command-line entry point (serve, and future subcommands) built on top of rayflow.api and rayflow.server. |
| `docs` | 21 | Long-form prose: README, CLAUDE.md (this repo's own agent-facing architecture guide), design-decision docs, and licensing/contribution documents (LICENSE, CLA.md, COMMERCIAL-LICENSE.md, CONTRIBUTING.md). |
| `editor-api` | 5 | The REST surface for the visual editor: flow CRUD, validation, catalog resolution, custom-node CRUD with hot reload, and the curated markdown guide served to LLM agents. |
| `engine` | 2 | The FlowEngine Ray actor and LoadedFlow lifecycle: executes a BuiltFlow node-by-node (sequential exec pins, parallel data pins), manages per-run scratch state (RunContext), and is the runtime core every other backend system ultimately drives. |
| `events` | 2 | The EventBroker pub/sub bus: fire-and-forget publish/subscribe connecting EmitEvent nodes, OnEvent/OnVariableChange entry points, and cross-flow event-triggered execution. |
| `frontend-app` | 10 | App shell: root component, entry point, global styles, static assets, and the HTML page the editor mounts into. |
| `frontend-build` | 10 | Frontend build/tooling config: Vite, TypeScript project references, ESLint, npm package manifest — governs how src/ compiles into rayflow/editor/static/dist/. |
| `frontend-canvas` | 4 | The React Flow graph canvas: node rendering (NodeCard), the FlowCanvas itself with execution animations, and the flowDef-JSON <-> React Flow nodes/edges translator. |
| `frontend-panels` | 7 | Sidebar/footer editor panels: node palette, variables panel, custom-nodes CodeMirror editor, properties panel, runs panel, and the flow settings dialog. |
| `frontend-state` | 5 | Client-side state and data access: the Zustand store (tabs, runs, catalog), the typed HTTP API client, and the SSE run-streaming hook with reconnect logic. |
| `frontend-ui-kit` | 11 | Design-system primitives adapted from shadcn/ui (Button, Dialog, Select, Tabs, etc.), rewritten to use inline styles instead of Tailwind per this repo's UI conventions. |
| `hooks-infra` | 54 | Repo-quality tooling infrastructure: Claude Code hooks that read rayflow_file_map.json to give an LLM agent per-file/per-system context, staleness reminders, live symbol/type-diagnostic info, and workflow checklists (plus settings.json wiring them in); the rayflow-auditor subagent and its _sot_scope.py helper; and the git/pre-commit-level SOT edit-blocking mechanism (scripts/check_sot_commit_message.py, .pre-commit-config.yaml) — a different mechanism (git hooks, not Claude Code hooks) serving the same repo-quality purpose. |
| `mcp` | 3 | The curated FastMCP tool layer exposing a subset of the editor API as MCP tools for LLM agents (get_guide, list_nodes, validate_flow, run_flow, etc.) plus the .mcp.json client registration for this repo. |
| `nodes` | 14 | The node system: @ray_node/@engine_node/@parallel_node decorators, pin descriptors (Input/Output/ExecInput/ExecOutput), NodeCatalog discovery/loading, and the built-in node library (math, control flow, casting, comparisons, variables, events). |
| `packaging` | 2 | Controls what actually ships: pyproject.toml package metadata/dependencies, MANIFEST.in inclusion/exclusion rules, and the built frontend bundle (rayflow/editor/static/dist/) that server.py serves. |
| `schema` | 4 | Flow JSON schema (FlowDef/NodeDef plain stdlib @dataclass models, not Pydantic — no pydantic dependency exists in this project) and the canonical data-pin type system (int/str/list[T]/dict[str,V]/Any) with compatibility rules. Foundational — almost every other backend system imports from here. |
| `server` | 6 | Top-level app wiring and the public Python API: FastAPI app assembly (rayflow/server.py), and rayflow.api's load()/execute()/execute_async()/serve_events()/stop() functions that everything else (CLI, tests, external callers) goes through. run() was removed — no more load+run+unload one-shot in the public API (tests/helpers.py's run_once is a test-only replacement, not public). |
| `state` | 3 | Two detached Ray actors that persist across executions of a loaded flow: GraphState (variables + watch_variable for change-triggered flows) and RunQueue (per-run SSE event sub-queues consumed by FastAPI). |
| `tests` | 14 | The pytest suite covering build/validation, the engine/executor, the editor REST API, custom nodes, events, CallFlow subflows, MCP tools, node behavior, and schema parsing. |


---
_Generado desde el commit `69ea42c`._
