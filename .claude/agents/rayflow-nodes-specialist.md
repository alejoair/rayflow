---
name: rayflow-nodes-specialist
description: "Especialista en el sistema `nodes` de rayflow. The node system: @ray_node/@engine_node/@parallel_node decorators, pin descriptors (Input/Output/ExecInput/ExecOutput), NodeCatalog discovery/loading, and the built-in node library (math, control flow, casting,... Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
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

# Especialista: sistema `nodes`

The node system: @ray_node/@engine_node/@parallel_node decorators, pin descriptors (Input/Output/ExecInput/ExecOutput), NodeCatalog discovery/loading, and the built-in node library (math, control flow, casting, comparisons, variables, events).

## Archivos (`rayflow_file_map.json` → `systems.nodes.files`)

| archivo | descripción |
|---|---|
| `rayflow/nodes/__init__.py` | Re-exports the node-authoring API: decorators, pin descriptors, ExecContext, and NodeCatalog. |
| `rayflow/nodes/builtin/__init__.py` | Imports CallFlow so it's registered as part of the builtin module set. |
| `rayflow/nodes/builtin/cast.py` | Builtin explicit type-casting nodes: ToInt, ToFloat, ToStr, ToBool. |
| `rayflow/nodes/builtin/chat_trigger_frontend/index.html` | Static chat UI bundle for the built-in ChatTrigger entry node (declares frontend = "chat_trigger_frontend"); mounted at GET /flows/{name}/ui for any served flow whose entry is ChatTrigger. Self-contained HTML/CSS/JS that POSTs {message: ...} to /flows/{name}/run and renders the response — no build step, no separate transport. |
| `rayflow/nodes/builtin/compare.py` | Builtin pure comparison/boolean-logic nodes (no exec pins): GreaterThan, LessThan, Equal, NotEqual, Not, And, Or, etc. |
| `rayflow/nodes/builtin/control.py` | Builtin control-flow nodes: OnStart (entry, @entry_node, declares body/headers/query/method from the HTTP envelope as Inputs with empty defaults — auto-passthrough since no run()), ChatTrigger (entry with frontend bundle, declares message Input + message_out Output + run() that forwards), FlowOutput, Branch, Sequence, Parallel (fork/join), ForEach, While, Map. OnStart and ChatTrigger now use category="Trigger" (unified with OnEvent/OnVariableChange in events.py) instead of "Control". The EntryX/EntryXY/EntryAB/EntryN/EntryABC/EntryItems/EntryNumbersThreshold/EntryXBool convenience entries that used to live here were removed — re-homed as test-only fixtures in tests/entry_fixtures.py so they no longer ship in the real builtin catalog. |
| `rayflow/nodes/builtin/events.py` | Builtin event nodes: OnEvent (@entry_node triggered by the event bus; declares event_name config Input + payload Input, auto-passthrough), OnVariableChange (@entry_node triggered by a watched variable; declares variable/source config + value/old Inputs, auto-passthrough), and EmitEvent (@engine_node, publishes to the bus). OnEvent and OnVariableChange both use category="Trigger" (unified with OnStart/ChatTrigger in control.py). |
| `rayflow/nodes/builtin/flow.py` | The CallFlow builtin node: declares the pins for running a subflow, orchestrated directly by the engine rather than via its own run(). |
| `rayflow/nodes/builtin/math.py` | The builtin Add node (integer addition). |
| `rayflow/nodes/builtin/variables.py` | Builtin state nodes: Get (reads a GraphState variable) and Set (writes one). |
| `rayflow/nodes/decorators.py` | Defines the node-authoring contract: the Input/Output/ExecInput/ExecOutput pin descriptors, the @ray_node/@engine_node/@parallel_node/@entry_node decorators, NodeMeta/PinSpec metadata, the unified ExecContext used by every node's run(), and EntryContext (subclass with .request) used only by @entry_node classes. @entry_node marks a flow's entry point — sets NodeMeta.is_entry (read by _find_entry), rejects exec_in and missing ExecOutput, and is the only path to EntryContext/RequestData. NodeMeta.is_entry is set ONLY by @entry_node (no longer a class attribute authors set). The old exposes_flow_inputs flag is gone. |
| `rayflow/nodes/loader.py` | NodeCatalog: discovers and registers node classes from a directory or from the workspace's custom_nodes/ package, handling pickling concerns for Ray worker distribution. |
| `rayflow/nodes/registry.py` | Builds and caches the process-wide singleton NodeCatalog from the builtin node modules plus the workspace's custom nodes; reset_catalog() forces a rebuild for tests/hot-reload. |

