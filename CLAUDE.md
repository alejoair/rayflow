# Rayflow — Contexto del proyecto

Rayflow es un motor de ejecución de grafos de nodos al estilo Unreal Engine Blueprints, construido sobre Ray. Los flows se definen como JSON y se ejecutan distribuyendo nodos como actores/tasks de Ray.

---

## Tipos de nodo

### `@ray_node`
Ejecutado como actor o task de Ray (proceso remoto, distribuido).

- **Con exec pins** → actor Ray (estado persistente entre llamadas).
- **Sin exec pins** → task Ray (función pura sin estado).
- `ctx.fire(pin)` acumula los pins disparados; el engine los encola al terminar `run()`.
- El decorador genera automáticamente `run_with_ctx(ctx, **inputs)` que devuelve `(fired_pins, outputs_dict)`.

```python
@ray_node
class Add:
    exec_in = ExecInput()
    a = Input("int", default=0)
    b = Input("int", default=0)
    result = Output("int")
    exec_out = ExecOutput()

    def run(self, ctx: ExecContext, a: int, b: int) -> dict:
        ctx.fire("exec_out")
        return {"result": a + b}
```

### `@engine_node`
Ejecutado localmente por el engine (mismo proceso, sin Ray).

- `ctx.fire(pin)` es **bloqueante**: ejecuta el subgrafo conectado completo antes de retornar.
- `ctx.set_output(pin, value)` expone data outputs intermedios (usado en ForEach, etc.).
- Habilita: control de flujo (Branch, ForEach, Sequence), TryCatch, While, CallFlow, depuración, y cualquier nodo que necesite razonar sobre la ejecución.
- Los subgrafos disparados por `ctx.fire()` pueden contener `@ray_node` normales.

```python
@engine_node
class Branch:
    exec_in = ExecInput()
    condition = Input("bool", default=False)
    true = ExecOutput()
    false = ExecOutput()

    def run(self, ctx: ExecContext, condition: bool) -> dict:
        ctx.fire("true" if condition else "false")
        return {}

@engine_node
class ForEach:
    exec_in = ExecInput()
    array = Input("list", default=None)
    loop_body = ExecOutput()
    completed = ExecOutput()
    element = Output("Any")
    index = Output("int")

    def run(self, ctx: ExecContext, array: list) -> dict:
        for i, element in enumerate(array or []):
            ctx.set_output("element", element)
            ctx.set_output("index", i)
            ctx.fire("loop_body")   # bloquea; el subgrafo puede tener @ray_node
        ctx.fire("completed")
        return {}
```

---

## ExecContext

Pasado como primer argumento a `run()` en ambos tipos de nodo.

```python
class ExecContext:
    def fire(self, pin_name: str) -> None: ...
    def set_output(self, pin_name: str, value: Any) -> None: ...
    def get_variable(self, name: str) -> Any: ...       # lee variable del GraphState
    def set_variable(self, name: str, value: Any): ...  # escribe variable en el GraphState
    def emit_event(self, event_name: str, payload: Any = None): ...  # publica al EventBroker
```

En `@ray_node` viaja serializado al proceso del actor (`_SerializableExecContext`). Lleva el `graph_id` de la ejecución y resuelve el `GraphState` via `ray.get_actor(f"gs_{graph_id}")` — así cualquier actor Ray puede acceder al estado compartido de su grafo sin depender del handle Python del driver.

En `@engine_node` es local con callbacks directos al engine.

`get_variable` y `set_variable` están disponibles en **ambos** tipos. En `@ray_node` la llamada es remota (actor → actor de estado); en `@engine_node` es local.

---

## Pin implícito `meta`

Todos los nodos (tanto `@ray_node` como `@engine_node`) exponen automáticamente un data output `meta` de tipo `dict`, inyectado por el engine tras cada ejecución. No se declara en el nodo — siempre está disponible.

```python
{
    "id": "add_1",        # id de la instancia (ruta plana: "sub/add_1" si viene de un CallFlow)
    "type": "Add",        # nombre de la clase del nodo
    "flow": "mi_flow",    # nombre del flow que DECLARÓ el nodo (el subflow si viene de un CallFlow, no el raíz)
    "started_at": 1718100000.123,  # unix timestamp de inicio
    "duration_ms": 45.2,           # duración de run() en milisegundos
}
```

Se puede conectar como cualquier data output:
```json
{ "id": "logger", "type": "Log", "inputs": { "data": "add_1.meta" } }
```

