---
name: rayflow-cli-specialist
description: "Especialista en el sistema `cli` de rayflow. The `rayflow` command-line entry point (serve, and future subcommands) built on top of rayflow.api and rayflow.server. Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
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

# Especialista: sistema `cli`

The `rayflow` command-line entry point (serve, and future subcommands) built on top of rayflow.api and rayflow.server.

## Archivos (`rayflow_file_map.json` → `systems.cli.files`)

| archivo | descripción |
|---|---|
| `rayflow/claude_tools/__init__.py` | Marks claude_tools as a package so setuptools' packages.find (include=['rayflow*']) picks it up automatically; no code, just the template assets `rayflow install claude-tools` copies. |
| `rayflow/claude_tools/agents/rayflow-debugger.md` | Installable Claude Code subagent (end-user template): diagnoses why a user's flow fails/misbehaves. Deliberately restricted to read-only tools (Read/Grep/Glob + diagnostic-only MCP tools, no create_flow/update_flow/Write) so it can only report a diagnosis, never silently modify the flow it's investigating. |
| `rayflow/claude_tools/mcp.json` | Template copied to <cwd>/.mcp.json by `rayflow install claude-tools`, identical in shape to this repo's own .mcp.json — registers the local rayflow MCP server at http://localhost:8000/mcp/. Only written if the destination doesn't already have one. |
| `rayflow/claude_tools/skills/rayflow-flow/SKILL.md` | Installable Claude Code skill (end-user template): the MCP tool loop for building/editing/testing a flow (get_guide -> list_nodes -> validate_flow iterate -> create_flow/update_flow -> test_flow/run_flow), CallFlow composition, event-reactive flows, and the HTTP request/response mechanism (OnStart's headers/query/body/method, ctx.set_response_status/set_response_header) for flows served via rayflow serve. |
| `rayflow/claude_tools/skills/rayflow-node/SKILL.md` | Installable Claude Code skill (end-user template, not for this repo's own dev process): how to create/edit a custom Rayflow node in a user's own project — decorator choice, pin contract, create_custom_node/update_custom_node_source MCP tools, hot reload. |
| `rayflow/cli/__init__.py` | Re-exports the click CLI group as `main`. |
| `rayflow/cli/main.py` | Click-based CLI: `rayflow serve` initializes Ray and starts the REST/editor/MCP server; `rayflow install claude-tools` copies packaged Claude Code skills/agent templates (rayflow/claude_tools/) into the current working directory's .claude/ and drops a .mcp.json registering the local MCP server, for an end user's own project (not this repo's own dev tooling). |

## Dependencias entre sistemas

Depende de: `events`, `server`

Es dependencia de: `server`

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

### Capa MCP (para agentes LLM)

- **capa-mcp#reusa-misma-logica-api-rest-editor**: Reusa la misma lógica que la API REST del editor — no la reimplementa. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#lifespan-pasa-fastapi-construir-app-gestor**: Su lifespan se pasa a FastAPI al construir la app para que el gestor de sesiones arranque. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#discovery-tools-get-guide-list-nodes**: Discovery tools: get_guide, list_nodes, get_node, list_types, type_check. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#validation-tools-validate-flow**: Validation tools: validate_flow. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#flow-crud-tools-list-flows-get**: Flow CRUD tools: list_flows, get_flow, create_flow, update_flow, delete_flow, flow_catalog. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#custom-nodes-tools-list-custom-nodes**: Custom nodes tools: list_custom_nodes, get_custom_node_source, create_custom_node, update_custom_node_source, delete_custom_node, reload_custom_nodes. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#events-tools-serve-flow-events-stop**: Events tools: serve_flow_events, stop_flow_events. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#execution-tools-run-flow-test-flow**: Execution tools: run_flow, test_flow, unload_flow. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#loop-tipico-agente-get-guide-list**: Loop típico de un agente: get_guide -> list_nodes -> validate_flow (itera hasta valid:true) -> create_flow/update_flow -> test_flow/run_flow. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#validate-flow-devuelve-todos-errores-pasada**: validate_flow devuelve todos los errores de una pasada (ver validate_all en build/validator.py), cerrando el loop de feedback con pocos round-trips. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#update-flow-delete-flow-descargan-flow**: update_flow/delete_flow descargan el flow de Ray si ya estaba cargado — si no, la siguiente ejecución reusaría en silencio el grafo viejo, porque run_flow/test_flow evitan recargar un flow ya cargado como optimización. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#unload-flow-expone-esa-descarga-explicitamente**: unload_flow expone esa descarga explícitamente. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#create-custom-node-update-custom-node**: create_custom_node/update_custom_node_source/delete_custom_node hacen hot-reload del catálogo automáticamente (mismo mecanismo que el endpoint REST). — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#run-flow-test-flow-aceptan-trace**: run_flow/test_flow aceptan trace=True para devolver los eventos node_start/node_done/edge_fire en orden — útil para localizar qué nodo produjo un valor inesperado. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#fastmcp-dependencia-core**: fastmcp es dependencia core. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#rayflow-install-claude-tools-copia-plantillas**: rayflow install claude-tools copia plantillas empaquetadas en rayflow/claude_tools/ (package-data) al directorio de trabajo del usuario final — no es tooling para desarrollar rayflow mismo. — evidencia: `rayflow/cli/main.py#install_claude_tools`
- **capa-mcp#claude-skills-rayflow-node-skill-md**: .claude/skills/rayflow-node/SKILL.md: cómo crear/editar un nodo custom. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#claude-skills-rayflow-flow-skill-md**: .claude/skills/rayflow-flow/SKILL.md: el loop de construir/validar/probar un flow vía MCP. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#claude-agents-rayflow-debugger-md-subagente**: .claude/agents/rayflow-debugger.md: subagente restringido a tools de solo lectura/diagnóstico (sin create_flow/update_flow/Write). — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#mcp-json-registra-server-mcp-local**: .mcp.json: registra el server MCP local (http://localhost:8000/mcp/); solo se escribe si el usuario no tiene uno ya (nunca se sobreescribe, ni con --force). — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#force-sobreescribe-skills-agente-existentes-nunca**: --force sobreescribe skills/agente existentes; nunca .mcp.json. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#sin-force-instalacion-idempotente-archivos-existentes**: Sin --force, la instalación es idempotente (archivos existentes se saltean). — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`

### Archivos clave del backend

- **archivos-clave-del-backend#rayflow-cli-main-py-cli-rayflow**: rayflow/cli/main.py: CLI — rayflow serve. — evidencia: `rayflow/cli/main.py`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `c7fb55c`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