## Dependencias entre sistemas

Depende de: `events`, `schema`, `server`

Es dependencia de: `build`, `editor-api`, `engine`, `mcp`, `server`, `tests`

## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)

### Sistema de nodos > Decoradores

- **sistema-de-nodos-decoradores#ray-node-corre-proceso-ray-remoto**: @ray_node corre en proceso Ray remoto (actor con exec pins, task sin exec pins). — evidencia: `rayflow/nodes/decorators.py`
- **sistema-de-nodos-decoradores#engine-node-corre-directamente-dentro-flowengine**: @engine_node corre directamente dentro del FlowEngine (sin RPC); usar para lógica de control ligera. — evidencia: `rayflow/nodes/decorators.py`
- **sistema-de-nodos-decoradores#parallel-node-alias-engine-node-fork**: @parallel_node es alias de @engine_node, para fork/join explícito. — evidencia: `rayflow/nodes/decorators.py`
- **sistema-de-nodos-decoradores#contrato-run-identico-entre-ray-node**: El contrato de run() es idéntico entre @ray_node y @engine_node (ctx.set_output(), await ctx.fire()), pero difieren en despliegue y estado. — evidencia: `rayflow/nodes/decorators.py`
- **sistema-de-nodos-decoradores#ray-node-exec-pins-stateful-actor**: @ray_node con exec pins es stateful: el actor Ray se instancia una vez en load() y persiste hasta unload(); la misma instancia atiende todas las ejecuciones — atributos en self.__init__ o acumulados en run() persisten entre requests. — evidencia: `rayflow/nodes/decorators.py`
- **sistema-de-nodos-decoradores#engine-node-stateless-instancia-descarta-cada**: @engine_node es stateless: se instancia y descarta en cada ejecución del nodo; no puede acumular estado en self. — evidencia: `rayflow/nodes/decorators.py`

### Sistema de nodos > Nodos de entrada (@entry_node)