El validator reconoce `"node_id.meta"` como referencia válida aunque no esté declarado en el nodo. En `build/validator.py` hay un caso especial para `src_pin == "meta"` que asigna tipo `"dict"`.

---

## Tipos de pines

| Descriptor | Tipo | Descripción |
|---|---|---|
| `Input("int", default=0)` | data input | Recibe un valor. Tipo canónico string. |
| `Output("str")` | data output | Produce un valor. |
| `ExecInput()` | exec input | Recibe señal de ejecución. |
| `ExecOutput()` | exec output | Dispara señal de ejecución. |

**Tipos permitidos**: `int`, `float`, `str`, `bool`, `list`, `dict`, `Any`, `list[T]`, `dict[str, T]`.
La compatibilidad es estricta: no hay coerción implícita. `int` y `float` son incompatibles. Usar nodos `ToInt`, `ToFloat`, `ToStr`, `ToBool` para casteos.

---

## Engine — ciclo de ejecución

`FlowEngine` es una clase Python local (no actor Ray). `FlowExecutor` es un wrapper fino para compatibilidad con la API pública. `_run_loop()` mantiene una cola BFS de `node_id`s a disparar.

```
_fire(node_id)
  ├─ subflow_entry  → _fire_callflow_node()  (CallFlow shell: orquesta subgrafo inline)
  ├─ is_parallel    → _fire_parallel_node()  (fork/join vía _run_subgraph_task)
  ├─ is_engine_node → _fire_engine_node()    (local, ctx.fire() bloqueante)
  └─ @ray_node      → _fire_ray_node()       (actor Ray, ctx acumula pins)
```

- **`_fire_callflow_node()`**: orquesta un CallFlow shell. El subflow ya está aplanado inline en build (ver "Flatten"). Dispara `subflow_entry` (bloqueante vía `_run_loop`), reúne los inputs del `subflow_exit` como el dict `result`, y continúa hacia `exec_out`.
- **`_fire_engine_node()`**: instancia el nodo, crea `ExecContext` con callbacks locales, llama `run(ctx, **inputs)`. Cada `ctx.fire(pin)` llama `_run_loop(target)` síncronamente. Los outputs se guardan en `GraphState` **después** de que `run()` retorna. Para outputs que deben estar disponibles antes del `fire()`, usar `ctx.set_output(pin, value)` dentro de `run()`.
- **`_fire_ray_node()`**: llama `actor.run_with_ctx.remote(ctx, **inputs)`, hace `ray.get()`, recoge `fired_pins` del ctx devuelto, los traduce a `node_id`s via `exec_targets` y los encola en el BFS.

Los data outputs de cada nodo se escriben en `GraphState` (actor Ray) y se leen bajo demanda al resolver inputs de nodos posteriores.

### Pure nodes (nodos lazy)

Un `@engine_node` **sin exec pins** es un "pure node" — se evalúa bajo demanda cuando otro nodo necesita su output, igual que los pure nodes de Unreal Blueprints. No requiere conexión exec en el JSON.

```python
@engine_node
class Get:
    variable_name = Input("str", default="")
    value = Output("Any")

    def run(self, ctx: ExecContext, variable_name: str) -> dict:
        return {"value": ctx.get_variable(variable_name)}
```

El engine lo detecta en `_resolve_pin` (path 2a) y llama `_eval_pure_engine_node()` en el momento en que el nodo consumidor necesita ese valor. El mismo mecanismo aplica a cualquier `@engine_node` sin exec pins que el usuario defina — no hay configuración especial.

Un `@ray_node` sin exec pins también es lazy (path 2b), pero se ejecuta como task Ray.

### Ciclo de vida de actores @ray_node

Los actores se crean **una sola vez** al inicio del flow en `FlowEngine._spawn_actors()`, con nombre único `{node_id}_{graph_id}` en namespace `"rayflow"`. Los handles se guardan en `self._actors` y se pasan directamente a las ramas paralelas (`_run_subgraph_task`), que reusan el mismo `FlowEngine` en modo subgrafo.

- Los actores **no** se crean en tiempo de ejecución ni por cada rama — son singleton por flow.
- `CallFlow` **no** crea engines: el subflow se aplana inline en build time (ver "Flatten" abajo) y el engine lo orquesta como un subgrafo del mismo flow.
- `NodeMeta.__getstate__/__setstate__` excluye `ray_handle` del pickle y lo reconstruye en el worker a partir de `py_class` — evita problemas de serialización de handles Ray.
- **Restricción**: clases `@ray_node` definidas localmente (ej. en tests) deben registrarse en el catálogo antes de compilar el flow. Son serializables porque `py_class` viaja en el `BuiltFlow`.

