---
name: rayflow-mcp-specialist
description: "Especialista en el sistema `mcp` de rayflow. The curated FastMCP tool layer exposing a subset of the editor API as MCP tools for LLM agents (get_guide, list_nodes, validate_flow, run_flow, etc.) plus the .mcp.json client registration for this repo. Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
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

# Especialista: sistema `mcp`

The curated FastMCP tool layer exposing a subset of the editor API as MCP tools for LLM agents (get_guide, list_nodes, validate_flow, run_flow, etc.) plus the .mcp.json client registration for this repo.

## Archivos (`rayflow_file_map.json` → `systems.mcp.files`)

| archivo | descripción |
|---|---|
| `.mcp.json` | Registers Rayflow's own MCP server (served at /mcp by a running `rayflow serve`) so Claude Code can use its tools directly. |
| `rayflow/mcp/__init__.py` | Re-exports create_mcp, the entry point for Rayflow's MCP layer. |
| `rayflow/mcp/server.py` | Builds the FastMCP server exposing the curated MCP tool set for LLM agents: discovery (get_guide/list_nodes/get_node/list_types/type_check), validation (validate_flow), flow CRUD (list/get/create/update/delete_flow, flow_catalog), custom-node CRUD with hot reload, events (serve_flow_events/stop_flow_events), and execution (run_flow/test_flow with optional trace, unload_flow). All reuse the editor REST logic via rayflow.api (which uses rayflow.registry internally) instead of reimplementing it. create_mcp() takes no parameters — served flows are read from the registry, not passed in. |

## Dependencias entre sistemas

Depende de: `build`, `editor-api`, `nodes`, `schema`, `server`

Es dependencia de: `server`, `tests`

## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)

### Capa MCP (para agentes LLM)

- **capa-mcp#rayflow-mcp-server-py-expone-set**: rayflow/mcp/server.py expone un set curado de tools MCP construido con FastMCP, montado en /mcp (streamable-http) por create_app. — evidencia: `rayflow/mcp/server.py`
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
- **capa-mcp#claude-skills-rayflow-node-skill-md**: .claude/skills/rayflow-node/SKILL.md: cómo crear/editar un nodo custom. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#claude-skills-rayflow-flow-skill-md**: .claude/skills/rayflow-flow/SKILL.md: el loop de construir/validar/probar un flow vía MCP. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#claude-agents-rayflow-debugger-md-subagente**: .claude/agents/rayflow-debugger.md: subagente restringido a tools de solo lectura/diagnóstico (sin create_flow/update_flow/Write). — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#mcp-json-registra-server-mcp-local**: .mcp.json: registra el server MCP local (http://localhost:8000/mcp/); solo se escribe si el usuario no tiene uno ya (nunca se sobreescribe, ni con --force). — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#force-sobreescribe-skills-agente-existentes-nunca**: --force sobreescribe skills/agente existentes; nunca .mcp.json. — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`
- **capa-mcp#sin-force-instalacion-idempotente-archivos-existentes**: Sin --force, la instalación es idempotente (archivos existentes se saltean). — evidencia: `rayflow/mcp/server.py`, `rayflow/cli/main.py`, `rayflow/claude_tools/mcp.json`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `a4bce82`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