- **sistema-de-nodos-entrada#flow-necesita-exactamente-nodo-entrada-punto**: Un flow necesita exactamente un nodo de entrada — el punto donde el engine arranca la ejecución. — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#diferencia-category-frontend-atributos-clase-leidos**: A diferencia de category/frontend (atributos de clase leídos por _extract_meta), ser entry point no es algo que el autor del nodo fije directamente: lo otorga el decorador @entry_node, que marca meta.is_entry = True después de extraer la metadata. — evidencia: `rayflow/nodes/decorators.py#entry_node`
- **sistema-de-nodos-entrada#entry-node-engine-node-corre-dentro**: @entry_node es un @engine_node (corre dentro del engine, nunca @ray_node) con dos agregados: (1) recibe un EntryContext, subclase de ExecContext que expone ctx.request (body/headers/query/method) — solo un entry tiene acceso; cualquier otro nodo que intente leer ctx.request obtiene AttributeError por construcción; (2) sus Input declarados se pueblan desde run.flow_inputs (que el server llena con el body de la request, matcheando por nombre de pin) en vez de desde predecesores wireados. — evidencia: `rayflow/nodes/decorators.py#EntryContext`
- **sistema-de-nodos-entrada#find-entry-build-validator-py-exige**: _find_entry (build/validator.py) exige exactamente un nodo con meta.is_entry = True al buildear — cero o más de uno es error de build ("no entry node" / "more than one entry node"). — evidencia: `rayflow/nodes/decorators.py#entry_node`
- **sistema-de-nodos-entrada#define-run-autor-llama-ctx-set**: Si define run(), el autor llama ctx.set_output(...) + await ctx.fire(...) como cualquier engine_node (ChatTrigger es la referencia: reenvía message como message_out). — evidencia: `rayflow/nodes/builtin/control.py#ChatTrigger`
- **sistema-de-nodos-entrada#red-seguridad-run-entry-dispara-ningun**: Red de seguridad: si el run() de un entry no dispara ningún exec output, el engine dispara exec_out automáticamente al terminar, para no dejar el flow trabado. — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#frontend-str-opcional-nombre-directorio-assets**: frontend (str, opcional): nombre de un directorio de assets estáticos (HTML/JS/CSS) hermano del archivo .py del nodo. Si el entry de un flow servido lo declara, create_app monta ese directorio en GET /flows/{name}/ui con StaticFiles(html=True). — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#bundle-neutral-tipo-entry-onstart-chattrigger**: El bundle es neutral al tipo de entry: para OnStart/ChatTrigger el JS típicamente POSTea a /flows/{name}/run; otro entry podría no usar /run. — evidencia: `rayflow/nodes/builtin/control.py#ChatTrigger`
- **sistema-de-nodos-entrada#hay-sumo-frontend-flow-garantizado-exactly**: Hay a lo sumo un frontend por flow (garantizado por exactly-one-entry). — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#directorio-resuelve-via-inspect-getfile-cls**: El directorio se resuelve vía inspect.getfile(cls).parent / frontend; para built-ins vive en rayflow/nodes/builtin/<bundle>/ y para custom en custom_nodes/<bundle>/. — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#directorio-declarado-existe-loguea-warning-ruta**: Si el directorio declarado no existe, se loguea un warning y la ruta /ui no se monta (no rompe el startup). — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#chattrigger-built-in-referencia-declara-frontend**: ChatTrigger es el built-in de referencia: declara frontend = "chat_trigger_frontend" y un message/message_out propios. — evidencia: `rayflow/nodes/builtin/control.py#ChatTrigger`
- **sistema-de-nodos-entrada#restricciones-validadas-decorar-valueerror-inmediato-entry**: Restricciones validadas al decorar (ValueError inmediato): @entry_node no puede declarar exec_in y debe declarar al menos un ExecOutput. — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#ray-node-rechaza-clase-ya-decorada**: @ray_node rechaza una clase ya decorada con @entry_node. — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#onstart-onevent-onvariablechange-chattrigger-son-cuatro**: OnStart, OnEvent, OnVariableChange, y ChatTrigger son los cuatro tipos built-in decorados con @entry_node — no una lista cerrada del engine. — evidencia: `rayflow/nodes/builtin/control.py#ChatTrigger`
- **sistema-de-nodos-entrada#subflows-callflow-reconocen-nodo-entrada-spliceado**: Los subflows (CallFlow) reconocen su nodo de entrada spliceado genéricamente vía meta.is_entry en _splice_subflow (con un fallback por nombre literal OnStart/OnEvent, solo para callers legacy que invocan sin pasar el catálogo). — evidencia: `rayflow/nodes/builtin/events.py#OnEvent`

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

### Sistema de nodos > RunQueue y eventos de ejecución (SSE)

- **sistema-de-nodos-runqueue-sse#chattrigger-built-in-expone-asi-ui**: ChatTrigger (built-in) expone así una UI de chat estilo n8n. — evidencia: `rayflow/nodes/builtin/control.py#ChatTrigger`

### Sistema de nodos > Descubrimiento de nodos

- **sistema-de-nodos-descubrimiento#servidor-carga-nodos-desde-rayflow-nodes**: El servidor carga nodos desde rayflow/nodes/builtin/ (nodos built-in del paquete) y ./custom_nodes/ (nodos del usuario en el directorio de trabajo). — evidencia: `rayflow/nodes/registry.py`, `rayflow/nodes/loader.py`

### API REST del editor > Flows (rayflow/editor/routes.py)

- **api-rest-flows#get-editor-nodes-node-type-spec**: GET /editor/nodes/{node_type}: spec de un tipo de nodo concreto. Incluye dynamic para nodos con pins dinámicos (FlowOutput, Parallel, CallFlow); los nodos de entrada (OnStart, OnEvent, ChatTrigger, ...) ya no aparecen ahí — sus pins son estáticos, declarados en la clase. — evidencia: `rayflow/nodes/builtin/control.py#ChatTrigger`

### Schema de un flow (JSON)

