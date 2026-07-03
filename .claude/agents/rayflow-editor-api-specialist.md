---
name: rayflow-editor-api-specialist
description: "Especialista en el sistema `editor-api` de rayflow. The REST surface for the visual editor: flow CRUD, validation, catalog resolution, custom-node CRUD with hot reload, and the curated markdown guide served to LLM agents. Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
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

# Especialista: sistema `editor-api`

The REST surface for the visual editor: flow CRUD, validation, catalog resolution, custom-node CRUD with hot reload, and the curated markdown guide served to LLM agents.

## Archivos (`rayflow_file_map.json` → `systems.editor-api.files`)

| archivo | descripción |
|---|---|
| `rayflow/editor/__init__.py` | Empty package marker for the editor subpackage. |
| `rayflow/editor/custom_nodes_routes.py` | FastAPI router for CRUD on custom node .py files (create/read/update/delete) plus hot-reloading the node catalog from disk without restarting the server. |
| `rayflow/editor/guide.py` | Curated markdown guide to Rayflow's flow model, served by GET /editor/guide and the MCP get_guide tool as the semantic contract an LLM agent needs to build flows. Documents @entry_node (declares its own Input/Output pins, gets EntryContext with .request), auto-passthrough for entries without run(), ctx.set_response_status()/set_response_header() for flows served over HTTP. |
| `rayflow/editor/routes.py` | FastAPI router for the visual editor: node catalog, type info, flow CRUD, validation, load/test endpoints, guide, and event subscription. _node_spec() surfaces meta.is_entry. The _DYNAMIC_PINS table no longer includes OnStart/FlowInput/OnEvent — those nodes declare their pins statically now; only FlowOutput/Parallel/CallFlow remain as dynamic. run_flow_response accepts an optional `request` RequestData. The packaged-examples endpoints (GET /editor/examples, GET /editor/examples/{name}) were removed. |
| `rayflow/editor/storage.py` | Flow persistence: reads/writes flow JSON files under the workspace's flows/ directory and serializes a FlowDef back to a JSON-safe dict (no `inputs` field — entries declare their own Input pins). |

## Dependencias entre sistemas

Depende de: `build`, `nodes`, `schema`, `server`

Es dependencia de: `mcp`, `server`, `tests`

## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)

### Sistema de nodos > RunQueue y eventos de ejecución (SSE)

