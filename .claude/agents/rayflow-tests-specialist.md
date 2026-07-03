---
name: rayflow-tests-specialist
description: "Especialista en el sistema `tests` de rayflow. The pytest suite covering build/validation, the engine/executor, the editor REST API, custom nodes, events, CallFlow subflows, MCP tools, node behavior, and schema parsing. Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
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

# Especialista: sistema `tests`

The pytest suite covering build/validation, the engine/executor, the editor REST API, custom nodes, events, CallFlow subflows, MCP tools, node behavior, and schema parsing.

## Archivos (`rayflow_file_map.json` → `systems.tests.files`)

| archivo | descripción |
|---|---|
| `tests/__init__.py` | Empty package marker for the test suite. |
| `tests/entry_fixtures.py` | Test-only @entry_node fixtures (EntryXY/EntryX/EntryAB/EntryN/EntryABC/EntryItems/EntryNumbersThreshold/EntryXBool) with register() to add them to the process-wide NodeCatalog. Re-homed here from rayflow/nodes/builtin/control.py so they never ship in the real catalog a `pip install rayflow` user sees; called from each test file's ray_init fixture right after reset_catalog(), since a catalog reset wipes anything outside rayflow.nodes.builtin. |
| `tests/helpers.py` | Test-only helper (run_once) replacing the removed rayflow.api.run(): loads, executes, and unconditionally unloads a flow — the always-fresh-reload behavior many tests rely on (reusing generic throwaway flow names like "parent"/"counter" across unrelated test functions), scoped to test code now that it's no longer part of the public API. |
| `tests/test_build.py` | Tests for the build/validation layer: BuildError cases for unknown node types, missing/duplicate entry nodes, missing exec inputs, type mismatches, and data cycles. Covers the generic @entry_node entry-point mechanism: any class decorated with @entry_node (not just the builtins) builds as the flow's entry, more than one entry node is a build error, and @entry_node is rejected when combined with @ray_node or when it declares exec_in. |
| `tests/test_callflow.py` | Tests for the CallFlow node: isolated vs. shared subflow state, meta['flow'] attribution, CallFlow inside a Parallel branch, and nested CallFlows. |
| `tests/test_cli.py` | Tests for `rayflow install claude-tools` via Click's CliRunner: fresh install writes skills/agent/.mcp.json, idempotency without --force, and --force overwriting skills/agent but never .mcp.json. |
| `tests/test_custom_nodes.py` | Tests for convention-based custom node discovery (custom_nodes/ + flows/ in the cwd) and the runtime_env it produces for Ray workers. |
| `tests/test_editor.py` | Tests for the /editor/* FastAPI routes: node catalog, types, validation (including multi-error collection and warnings), flow CRUD, custom nodes, concurrency isolation, events, and the self-verification /test endpoint. Also covers POST /flows/{name}/run (rayflow/server.py) from the editor-managed-flow side — requires an explicit POST /editor/flows/{name}/load first (no auto-load on demand: 'served' = 'explicitly loaded'), 404 if not served, SSE vs. JSON via the Accept header — since that endpoint is shared with served flows rather than living under /editor. The packaged-examples tests were removed along with that feature. |
| `tests/test_events.py` | Tests for the EventBroker: cross-flow EmitEvent/OnEvent pub/sub, OnVariableChange triggering on variable writes, and namespace isolation. |
| `tests/test_executor.py` | End-to-end execution tests with Ray: fan-out, Parallel fork/join (including nested), AND/OR exec_in join semantics, While/Map nodes, pure comparisons, per-run output isolation (the RunContext regression test), OnStart's request pins defaulting gracefully outside HTTP, ctx.set_response_status()/set_response_header() via both the engine_node local-closure and ray_node RPC paths, and custom @entry_node classes running as a flow's entry point (with and without declaring the HTTP envelope pins) exactly like OnStart/OnEvent do. |
| `tests/test_mcp.py` | Tests for the curated MCP tool layer (rayflow/mcp/server.py), exercised through FastMCP's in-memory client: discovery/validation/flow CRUD, the custom-node hot-reload lifecycle, the update_flow/delete_flow stale-graph regression, unload_flow, run_flow's trace=True, and serve/stop_flow_events. |
| `tests/test_nodes.py` | Tests for the node definition and discovery system: decorators, pin descriptors, NodeCatalog registration, and NodeMeta.is_entry being set only by the @entry_node decorator (false by default, rejecting exec_in, requiring at least one ExecOutput). |
| `tests/test_schema.py` | Tests for flow JSON schema deserialization (load_flow / FlowDef parsing). |
| `tests/test_server.py` | Tests for the REST API used by `rayflow serve` (rayflow/server.py): served-flow listing, running, duplicate-name validation, GraphState persistence across requests, OnStart's fixed headers/query/body/method outputs, ctx.set_response_status()/set_response_header() reaching the real HTTP response (including header isolation between separate requests), POST /flows/{name}/run returning 404 for an editor-managed flow that hasn't been explicitly served via POST /editor/flows/{name}/load (no on-demand auto-load — 'served' = 'explicitly loaded'), and the /flows/{name}/ui bundle (ChatTrigger end-to-end, 404 when the entry declares no frontend, UI disappearing after unload). |

## Dependencias entre sistemas

Depende de: `build`, `editor-api`, `events`, `mcp`, `nodes`, `schema`, `server`

Es dependencia de: _(ningún otro sistema)_

## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)

### Sistema de nodos > RunQueue y eventos de ejecución (SSE)

- **sistema-de-nodos-runqueue-sse#flow-este-servido-devuelve-404-ya**: Un flow que no esté servido devuelve 404 — ya no hay auto-carga on-demand desde /run (decisión deliberada: "servido" = "cargado explícitamente"). — evidencia: `rayflow/server.py#run_flow`, `tests/test_server.py`, `tests/test_editor.py`
- **sistema-de-nodos-runqueue-sse#ui-monta-desmonta-automaticamente-segun-presencia**: La UI se "monta y desmonta" automáticamente según la presencia del flow en el registry: un DELETE /editor/flows/{name}/load hace que /ui devuelva 404 al instante, sin necesidad de desmontar nada en el router. — evidencia: `rayflow/server.py#run_flow`, `tests/test_server.py`, `tests/test_editor.py`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `c7fb55c`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