- **schema-de-un-flow#ejemplo-schema-name-version-outputs-variables**: Ejemplo de schema: name, version, outputs, variables, events, nodes — sin campo inputs. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#flowinput-existe-alias-onstart-compatibilidad-hacia**: FlowInput existe como alias de OnStart por compatibilidad hacia atrás, pero el nombre canónico es OnStart. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#flows-guardan-flows-dentro-directorio-trabajo**: Los flows se guardan en flows/ dentro del directorio de trabajo. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#todo-flow-disparado-via-post-flows**: Todo flow disparado vía POST /flows/{name}/run — sea servido o del editor — se dispara por una request HTTP real. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#onstart-declara-body-headers-query-method**: OnStart declara body/headers/query/method como sus propios Input pins (defaults vacíos), así que cualquier flow con OnStart como entry los tiene disponibles gratis; un entry custom que los quiera debe declararlos él mismo. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#ya-hay-flag-generico-exposes-flow**: Ya no hay un flag genérico (exposes_flow_inputs) que inyecte esos pines automáticamente en cualquier entry. — evidencia: `rayflow/nodes/builtin/control.py#OnStart`
- **schema-de-un-flow#downstream-cualquier-nodo-lee-wireando-entry**: Downstream, cualquier nodo los lee wireando entry.headers, etc., como cualquier otro pin. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#flow-corre-via-http-mcp-execute**: Si el flow no corre vía HTTP (MCP, execute() directo), esos pines caen al default del Input que los consume (llegan vacíos). — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#acceso-envelope-crudo-sin-declarar-pines**: Para acceso al envelope crudo sin declarar pines, el propio entry puede leer ctx.request (EntryContext) dentro de su run(). — evidencia: `rayflow/nodes/decorators.py#EntryContext`
- **schema-de-un-flow#ctx-set-response-status-code-ctx**: ctx.set_response_status(code) / ctx.set_response_header(name, value) (en ExecContext) fijan el status/headers HTTP reales de la respuesta — viven en el RunContext de la ejecución (no en flow.outputs), así que no aparecen en el resultado que ve un caller no-HTTP. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#sin-llamarlos-default-200-sin-headers**: Sin llamarlos, el default es 200 sin headers extra. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#cuidado-parallel-dos-ramas-verdaderamente-paralelas**: Cuidado con Parallel: si dos ramas verdaderamente paralelas llaman set_response_status a la vez, gana la última escritura — solo una rama de un fork debería fijarlos. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#ejemplo-codigo-nodo-checkapikey-engine-node**: Ejemplo de código: nodo CheckApiKey (@engine_node normal) que compara headers.get("x-api-key") contra una env var y usa set_response_status(401) en el camino denegado. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`

### Sistema de eventos

- **sistema-de-eventos#serve-events-flow-json-igual-load**: serve_events(flow_json): igual que load() + suscripción al broker vía EventBroker.subscribe(event_name, flow_name, graph_id). — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-eventos#emitevent-node-ctx-emit-event-name**: EmitEvent node -> ctx.emit_event(name, payload) -> EventBroker.publish(name, payload) (fire-and-forget) -> _run_event_flow.remote(flow_name, name, payload) (Ray task que corre en un worker) -> ray.get_actor("engine_{flow_name}") + ray.get_actor("queue_{flow_name}") por nombre -> engine.execute.remote({"payload": payload}, queue, run_id). — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-eventos#stop-graph-id-event-names-eventbroker**: stop(graph_id, event_names): EventBroker.unsubscribe() + unload(). — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-eventos#run-event-flow-corre-task-ray**: _run_event_flow corre como task @ray.remote en un worker distinto del proceso driver, donde el registry (rayflow.registry) está vacío. Por eso resuelve el flow receptor por sus actores detached con nombre (engine_{flow}/queue_{flow}), no con get_served(). — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-eventos#dispara-engine-execute-directamente-varios-eventos**: Como dispara engine.execute directamente, varios eventos sobre el mismo flow generan ejecuciones concurrentes — aisladas por el RunContext de cada una (sin lock). — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-eventos#matching-eventbroker-exacto-string-incluyendo-namespace**: El matching del EventBroker es exacto por string (incluyendo namespace, p.ej. "ventas/order_created"). — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-eventos#nadie-esta-suscrito-evento-pierde-hay**: Si nadie está suscrito al evento, se pierde — no hay persistencia. — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-eventos#flow-eventos-debe-declarar-eventos-campo**: Un flow de eventos debe declarar los eventos en su campo events y tener nodo OnEvent. — evidencia: `rayflow/nodes/builtin/events.py#OnEvent`
- **sistema-de-eventos#flow-tiene-exactamente-nodo-entrada-decorado**: Un flow tiene exactamente un nodo de entrada (decorado con @entry_node) — declarar OnStart y OnEvent a la vez es un error de build, no una coexistencia silenciosa. — evidencia: `rayflow/nodes/builtin/events.py#OnEvent`