---

## Flatten — namespace plano de nodos

En build time, `flatten()` (`build/validator.py`) expande recursivamente cada `CallFlow` **inline** en un único grafo plano. No hay subflows ni ejecutores anidados en runtime: todo es un namespace plano de nodos cuyos ids son **rutas de procedencia** estilo S3, donde los `/` son solo parte del nombre, no contenedores reales.

```
padre/add_1
padre/sub/add_1          ← nodo de un CallFlow "sub"
padre/sub/sub2/add_1     ← CallFlow anidado (un salto por nivel)
```

- **Reusa FlowInput/FlowOutput** del subflow como puntos de empalme — cero nodos builtin implícitos nuevos. Se marcan con `subflow_of` = el CallFlow shell **inmediato** (un salto hacia arriba, como `parentNode` en el DOM).
- El `CallFlow` shell guarda `subflow_entry`/`subflow_exit` (ids del entry/exit del subgrafo) y `subflow_vars` (variables del subflow aislado a sembrar). El engine lo orquesta en `_fire_callflow_node`.
- **Subflow estático**: el input `flow` debe ser un dict inline o ruta conocida en build. No se soporta elegir el subflow en runtime.

Campos en `NodeDef` que produce el flatten: `state_path`, `subflow_of`, `iface`, `subflow_entry`, `subflow_exit`, `subflow_vars`, `flow_name` (nombre del flow declarante, usado en `meta['flow']`).

---

## Paralelismo

### Fan-out exec
Un exec output puede conectarse a múltiples nodos destino — todos se disparan en secuencia desde el engine. Se declara con múltiples nodos apuntando al mismo origen:

```json
{ "id": "nodo_a", "exec_in": "origen" },
{ "id": "nodo_b", "exec_in": "origen" }
```

`exec_targets` en `ResolvedNode` es `dict[str, list[str]]` — cada pin puede tener uno o varios destinos.

### Nodo `Parallel` — fork/join real
Fork/join con paralelismo real vía Ray. Cada rama corre como task Ray (`_run_subgraph_task`), que reusa el mismo `FlowEngine` en **modo subgrafo** (estado y actores inyectados, no creados ni destruidos) y comparte el mismo `GraphState` actor.

```json
{ "id": "par", "type": "Parallel", "exec_in": "entry" },
{ "id": "rama_a", "type": "ProcessA", "exec_in": "par.branch_0" },
{ "id": "rama_b", "type": "ProcessB", "exec_in": "par.branch_1" },
{ "id": "merge",  "type": "Merge",    "exec_in": "par.joined" }
```

- `branch_0`, `branch_1`, `branch_2` — se lanzan simultáneamente.
- `joined` — se dispara cuando **todas** las ramas terminan (ray.get sobre todos los refs).
- Las ramas pueden contener `@engine_node` y `@ray_node` normales.
- El aislamiento es por proceso Ray — los `@engine_node` de ramas distintas no comparten estado Python.
- El `GraphState` es el único punto de sincronización compartido — accesos serializados por ser actor Ray.
- **Condición de carrera**: si dos ramas escriben la misma variable con `Set`, el resultado es no determinista. Es un error de diseño del flow, no del engine.

### Modelo de serialización para ramas paralelas
`BuiltFlow` se serializa por Ray para pasar a cada task de rama. `NodeMeta.ray_handle` se excluye del pickle (`__getstate__`) y se reconstruye en el worker destino (`__setstate__`).

`_run_subgraph_task` recibe el `built`, el `graph_id`, el handle del `GraphState` y los handles de actores `@ray_node` del flow padre — todos serializables por Ray. Con ellos instancia un `FlowEngine` en modo subgrafo (`run_subgraph(entry_id)`), sin recrear estado ni actores.

---

## Nodos builtin