- **sistema-de-nodos-runqueue-sse#cada-flow-cargado-tiene-actor-runqueue**: Cada flow cargado tiene un actor RunQueue persistente (queue_{flow_name}, lifetime="detached"), que se crea en load() y se destruye en unload(). — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#internamente-mantiene-dict-run-id-asyncio**: Internamente mantiene un dict[run_id -> asyncio.Queue]: cada ejecución reserva una entrada con create_run(run_id) y la libera con close_run(run_id) al terminar. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#flowengine-empuja-eventos-sub-queue-run**: El FlowEngine empuja eventos a la sub-queue del run activo; FastAPI los consume via get(run_id) bloqueante y los reenvía como SSE al cliente. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#driver-llama-await-queue-get-remote**: El driver llama await queue.get.remote(run_id) desde un async generator, evitando el overhead de run_in_executor. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#eventos-sse-emitidos-orden-run-start**: Eventos SSE emitidos en orden: run_start (run_id, por execute_async() como primer evento), node_start (node_id, node_type, ts), edge_fire (from, to, pin, ts), node_done (node_id, node_type, duration_ms, ts), flow_done (result, ts), flow_error (error, ts) — los últimos cinco por FlowEngine. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#5-eventos-node-start-edge-fire**: Los 5 eventos (node_start, edge_fire, node_done, flow_done, flow_error) se empujan con await. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#driver-drena-queue-execute-async-corta**: Un driver que drena la queue (execute_async()) corta el loop en cuanto ve flow_done/flow_error — así que esos eventos por-nodo, si llegaban después, no aparecían en la respuesta (trace vacío en run_flow/test_flow con trace=True, o en el stream SSE), no solo desordenados. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#await-cada-push-garantiza-cada-evento**: await en cada push garantiza que cada evento esté confirmado en el mailbox antes de que se dispare el siguiente, así que flow_done nunca se adelanta. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#costo-rpc-bloqueante-evento-hot-path**: El costo es una RPC bloqueante por evento en el hot path del engine — se prioriza correctitud de la respuesta sobre esa latencia extra. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#post-flows-name-run-rayflow-server**: POST /flows/{name}/run (rayflow/server.py) es el único endpoint de ejecución HTTP — requiere que el flow esté servido (cargado en rayflow.registry). — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#servido-validado-actores-ray-vivos-llega**: Servido = "validado y con actores Ray vivos", y se llega por dos caminos equivalentes: rayflow serve --file al arranque, o POST /editor/flows/{name}/load en runtime. Ambos pre-validan (build()) y pre-cargan (LoadedFlow.load) de forma idéntica. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#run-flow-delega-renderizado-respuesta-run**: run_flow delega el renderizado de la respuesta a run_flow_response/wants_stream (en rayflow/editor/routes.py, reusado desde server.py) — que decide el formato según el header Accept: text/event-stream devuelve el stream SSE completo, cualquier otro valor (o ausencia) drena execute_async() internamente y devuelve un solo JSON con los outputs una vez que llega flow_done. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#frontend-manda-explicitamente-ese-header-accept**: El frontend manda explícitamente ese header Accept en cada POST .../run. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#reconexion-sse-get-flows-name-run**: Reconexión SSE: GET /flows/{name}/run/{run_id}/stream consume la sub-queue existente sin relanzar la ejecución ni cerrarla — funciona igual para un flow servido o uno del editor, ya que solo depende de que el flow esté cargado en Ray (is_flow_loaded). — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#frontend-bundle-flow-get-flows-name**: Frontend bundle por flow (GET /flows/{name}/ui): si el entry de un flow servido declaró frontend, el handler dinámico de rayflow/server.py sirve ese bundle de assets. Aplica a todo flow en el registry (servidos por CLI o cargados desde el editor). — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#ui-habla-flow-mismo-flows-name**: La UI habla con el flow por el mismo /flows/{name}/run de siempre — el atributo frontend solo selecciona "qué UI servir", no es un transporte nuevo. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`

### API REST del editor > Flows (rayflow/editor/routes.py)

- **api-rest-flows#get-editor-info-workspace-activo-cwd**: GET /editor/info: workspace activo {cwd}. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#get-editor-nodes-catalogo-nodos-disponibles**: GET /editor/nodes: catálogo de nodos disponibles. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#get-editor-types-tipos-canonicos-reglas**: GET /editor/types: tipos canónicos y reglas de compatibilidad. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#post-editor-type-check-verificar-compatibilidad**: POST /editor/type-check: verificar compatibilidad entre dos tipos. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#get-editor-guide-guia-curada-modelo**: GET /editor/guide: guía curada del modelo de Rayflow (markdown) para construir flows. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#get-editor-flows-lista-flows-flows**: GET /editor/flows: lista flows en flows/. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#get-editor-flows-name-flow-json**: GET /editor/flows/{name}: flow JSON. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#get-editor-flows-name-catalog-catalogo**: GET /editor/flows/{name}/catalog: catálogo resuelto del flow, cada nodo con sus pins dinámicos ya expandidos. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#post-editor-flows-crear-flow**: POST /editor/flows: crear flow. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#put-editor-flows-name-actualizar-flow**: PUT /editor/flows/{name}: actualizar flow. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#delete-editor-flows-name-borrar-flow**: DELETE /editor/flows/{name}: borrar flow. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#post-editor-validate-validar-flow-body**: POST /editor/validate: validar flow (body = flow JSON). Devuelve todos los errores + warnings de claves desconocidas. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#post-editor-flows-name-test-ejecutar**: POST /editor/flows/{name}/test: ejecutar y comparar outputs vs expected_outputs (auto-verificación). — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#post-editor-flows-name-load-cargar**: POST /editor/flows/{name}/load: cargar flow en Ray (precaché). — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#delete-editor-flows-name-load-descargar**: DELETE /editor/flows/{name}/load: descargar flow de Ray. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#get-editor-flows-loaded-lista-todos**: GET /editor/flows/loaded: lista todos los flows cargados en Ray con su interfaz (inputs/outputs). — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#get-editor-flows-name-loaded-estado**: GET /editor/flows/{name}/loaded: estado de carga de un flow concreto. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#post-editor-flows-name-serve-events**: POST /editor/flows/{name}/serve-events: suscribir al event bus. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#delete-editor-flows-name-serve-events**: DELETE /editor/flows/{name}/serve-events/{graph_id}: desuscribir. — evidencia: `rayflow/editor/routes.py`
- **api-rest-flows#ejecutar-flow-post-flows-name-run**: Ejecutar un flow (POST /flows/{name}/run) y reconectarse a un run activo (GET /flows/{name}/run/{run_id}/stream) no viven en routes.py — son endpoints de rayflow/server.py, compartidos entre flows servidos y flows del editor. — evidencia: `rayflow/editor/routes.py`

