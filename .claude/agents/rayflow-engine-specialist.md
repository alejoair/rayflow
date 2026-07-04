---
name: rayflow-engine-specialist
description: "Especialista en el sistema `engine` de rayflow. The FlowEngine Ray actor and LoadedFlow lifecycle: executes a BuiltFlow node-by-node (sequential exec pins, parallel data pins), manages per-run scratch state (RunContext), and is the runtime core every other backend... Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
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

# Especialista: sistema `engine`

The FlowEngine Ray actor and LoadedFlow lifecycle: executes a BuiltFlow node-by-node (sequential exec pins, parallel data pins), manages per-run scratch state (RunContext), and is the runtime core every other backend system ultimately drives.

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

## Archivos (`rayflow_file_map.json` → `systems.engine.files`)

| archivo | descripción |
|---|---|
| `rayflow/engine/__init__.py` | Re-exports LoadedFlow (the engine's only public symbol after the registry moved to rayflow/registry.py). |
| `rayflow/engine/executor.py` | The core execution engine: the FlowEngine Ray actor (runs a BuiltFlow node-by-node, dispatching @ray_node/@engine_node/CallFlow nodes, resolving data pins, emitting SSE events) and LoadedFlow (lifecycle of a flow's actors in Ray). The entry node is no longer short-circuited: it runs the normal _fire_engine_node path, constructs an EntryContext (with .request) for the root entry only, and _resolve_inputs pulls the root entry's inputs from RunContext.flow_inputs (the HTTP body). Entries without run() get auto-passthrough (mirror Input→Output) and auto-fire exec_out if run() didn't fire. RunContext now carries flow_inputs + request; execute() takes a request arg. |

## Dependencias entre sistemas

Depende de: `build`, `nodes`, `state`

Es dependencia de: `server`

## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)

### Arquitectura general

- **arquitectura-general#diagrama-editor-visual-browser-fastapi-rayflow**: Diagrama: editor visual (browser) <-> FastAPI (rayflow/server.py) <-> Ray actors/tasks; editor/frontend/ (React+Vite) compila a editor/static/dist/, que es lo que sirve el server; el motor vive en rayflow/engine/executor.py. — evidencia: `rayflow/server.py`, `rayflow/engine/executor.py`, `rayflow/editor/frontend/vite.config.ts`
- **arquitectura-general#principio-diseno-1-nodo-clase-python**: Principio de diseño 1: un nodo = una clase Python decorada con @ray_node o @engine_node. — evidencia: `rayflow/server.py`, `rayflow/engine/executor.py`, `rayflow/editor/frontend/vite.config.ts`
- **arquitectura-general#principio-diseno-2-namespace-plano-flatten**: Principio de diseño 2: namespace plano — flatten() expande subflows inline en build time (ids tipo padre/sub/nodo). — evidencia: `rayflow/server.py`, `rayflow/engine/executor.py`, `rayflow/editor/frontend/vite.config.ts`
- **arquitectura-general#principio-diseno-3-ejecucion-secuencial-control**: Principio de diseño 3: ejecución secuencial de control, paralela de datos — exec pins secuenciales, data pins evaluados en paralelo vía Ray. — evidencia: `rayflow/server.py`, `rayflow/engine/executor.py`, `rayflow/editor/frontend/vite.config.ts`
- **arquitectura-general#principio-diseno-4-tipos-siempre-son**: Principio de diseño 4: los tipos siempre son strings canónicos ("int", "str", "list[str]"), nunca clases Python. — evidencia: `rayflow/server.py`, `rayflow/engine/executor.py`, `rayflow/editor/frontend/vite.config.ts`

### Sistema de nodos > Nodos de entrada (@entry_node)

- **sistema-de-nodos-entrada#sin-run-engine-fire-engine-node**: Sin run(), el engine (_fire_engine_node) espeja cada Input declarado como un Output del mismo nombre y dispara exec_out — auto-passthrough, cubre el caso "trigger tonto" (OnStart) sin escribir un run() trivial. — evidencia: `rayflow/engine/executor.py#_fire_engine_node`

### Sistema de nodos > Estado en nodos

- **sistema-de-nodos-estado#engine-node-entre-iteraciones-mismo-run**: engine_node, entre iteraciones del mismo run(): variables locales Python en el stack de run() — funciona porque _local_fire cede y retoma en el mismo frame. — evidencia: `rayflow/nodes/decorators.py`, `rayflow/engine/executor.py`
- **sistema-de-nodos-estado#engine-node-entre-ejecuciones-flow-solo**: engine_node, entre ejecuciones del flow: solo vía ctx.get_variable()/ctx.set_variable() -> GraphState. — evidencia: `rayflow/nodes/decorators.py`, `rayflow/engine/executor.py`
- **sistema-de-nodos-estado#ray-node-exec-pins-entre-iteraciones**: ray_node con exec pins, entre iteraciones del mismo run(): variables locales Python o atributos self (el actor persiste). — evidencia: `rayflow/nodes/decorators.py`, `rayflow/engine/executor.py`
- **sistema-de-nodos-estado#ray-node-exec-pins-entre-ejecuciones**: ray_node con exec pins, entre ejecuciones del flow: atributos self.__init__ o ctx.get_variable() -> GraphState. — evidencia: `rayflow/nodes/decorators.py`, `rayflow/engine/executor.py`
- **sistema-de-nodos-estado#engine-node-reinstancia-cada-ejecucion-flow**: Un engine_node se reinstancia en cada ejecución del flow — no puede acumular estado en self entre requests. — evidencia: `rayflow/nodes/decorators.py`, `rayflow/engine/executor.py`
- **sistema-de-nodos-estado#ray-node-exec-pins-actor-ray**: Un ray_node con exec pins es un actor Ray persistente (vive de load() a unload()) — sí puede tener estado en self. — evidencia: `rayflow/nodes/decorators.py`, `rayflow/engine/executor.py`

### Sistema de nodos > Cómo funciona ctx.fire() internamente

- **sistema-de-nodos-ctx-fire#engine-node-llama-local-fire-directamente**: En un engine_node: llama _local_fire directamente dentro del FlowEngine — invoca _run_loop sin RPC, sin self-call. Esto permite que nodos de loop (ForEach, While) hagan await ctx.fire("loop_body") a mitad de run() sin deadlock. — evidencia: `rayflow/nodes/decorators.py#ExecContext.fire`, `rayflow/engine/executor.py`
- **sistema-de-nodos-ctx-fire#ray-node-execcontext-viaja-serializado-actor**: En un ray_node: el ExecContext viaja serializado al actor remoto; _fire_handler se descarta y ctx.fire() hace RPC al engine (engine.fire.remote(run_id, node_id, pin) — scopeado al run via ctx._run_id). — evidencia: `rayflow/nodes/decorators.py#ExecContext.fire`, `rayflow/engine/executor.py`

### Sistema de nodos > Buffer _pending_outputs en engine_nodes

- **sistema-de-nodos-pending-outputs#ctx-set-output-engine-node-escribe**: ctx.set_output() en un engine_node no escribe directamente al RunContext (eso requeriría await dentro de un método sync, o ray.get() bloqueante dentro del actor FlowEngine). En cambio, acumula en ctx._pending_outputs (dict local en memoria). — evidencia: `rayflow/engine/executor.py#_fire_engine_node`
- **sistema-de-nodos-pending-outputs#flowengine-flushea-ese-buffer-await-dos**: El FlowEngine flushea ese buffer con await en dos momentos: (1) antes de _local_fire(pin), solo si hay nodos destino que vayan a leer los outputs; (2) al finalizar run(), para outputs que no tienen sucesor exec. — evidencia: `rayflow/engine/executor.py#_fire_engine_node`
- **sistema-de-nodos-pending-outputs#write-node-outputs-escribe-run-node**: _write_node_outputs escribe en run.node_outputs (dict local por-run, síncrono — ya no toca el GraphState). — evidencia: `rayflow/engine/executor.py#_fire_engine_node`
- **sistema-de-nodos-pending-outputs#pending-outputs-vacia-serializacion-getstate-ctx**: _pending_outputs se vacía en serialización (__getstate__) — si el ctx viaja a un worker Ray, el buffer queda limpio y el nodo usa la ruta normal (RPC a set_output). — evidencia: `rayflow/engine/executor.py#_fire_engine_node`

### Sistema de nodos > RunQueue y eventos de ejecución (SSE)

- **sistema-de-nodos-runqueue-sse#cada-flow-cargado-tiene-actor-runqueue**: Cada flow cargado tiene un actor RunQueue persistente (queue_{flow_name}, lifetime="detached"), que se crea en load() y se destruye en unload(). — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#internamente-mantiene-dict-run-id-asyncio**: Internamente mantiene un dict[run_id -> asyncio.Queue]: cada ejecución reserva una entrada con create_run(run_id) y la libera con close_run(run_id) al terminar. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#flowengine-empuja-eventos-sub-queue-run**: El FlowEngine empuja eventos a la sub-queue del run activo; FastAPI los consume via get(run_id) bloqueante y los reenvía como SSE al cliente. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#driver-llama-await-queue-get-remote**: El driver llama await queue.get.remote(run_id) desde un async generator, evitando el overhead de run_in_executor. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#eventos-sse-emitidos-orden-run-start**: Eventos SSE emitidos en orden: run_start (run_id, por execute_async() como primer evento), node_start (node_id, node_type, ts), edge_fire (from, to, pin, ts), node_done (node_id, node_type, duration_ms, ts), flow_done (result, ts), flow_error (error, ts) — los últimos cinco por FlowEngine. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#5-eventos-node-start-edge-fire**: Los 5 eventos (node_start, edge_fire, node_done, flow_done, flow_error) se empujan con await. — evidencia: `rayflow/state/queue.py`, `rayflow/engine/executor.py`, `rayflow/server.py`, `rayflow/editor/routes.py`, `rayflow/editor/frontend/src/hooks/useRunStream.ts`
- **sistema-de-nodos-runqueue-sse#antes-empujaban-node-start-edge-fire**: Antes se empujaban node_start/edge_fire/node_done fire-and-forget (sin await), asumiendo que el orden FIFO quedaba garantizado solo por el event loop secuencial del actor RunQueue. Eso no alcanzaba: como flow_done sí se esperaba, era posible que execute() terminara y su push de flow_done ya estuviera en el mailbox de la RunQueue mientras los pushes fire-and-forget anteriores todavía estaban en vuelo. — evidencia: `rayflow/engine/executor.py#_local_fire`, `rayflow/engine/executor.py#_emit_node_start`
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

### Ciclo de vida de un flow en Ray

- **ciclo-de-vida-de-un-flow#load-flow-json-build-pre-valida**: load(flow_json): build() pre-valida y produce BuiltFlow (falla loud sin levantar actores). — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`
- **ciclo-de-vida-de-un-flow#loadedflow-load-spawn-actores-ray-node**: LoadedFlow.load(): spawn de actores @ray_node (uno por nodo exec con decorator ray_node), spawn de FlowEngine (engine_{flow_name}, lifetime="detached"), spawn de GraphState (gs_{flow_name}, lifetime="detached"), spawn de RunQueue (queue_{flow_name}, lifetime="detached"). — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`
- **ciclo-de-vida-de-un-flow#register-served-servedflow-agrega-flow-registry**: register_served(ServedFlow(...)) agrega el flow al registry (rayflow.registry). — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`
- **ciclo-de-vida-de-un-flow#execute-flow-name-inputs-genera-run**: execute(flow_name, inputs): genera run_id (uuid hex 8 chars), queue.create_run(run_id) reserva sub-queue en el actor persistente, yield {"event": "run_start", "run_id": run_id} como primer evento SSE, engine.execute.remote(inputs, queue, run_id) no bloquea, el driver consume queue.get(run_id) -> SSE al cliente, al llegar flow_done/flow_error se llama queue.close_run(run_id). — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`
- **ciclo-de-vida-de-un-flow#unload-flow-name-unregister-served-flow**: unload(flow_name): unregister_served(flow_name) lo quita del registry; kill de actores @ray_node + FlowEngine + GraphState + RunQueue. — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`
- **ciclo-de-vida-de-un-flow#graphstate-persiste-entre-ejecuciones-mismo-flow**: GraphState persiste entre ejecuciones del mismo flow cargado: solo guarda variables (memoria persistente) y su vigilancia (watch_variable). — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`
- **ciclo-de-vida-de-un-flow#outputs-nodos-viven-graphstate-son-scratch**: Los outputs de nodos NO viven en el GraphState — son scratch por-run y los posee el RunContext del engine, así que arrancan vacíos en cada execute() (un nodo no disparado en este run no deja output visible al siguiente). — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`
- **ciclo-de-vida-de-un-flow#run-reificado-runcontext-todo-scratch-transitorio**: El run reificado (RunContext): todo el scratch transitorio de una ejecución vive en un RunContext (run_id, queue, node_outputs, exec_arrivals, output_refs), no en campos sueltos de self. — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`
- **ciclo-de-vida-de-un-flow#engine-mantiene-self-runs-dict-run**: El engine mantiene self._runs: dict[run_id -> RunContext] y threadea el RunContext como primer parámetro por todos sus métodos internos. — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`
- **ciclo-de-vida-de-un-flow#execcontext-lleva-run-id-sobrevive-getstate**: El ExecContext lleva un _run_id (sobrevive a __getstate__) para que las RPC de vuelta de un @ray_node (fire/set_output) vayan scopeadas al run correcto. — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`
- **ciclo-de-vida-de-un-flow#persistente-compartido-entre-runs-debe-serlo**: Lo persistente y compartido entre runs es lo que debe serlo: variables del GraphState y el self de los @ray_node. — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`
- **ciclo-de-vida-de-un-flow#concurrencia-execute-flowengine-actor-ray-async**: Concurrencia de execute(): el FlowEngine es un actor Ray async que intercala las llamadas a execute() en su event loop. — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`
- **ciclo-de-vida-de-un-flow#scratch-run-esta-aislado-runcontext-dos**: Como el scratch por-run está aislado en su RunContext, dos ejecuciones simultáneas no se pisan y no hay lock (_exec_lock se eliminó al reificar el run). — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`
- **ciclo-de-vida-de-un-flow#ray-node-stateful-servido-dos-runs**: Un @ray_node stateful servido por dos runs concurrentes intercala sus mutaciones de self — es el contrato existente de "estado compartido entre invocaciones del actor", no una regresión; el aislamiento es solo del scratch por-run, no de la memoria del actor. — evidencia: `rayflow/api.py`, `rayflow/engine/executor.py`, `rayflow/registry.py`

### Sistema de eventos > Triggers por cambio de variable (OnVariableChange)

- **triggers-por-cambio-de-variable#onvariablechange-nodo-entrada-events-py-decorado**: OnVariableChange (nodo de entrada, events.py, decorado con @entry_node) declara variable y source (flow dueño; vacío = el propio) como Input de config, más value/old como Input que el engine puebla desde el evento — al no definir run(), el auto-passthrough los espeja como outputs. — evidencia: `rayflow/engine/executor.py#_fire_engine_node`
- **triggers-por-cambio-de-variable#registro-hace-serve-events-suscribe-flow**: El registro lo hace serve_events: suscribe el flow vigía al evento sintético var:{source}/{var} y marca la variable como vigilada en el GraphState del flow fuente (gs.watch_variable). Solo las variables vigiladas publican (sin amplificación sobre el resto). — evidencia: `rayflow/nodes/builtin/events.py`, `rayflow/state/actor.py`, `rayflow/engine/executor.py`
- **triggers-por-cambio-de-variable#graphstate-set-variable-solo-publica-valor**: GraphState.set_variable solo publica si el valor cambió (compara viejo vs nuevo, resolviendo ObjectRef). Escribir el mismo valor no dispara. — evidencia: `rayflow/nodes/builtin/events.py`, `rayflow/state/actor.py`, `rayflow/engine/executor.py`
- **triggers-por-cambio-de-variable#orden-carga-flow-fuente-debe-estar**: Orden de carga: el flow fuente debe estar cargado antes que el vigía (su gs_{source} debe existir al registrar). Por eso LoadedFlow.load ahora espera a que el engine termine __init__ (ray.get(engine.get_graph_id.remote())) antes de devolver: garantiza que gs_{flow} sea localizable por nombre apenas load() retorna. — evidencia: `rayflow/nodes/builtin/events.py`, `rayflow/state/actor.py`, `rayflow/engine/executor.py`
- **triggers-por-cambio-de-variable#riesgo-conocido-flow-vigila-propia-variable**: Riesgo conocido: un flow que vigila su propia variable y la reescribe en el run disparado puede entrar en bucle; la defensa actual es "solo dispara si cambió". Un guard de profundidad queda pendiente. — evidencia: `rayflow/nodes/builtin/events.py`, `rayflow/state/actor.py`, `rayflow/engine/executor.py`

### Archivos clave del backend

- **archivos-clave-del-backend#rayflow-engine-executor-py-flowengine-actor**: rayflow/engine/executor.py: FlowEngine (actor Ray), LoadedFlow (wrapper de actores, sin registry — eso vive en rayflow/registry.py). — evidencia: `rayflow/engine/executor.py`

### Sistema de engine (ejecución interna del FlowEngine)

- **sistema-engine#and-join-reset-en-loops**: En _is_ready, un nodo AND-join (exec_join='and' con >1 exec_sources) que ya recibió todas sus llegadas limpia run.exec_arrivals[node_id] con arrivals.clear() antes de retornar True — así que si el mismo nodo vuelve a visitarse dentro de la misma ejecución (loop / re-entrancy), debe esperar de nuevo TODAS sus fuentes, no queda 'ready' permanentemente. — evidencia: `rayflow/engine/executor.py#FlowEngine._is_ready`
- **sistema-engine#fire-run-descartado-keyerror**: FlowEngine.fire(run_id, ...) hace self._runs[run_id] sin default; como execute()'s finally hace self._runs.pop(run_id, None) apenas termina la corrida, cualquier RPC ctx.fire()/set_output() que llegue después de que execute() ya retornó revienta con KeyError en vez de fallar silenciosamente. — evidencia: `rayflow/engine/executor.py#FlowEngine.fire`, `rayflow/engine/executor.py#FlowEngine.execute`
- **sistema-engine#fanout-mismo-pin-concurrente**: Cuando un mismo exec pin tiene más de un target (rnode.exec_targets[pin] con len>1), tanto _local_fire como _run_loop disparan las ramas con asyncio.gather — es decir, el fan-out de UN pin hacia varios nodos corre en paralelo, no secuencialmente; 'secuencial' solo describe el avance dentro de una sola cadena de exec. — evidencia: `rayflow/engine/executor.py#FlowEngine._local_fire`, `rayflow/engine/executor.py#FlowEngine._run_loop`
- **sistema-engine#or-join-dispara-en-cada-llegada**: Un nodo con exec_join='or' nunca se registra en run.exec_arrivals (solo se registran ahí los AND-join con >1 fuente); por lo tanto _is_ready lo trata como siempre-listo, y el nodo se re-dispara en CADA llegada de CUALQUIERA de sus fuentes dentro de la misma corrida — no es 'el primero en llegar gana e ignora al resto', es 'corre una vez por cada arribo'. — evidencia: `rayflow/engine/executor.py#FlowEngine.execute`, `rayflow/engine/executor.py#FlowEngine._is_ready`
- **sistema-engine#callflow-invisible-en-sse**: El nodo shell de un CallFlow nunca emite node_start ni node_done: _fire_callflow_node escribe node_outputs directo y retorna la lista de targets a _run_loop sin pasar por _local_fire, así que la transición de su exec_out tampoco emite edge_fire. En el trace SSE/editor, un CallFlow shell es invisible — solo se ven los nodos internos ya aplanados del subflow. — evidencia: `rayflow/engine/executor.py#FlowEngine._fire_callflow_node`, `rayflow/engine/executor.py#FlowEngine._local_fire`
- **sistema-engine#callflow-isolated-vars-reseed-cada-fire**: Para un CallFlow isolated (subflow_vars no vacío), _fire_callflow_node reseedea las variables del subflow a sus defaults ESTÁTICOS en cada disparo del nodo — no solo una vez al cargar — vía self._state.set_variable.remote(...) ejecutado incondicionalmente al inicio de cada llamada. Si el mismo CallFlow se dispara varias veces dentro de un loop en la misma corrida, el estado acumulado del subflow se pisa antes de cada iteración. — evidencia: `rayflow/engine/executor.py#FlowEngine._fire_callflow_node`
- **sistema-engine#pure-node-sin-memoizar-por-run**: _resolve_pin, cuando el nodo productor no fue disparado en esta corrida y es un engine_node puro (not is_exec_node), evalúa su run() en el momento vía _eval_pure_engine_node — sin escribir el resultado a run.node_outputs. Si N consumidores distintos referencian el mismo pin de ese nodo puro, su run() se re-ejecuta N veces por corrida, sin memoización ni caché. — evidencia: `rayflow/engine/executor.py#FlowEngine._resolve_pin`, `rayflow/engine/executor.py#FlowEngine._eval_pure_engine_node`
- **sistema-engine#entry-input-requerido-silenciosamente-none**: Un Input requerido del entry raíz sin valor en flow_inputs (body HTTP) resuelve a None en runtime sin error: build.py salta el chequeo de 'required' para el entry raíz (rnode.node_def.subflow_of is None) en _validate_data_inputs, y _resolve_inputs en el engine cae a val=None cuando el pin no está en run.flow_inputs y no tiene default — no hay validación de 'required' ni en build-time ni en runtime para pines del entry raíz. — evidencia: `rayflow/build/validator.py#_validate_data_inputs`, `rayflow/engine/executor.py#FlowEngine._resolve_inputs`

### Sistema de state (GraphState)

- **sistema-state#isolation-callflow-es-namespacing-no-actor**: Un CallFlow isolated no obtiene su propio actor GraphState: _var_key namespacea la clave (state_path/var_name) dentro del MISMO actor GraphState del flow raíz. 'Isolated' es una convención de nombres de clave, no aislamiento real de proceso/actor. — evidencia: `rayflow/engine/executor.py#_var_key`, `rayflow/build/validator.py#flatten`

### Docs > Propuesta RunContext (staleness)

- **sistema-docs-runcontext#runcontext-ya-implementado-doc-sin-actualizar**: docs/propuesta-runcontext.md sigue redactado como propuesta pendiente ('Documento de diseño para ejecutar en una sesión nueva', plan incremental de 3 pasos aún sin marcar), pero el refactor que describe YA está implementado: rayflow/engine/executor.py define class RunContext (run_id, queue, node_outputs, exec_arrivals, output_refs) threadeada por parámetro, y _exec_lock ya no existe en el engine. A diferencia de otros docs de diseño que sí llevan un banner 'Actualización — implementado' agregado después de ejecutarse, este documento NO fue actualizado. — evidencia: `rayflow/engine/executor.py#RunContext`, `docs/propuesta-runcontext.md`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `133b575`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
