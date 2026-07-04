---
name: rayflow-state-specialist
description: "Especialista en el sistema `state` de rayflow. Two detached Ray actors that persist across executions of a loaded flow: GraphState (variables + watch_variable for change-triggered flows) and RunQueue (per-run SSE event sub-queues consumed by FastAPI). Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
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

# Especialista: sistema `state`

Two detached Ray actors that persist across executions of a loaded flow: GraphState (variables + watch_variable for change-triggered flows) and RunQueue (per-run SSE event sub-queues consumed by FastAPI).

## Regla de citación de evidencia (aplica a toda respuesta)

Al responder preguntas sobre el código de este sistema, citá siempre la
evidencia concreta de tu afirmación: ruta de archivo relativa al repo +
nombre de función/clase/símbolo + número de línea cuando sea posible (por
ejemplo: `rayflow/nodes/decorators.py:42`, función `ray_node`). No afirmes
comportamiento del código a partir de una descripción en prosa (la de este
archivo, la de rayflow_file_map.json, o tu propio recuerdo) sin haber
verificado esa cita contra una lectura real y reciente del archivo. Si no
podés verificar algo con una lectura real, decilo explícitamente ("no lo
pude verificar en el código, esto es una inferencia") en vez de presentarlo
como un hecho. Un framing que suena correcto en prosa pero no resiste
"citá la línea exacta" no está listo para pasarle al usuario.

## Archivos (`rayflow_file_map.json` → `systems.state.files`)

| archivo | descripción |
|---|---|
| `rayflow/state/__init__.py` | Re-exports the GraphState actor class. |
| `rayflow/state/actor.py` | The GraphState Ray actor: a loaded flow's persistent named-variable memory across runs, plus variable-watch registration that publishes change events. |
| `rayflow/state/queue.py` | The RunQueue Ray actor: a per-flow FIFO event queue (one sub-queue per run_id) that the engine pushes to and FastAPI drains via blocking get() to stream SSE. |

## Dependencias entre sistemas

Depende de: `events`

Es dependencia de: `engine`

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
- **sistema-de-nodos-runqueue-sse#timeout-runqueue-no-capturado-run-endpoint**: RunQueue.get() tiene un timeout hardcodeado de 300s que lanza asyncio.TimeoutError si se excede; ni execute() ni execute_async() (api.py) capturan esa excepción alrededor del loop de queue.get — solo reconnect_async() la atrapa (indirectamente, vía el except Exception genérico) y la convierte en un evento flow_error. Una corrida estancada más de 5 minutos hace crashear el generador principal usado por POST /flows/{name}/run en vez de emitir un error limpio. — evidencia: `rayflow/state/queue.py#RunQueue.get`, `rayflow/api.py#execute`, `rayflow/api.py#execute_async`, `rayflow/api.py#reconnect_async`

### Sistema de eventos > Triggers por cambio de variable (OnVariableChange)

- **triggers-por-cambio-de-variable#registro-hace-serve-events-suscribe-flow**: El registro lo hace serve_events: suscribe el flow vigía al evento sintético var:{source}/{var} y marca la variable como vigilada en el GraphState del flow fuente (gs.watch_variable). Solo las variables vigiladas publican (sin amplificación sobre el resto). — evidencia: `rayflow/nodes/builtin/events.py`, `rayflow/state/actor.py`, `rayflow/engine/executor.py`
- **triggers-por-cambio-de-variable#graphstate-set-variable-solo-publica-valor**: GraphState.set_variable solo publica si el valor cambió (compara viejo vs nuevo, resolviendo ObjectRef). Escribir el mismo valor no dispara. — evidencia: `rayflow/nodes/builtin/events.py`, `rayflow/state/actor.py`, `rayflow/engine/executor.py`
- **triggers-por-cambio-de-variable#orden-carga-flow-fuente-debe-estar**: Orden de carga: el flow fuente debe estar cargado antes que el vigía (su gs_{source} debe existir al registrar). Por eso LoadedFlow.load ahora espera a que el engine termine __init__ (ray.get(engine.get_graph_id.remote())) antes de devolver: garantiza que gs_{flow} sea localizable por nombre apenas load() retorna. — evidencia: `rayflow/nodes/builtin/events.py`, `rayflow/state/actor.py`, `rayflow/engine/executor.py`
- **triggers-por-cambio-de-variable#riesgo-conocido-flow-vigila-propia-variable**: Riesgo conocido: un flow que vigila su propia variable y la reescribe en el run disparado puede entrar en bucle; la defensa actual es "solo dispara si cambió". Un guard de profundidad queda pendiente. — evidencia: `rayflow/nodes/builtin/events.py`, `rayflow/state/actor.py`, `rayflow/engine/executor.py`

### Archivos clave del backend

- **archivos-clave-del-backend#rayflow-state-actor-py-graphstate-variables**: rayflow/state/actor.py: GraphState — variables persistentes y su vigilancia (watch_variable). Los outputs de nodos viven en el RunContext del engine, no aquí. — evidencia: `rayflow/state/actor.py`

### Sistema de state (GraphState)

- **sistema-state#comparacion-fallida-asume-cambio**: GraphState.set_variable envuelve la comparación old != new en try/except Exception, y en caso de fallo (valores incomparables, __eq__ que lanza, etc.) asume changed=True y publica el evento igual — prioriza no perderse un cambio real sobre evitar falsos positivos. — evidencia: `rayflow/state/actor.py#GraphState.set_variable`
- **sistema-state#graphstate-sync-vs-runqueue-async**: GraphState declara sus métodos como def (no async def), mientras que FlowEngine y RunQueue son actores con métodos async def — un actor Ray sync procesa una llamada a la vez sin puntos de interleaving posibles dentro de un método, una garantía de serialización más fuerte que la 'secuencialidad del engine' que el docstring de GraphState invoca: incluso dos execute() concurrentes de la MISMA flow que escriben la misma variable simultáneamente quedan serializados por el actor mismo. — evidencia: `rayflow/state/actor.py#GraphState`, `rayflow/state/queue.py#RunQueue`

### Docs > Propuesta RunContext (staleness)

- **sistema-docs-runcontext#graphstate-ya-no-tiene-node-outputs**: Consistente con lo anterior: rayflow/state/actor.py ya no tiene _node_outputs/set_node_outputs/get_node_output/node_has_fired — exactamente lo que la propuesta pedía remover al mover outputs de nodos al RunContext por-run. — evidencia: `rayflow/state/actor.py`, `docs/propuesta-runcontext.md`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `133b575`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