### API REST del editor > Nodos custom (rayflow/editor/custom_nodes_routes.py)

- **api-rest-custom-nodes#get-editor-custom-nodes-lista-archivos**: GET /editor/custom-nodes: lista archivos .py en custom_nodes/. — evidencia: `rayflow/editor/custom_nodes_routes.py`
- **api-rest-custom-nodes#get-editor-custom-nodes-name-source**: GET /editor/custom-nodes/{name}/source: código fuente de un nodo. — evidencia: `rayflow/editor/custom_nodes_routes.py`
- **api-rest-custom-nodes#post-editor-custom-nodes-crear-nuevo**: POST /editor/custom-nodes: crear nuevo archivo (body: {name, source?}). — evidencia: `rayflow/editor/custom_nodes_routes.py`
- **api-rest-custom-nodes#put-editor-custom-nodes-name-source**: PUT /editor/custom-nodes/{name}/source: guardar código editado. — evidencia: `rayflow/editor/custom_nodes_routes.py`
- **api-rest-custom-nodes#delete-editor-custom-nodes-name-eliminar**: DELETE /editor/custom-nodes/{name}: eliminar archivo. — evidencia: `rayflow/editor/custom_nodes_routes.py`
- **api-rest-custom-nodes#post-editor-custom-nodes-reload-recargar**: POST /editor/custom-nodes/reload: recargar catálogo desde disco (hot reload). — evidencia: `rayflow/editor/custom_nodes_routes.py`
- **api-rest-custom-nodes#endpoint-guardar-crear-valida-sintaxis-python**: El endpoint de guardar/crear valida sintaxis Python con ast.parse() antes de escribir el archivo, y llama reset_catalog() + get_catalog() para hacer hot reload sin reiniciar el servidor. — evidencia: `rayflow/editor/custom_nodes_routes.py`
- **api-rest-custom-nodes#modulos-custom-nodes-cacheados-sys-modules**: Los módulos custom_nodes.* cacheados en sys.modules se eliminan antes del reload para forzar reimportación. — evidencia: `rayflow/editor/custom_nodes_routes.py`

### Archivos clave del backend

- **archivos-clave-del-backend#rayflow-editor-routes-py-endpoints-flows**: rayflow/editor/routes.py: endpoints de flows, catálogo y ejecución. — evidencia: `rayflow/editor/routes.py`
- **archivos-clave-del-backend#rayflow-editor-custom-nodes-routes-py**: rayflow/editor/custom_nodes_routes.py: CRUD de nodos custom + hot reload del catálogo. — evidencia: `rayflow/editor/custom_nodes_routes.py`
- **archivos-clave-del-backend#rayflow-editor-storage-py-crud-flows**: rayflow/editor/storage.py: CRUD de flows en disco. — evidencia: `rayflow/editor/storage.py`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `c7fb55c`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