### Sistema de eventos > Triggers por cambio de variable (OnVariableChange)

- **triggers-por-cambio-de-variable#set-escribe-variable-vigilada-graphstate-set**: Set escribe variable vigilada -> GraphState.set_variable -> si cambió el valor: broker.publish("var:{source}/{var}", {value, old, variable}) (fire-and-forget) -> _run_event_flow.remote(flow_vigía, "var:...", payload) -> engine.execute(payload_como_flow_inputs, queue, run_id), donde OnVariableChange expone value/old. — evidencia: `rayflow/nodes/builtin/events.py#OnVariableChange`
- **triggers-por-cambio-de-variable#registro-vigilancia-variables-serve-events-suscribiendo**: El registro de vigilancia de variables (serve_events suscribiendo var:{source}/{var} + gs.watch_variable) es específico de OnVariableChange, no algo que un nodo custom decorado con @entry_node obtenga gratis — necesitaría su propio mecanismo de opt-in. — evidencia: `rayflow/nodes/builtin/events.py#OnVariableChange`
- **triggers-por-cambio-de-variable#registro-hace-serve-events-suscribe-flow**: El registro lo hace serve_events: suscribe el flow vigía al evento sintético var:{source}/{var} y marca la variable como vigilada en el GraphState del flow fuente (gs.watch_variable). Solo las variables vigiladas publican (sin amplificación sobre el resto). — evidencia: `rayflow/nodes/builtin/events.py`, `rayflow/state/actor.py`, `rayflow/engine/executor.py`
- **triggers-por-cambio-de-variable#graphstate-set-variable-solo-publica-valor**: GraphState.set_variable solo publica si el valor cambió (compara viejo vs nuevo, resolviendo ObjectRef). Escribir el mismo valor no dispara. — evidencia: `rayflow/nodes/builtin/events.py`, `rayflow/state/actor.py`, `rayflow/engine/executor.py`
- **triggers-por-cambio-de-variable#orden-carga-flow-fuente-debe-estar**: Orden de carga: el flow fuente debe estar cargado antes que el vigía (su gs_{source} debe existir al registrar). Por eso LoadedFlow.load ahora espera a que el engine termine __init__ (ray.get(engine.get_graph_id.remote())) antes de devolver: garantiza que gs_{flow} sea localizable por nombre apenas load() retorna. — evidencia: `rayflow/nodes/builtin/events.py`, `rayflow/state/actor.py`, `rayflow/engine/executor.py`
- **triggers-por-cambio-de-variable#riesgo-conocido-flow-vigila-propia-variable**: Riesgo conocido: un flow que vigila su propia variable y la reescribe en el run disparado puede entrar en bucle; la defensa actual es "solo dispara si cambió". Un guard de profundidad queda pendiente. — evidencia: `rayflow/nodes/builtin/events.py`, `rayflow/state/actor.py`, `rayflow/engine/executor.py`

### Archivos clave del backend

- **archivos-clave-del-backend#rayflow-nodes-decorators-py-ray-node**: rayflow/nodes/decorators.py: @ray_node, @engine_node, @parallel_node, ExecContext. — evidencia: `rayflow/nodes/decorators.py`
- **archivos-clave-del-backend#rayflow-nodes-loader-py-nodecatalog-registro**: rayflow/nodes/loader.py: NodeCatalog — registro, aliases, carga desde disco. — evidencia: `rayflow/nodes/loader.py`
- **archivos-clave-del-backend#rayflow-nodes-registry-py-singleton-catalogo**: rayflow/nodes/registry.py: singleton del catálogo, reset_catalog() para hot reload. — evidencia: `rayflow/nodes/registry.py`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `a4bce82`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