| Nodo | Tipo | Exec pins | Descripción |
|---|---|---|---|
| `OnStart` | `@engine_node` | sí | Punto de entrada sin parámetros |
| `FlowInput` | `@engine_node` | sí | Punto de entrada con parámetros |
| `FlowOutput` | `@engine_node` | sí | Punto de salida del flow |
| `OnEvent` | `@engine_node` | sí | Entrada por evento externo. `event_name` (con namespace) es config estática; expone el `payload` recibido como output |
| `EmitEvent` | `@engine_node` | sí | Publica un evento al EventBroker via `ctx.emit_event()`. `event_name` lleva el namespace (ej. `"ventas/order_created"`) |
| `Branch` | `@engine_node` | sí | Desvío condicional true/false |
| `Sequence` | `@engine_node` | sí | Dispara then_0/then_1/then_2 en orden |
| `Parallel` | `@parallel_node` | sí | Fork/join — lanza branch_0/1/2 en paralelo, joined al terminar |
| `ForEach` | `@engine_node` | sí | Itera array, dispara loop_body por elemento |
| `Get` | `@engine_node` | **no** | Lee variable — pure node, evaluado bajo demanda |
| `Set` | `@engine_node` | sí | Escribe variable via `ctx.set_variable()` |
| `CallFlow` | `@engine_node` | sí | Ejecuta otro flow como subgrafo, aplanado inline en build (ver "Flatten"). `isolated=True`: variables en namespace de estado propio (clave prefijada). `isolated=False`: comparte variables del padre. Output `result: dict` contiene los outputs del subflow. Inputs extra se pasan al subflow. |
| `Add` | `@ray_node` | sí | Suma dos enteros |
| `GreaterThan` | `@ray_node` | sí | Compara dos enteros, devuelve bool |
| `ToInt/ToFloat/ToStr/ToBool` | `@ray_node` | sí | Casteos explícitos |

---

## Schema de un flow (JSON)

```json
{
  "name": "mi_flow",
  "version": "1",
  "inputs": { "x": "int" },
  "outputs": { "result": "int" },
  "variables": [{ "name": "contador", "type": "int", "default": 0 }],
  "events": [],
  "nodes": [
    { "id": "entry", "type": "FlowInput" },
    { "id": "add", "type": "Add", "exec_in": "entry", "inputs": { "a": "entry.x", "b": 10 } },
    { "id": "exit", "type": "FlowOutput", "exec_in": "add", "inputs": { "result": "add.result" } }
  ]
}
```

`exec_in` acepta `"node_id"` (exec output por defecto) o `"node_id.pin_name"` (exec output específico, ej. `"branch.true"`).

---

## API pública

```python
import rayflow

# Síncrono
outputs = rayflow.run("flow.json", x=5, y=3)

# Asíncrono (devuelve ObjectRef de Ray)
ref = rayflow.run_async("flow.json", x=5)
outputs = ray.get(ref)

# Flow residente por eventos (suscribe al EventBroker; ver "Sistema de eventos")
graph_id = rayflow.serve_events("flow.json")
rayflow.stop(graph_id, ["mi_evento"])
```

Cada ejecución (`run`/`run_async`) se aísla por un `graph_id` UUID propio, así
que ejecuciones concurrentes del mismo flow no colisionan.

---

## API REST (CLI `rayflow serve`)

`rayflow/server.py` levanta un servidor FastAPI que sirve uno o más flows como
endpoints HTTP. Distinto de `serve_events` (bus de eventos): aquí cada request
HTTP ejecuta el flow y devuelve sus outputs.

```bash
rayflow serve --file suma.json --file otro.json --port 8000
```

Carga y **valida** cada flow al arrancar (build temprano; falla si un flow no
compila o si dos comparten `name`), los indexa por su `name`, y expone:

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Healthcheck |
| `GET` | `/flows` | Lista flows servidos con su interfaz (inputs/outputs) |
| `GET` | `/flows/{name}` | Interfaz de un flow |
| `POST` | `/flows/{name}/run` | Ejecuta el flow con los inputs del body JSON, devuelve outputs |

```
POST /flows/suma/run   { "x": 3, "y": 7 }   ->   { "resultado": 10 }
```

El handler es `async` y usa `run_async` (awaitable sobre el `ObjectRef` de Ray),
sin bloquear el event loop. Requiere el extra: `pip install 'rayflow[serve]'`
(FastAPI + uvicorn). CLI en `rayflow/cli.py`; `python -m rayflow serve …` también.

---

## Sistema de eventos (EventBroker)

El `EventBroker` (`events/bus.py`) es un **único actor Ray detached y global**,
análogo al `GraphState` pero para eventos: pub/sub **fire-and-forget** entre
flows. El aislamiento es por **namespace en el nombre del evento**, estilo clave
de S3 — los `/` son solo parte del nombre, no contenedores:

```
"ventas/order_created"   ← un namespace
"inventario/stock_low"   ← otro
"tick"                   ← namespace global
```

- **Matching exacto** por el nombre completo (namespace incluido). El namespace
  es **explícito en el `event_name`** que el usuario escribe en el JSON; emisor
  y receptor deben usar el mismo string. El broker no conoce `state_path`.
- **Fire-and-forget**: `publish` despacha a los suscriptores actuales y olvida.
  No persiste mensajes — si nadie escucha, el evento se pierde.
- `publish_count(event_name)` expone cuántas veces se publicó (introspección).

**Flujo emisor → receptor:**
- `EmitEvent` (nodo) → `ctx.emit_event(name, payload)` → `broker.publish`.
- El broker lanza `_run_event_flow.remote(source, name, payload)` por cada flow
  suscrito (registrado con `serve_events`).
- `_run_event_flow` ejecuta el flow receptor pasando `{"payload": payload}` como
  flow_input. El engine escribe los flow_inputs como outputs del entry node, así
  el output `payload` del `OnEvent` queda poblado y el subgrafo lo consume como
  `"on.payload"`.

`OnEvent` lleva `event_name` como configuración estática (a qué evento se
suscribe); no es un input de ejecución.

---

## GraphState y graph_id

Cada ejecución de un flow crea **un solo** actor `GraphState` con nombre único:

```python
graph_id = str(uuid.uuid4())
state = GraphState.options(name=f"gs_{graph_id}", lifetime="detached").remote(var_defaults)
```

El `graph_id` se propaga a:
- `_SerializableExecContext` — los `@ray_node` lo usan para resolver el state por nombre
- `_run_subgraph_task` — las ramas paralelas reciben el handle del state directamente

Esto permite que múltiples grafos corran simultáneamente sin colisiones, y que cualquier actor Ray del cluster acceda al estado de su grafo via `ray.get_actor(f"gs_{graph_id}")`.

### Aislamiento de variables por `state_path` (estilo bucket S3)

El único `GraphState` guarda **todas** las variables del flow y sus subgrafos. El aislamiento de un subflow `isolated=True` no usa actores separados: se logra **prefijando la clave de la variable** con el `state_path` del nodo, como una clave de S3 en un solo bucket (`_var_key` en `executor.py`):

```
contador            ← variable del flow raíz (state_path None)
padre/sub/contador  ← misma variable en un subflow aislado (state_path "padre/sub")
```

- `isolated=True` → `state_path` propio → claves prefijadas → no pisa al padre.
- `isolated=False` → `state_path` heredado → mismas claves → comparte con el padre.
- Los **node outputs** (pins) no se prefijan: sus ids ya son únicos por ruta (`padre/sub/add`).
- Los defaults de un subflow aislado se siembran lazy al entrar (`_fire_callflow_node`).

Al terminar el flow, el engine destruye el `GraphState` con `ray.kill(state)`.

---

## Archivos clave

| Archivo | Responsabilidad |
|---|---|
| `rayflow/nodes/decorators.py` | `@ray_node`, `@engine_node`, `ExecContext`, `_SerializableExecContext`, descriptores de pin, `NodeMeta` |
| `rayflow/engine/executor.py` | `FlowEngine` (clase Python local) + `FlowExecutor` (wrapper), `_run_subgraph_task` (ramas de Parallel, reusa `FlowEngine` en modo subgrafo) |
| `rayflow/build/validator.py` | `flatten()` (aplana CallFlow inline a namespace plano), valida el flow y produce `BuiltFlow` con `exec_targets` resueltos |
| `rayflow/schema/models.py` | `FlowDef`, `NodeDef` (incl. campos del flatten: `state_path`, `subflow_of`, `iface`, `subflow_entry`/`subflow_exit`, `subflow_vars`, `flow_name`), `PinKind` |
| `rayflow/types.py` | Sistema de tipos de data pins, `parse_type`, `compatible` |
| `rayflow/state/actor.py` | `GraphState` — actor Ray nombrado con variables y outputs de nodos |
| `rayflow/events/bus.py` | `EventBroker` — actor global pub/sub fire-and-forget, namespaced por nombre de evento |
| `rayflow/nodes/builtin/` | Nodos builtin organizados por dominio |
| `rayflow/nodes/builtin/flow.py` | `CallFlow` — subgrafos compartidos e isolados |
| `rayflow/api.py` | API pública: `run`, `run_async`, `serve_events`, `stop` |
| `rayflow/server.py` | API REST (FastAPI): carga/valida flows y los sirve como endpoints HTTP |
| `rayflow/cli.py` + `__main__.py` | CLI: `rayflow serve --file …` levanta la API REST |
