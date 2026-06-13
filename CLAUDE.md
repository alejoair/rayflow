# Rayflow — Contexto del proyecto

Rayflow es un motor de ejecución de grafos de nodos al estilo Unreal Engine Blueprints, construido sobre Ray. Los flows se definen como JSON y se ejecutan distribuyendo nodos como actores/tasks de Ray.

**Requisitos**: Python >= 3.10, Ray >= 2.9.

---

## Estructura del repositorio

```
rayflow/
├── rayflow/
│   ├── __init__.py            # Exporta: run, run_async, serve_events, stop
│   ├── __main__.py            # Punto de entrada: python -m rayflow
│   ├── api.py                 # API pública: run(), run_async(), serve_events(), stop()
│   ├── cli.py                 # CLI: rayflow serve --file …
│   ├── server.py              # API REST con FastAPI
│   ├── types.py               # Sistema de tipos de pines: parse_type, compatible
│   ├── workspace.py           # Convenciones de directorio: custom_nodes/, flows/
│   ├── build/
│   │   └── validator.py       # flatten(), build(), BuiltFlow, ResolvedNode
│   ├── engine/
│   │   └── executor.py        # FlowEngine (actor Ray async), FlowExecutor (wrapper síncrono)
│   ├── nodes/
│   │   ├── decorators.py      # @ray_node, @engine_node, @parallel_node, ExecContext, NodeMeta
│   │   ├── loader.py          # NodeCatalog: descubrimiento y registro de nodos
│   │   ├── registry.py        # Singleton del catálogo global
│   │   └── builtin/
│   │       ├── control.py     # OnStart, FlowInput, FlowOutput, Branch, Sequence, ForEach, Parallel, Map
│   │       ├── flow.py        # CallFlow (subgrafo inline)
│   │       ├── variables.py   # Get, Set
│   │       ├── events.py      # OnEvent, EmitEvent
│   │       ├── math.py        # Add, GreaterThan
│   │       └── cast.py        # ToInt, ToFloat, ToStr, ToBool
│   ├── schema/
│   │   ├── models.py          # FlowDef, NodeDef, VariableDef
│   │   └── loader.py          # load_flow() desde JSON
│   ├── state/
│   │   └── actor.py           # GraphState — actor Ray nombrado
│   └── events/
│       └── bus.py             # EventBroker — actor global pub/sub
├── tests/                     # Suite de tests (pytest)
├── examples/                  # Flows JSON de ejemplo
├── pyproject.toml
└── CLAUDE.md
```

---

## Workflow de desarrollo

```bash
# Instalar en modo editable con todas las dependencias de desarrollo
pip install -e ".[dev]"

# Ejecutar tests
pytest

# Ejecutar un flow directamente
python -c "import rayflow; print(rayflow.run('flows/suma.json', x=3, y=7))"

# Levantar servidor REST
rayflow serve --file flows/suma.json --port 8000
# o equivalentemente:
python -m rayflow serve --file flows/suma.json --port 8000
```

---

## Workspace y custom nodes

`workspace.py` define las convenciones del directorio de trabajo. El directorio donde se lanza rayflow es la raíz del workspace:

```
<cwd>/
├── custom_nodes/    ← paquete Python de nodos personalizados (auto-descubierto)
│   └── __init__.py
└── flows/           ← flows JSON, resueltos por nombre simple
```

- `custom_nodes/` se distribuye a los workers Ray via `runtime_env` (`py_modules`). Los nodos deben importarse como `custom_nodes.<modulo>` para ser serializables cross-proceso.
- `flows/` permite pasar solo el nombre (sin path): `rayflow.run("suma")` resuelve a `flows/suma.json`.
- `ensure_workspace()` crea ambas carpetas si no existen.
- `runtime_env()` devuelve el dict para `ray.init` solo si hay `.py` de nodos además del `__init__.py`.

### Diferencia crítica en carga de nodos

| Método | Uso | Serializable en workers |
|---|---|---|
| `NodeCatalog.load_custom_nodes_package()` | `custom_nodes/` del cwd | **Sí** (`custom_nodes.<mod>`) |
| `NodeCatalog.load_directory(path)` | Directorios arbitrarios | No (nombres sintéticos) |

Para distribución a workers Ray, usar siempre `custom_nodes/`. Para tests locales o nodos del driver, `load_directory` o registrar directamente con `catalog.register(cls)`.

---

## Tipos de nodo

Todos los tipos de nodo usan el mismo `ExecContext` unificado y el mismo contrato: `ctx.set_output()` para data outputs, `await ctx.fire()` para exec outputs. La distinción `@engine_node` vs `@ray_node` es solo sobre **dónde corre el nodo**, no sobre sus capacidades.

### `@ray_node`
Ejecutado como actor o task de Ray (proceso remoto, distribuido).

- **Con exec pins** → actor Ray (estado persistente entre llamadas). `run()` es `async def`.
- **Sin exec pins** → task Ray puro (función sin estado, evaluado bajo demanda). `run()` se llama sin `ctx`.
- El decorador inyecta `run_with_ctx(ctx, **inputs)` que llama `run()` y lo awaita.

```python
@ray_node
class Add:
    exec_in = ExecInput()
    a = Input("int", default=0)
    b = Input("int", default=0)
    result = Output("int")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, a: int, b: int) -> None:
        ctx.set_output("result", a + b)
        await ctx.fire("exec_out")
```

### `@engine_node`
Ejecutado localmente por el engine (mismo proceso asyncio, sin overhead de Ray).

- `run()` puede ser `def` o `async def`; si es async, el engine lo awaita.
- `await ctx.fire(pin)` es **bloqueante**: ejecuta el subgrafo conectado completo antes de retornar.
- **Con exec pins**: `ctx.set_output(pin, value)` es el canal de data outputs.
- **Pure (sin exec pins)**: `return {"pin": value}` funciona porque van por `_eval_pure_engine_node`.
- Llama `set_output` **antes** del `await fire` para que el subgrafo ya pueda leer el valor.
- Concurrencia: `await asyncio.gather(ctx.fire("a"), ctx.fire("b"))` lanza subgrafos concurrentemente.

```python
@engine_node
class Branch:
    exec_in = ExecInput()
    condition = Input("bool", default=False)
    true = ExecOutput()
    false = ExecOutput()

    async def run(self, ctx: ExecContext, condition: bool) -> None:
        await ctx.fire("true" if condition else "false")

@engine_node
class ForEach:
    exec_in = ExecInput()
    array = Input("list", default=None)
    loop_body = ExecOutput()
    completed = ExecOutput()
    element = Output("Any")
    index = Output("int")

    async def run(self, ctx: ExecContext, array: list) -> None:
        for i, element in enumerate(array or []):
            ctx.set_output("element", element)
            ctx.set_output("index", i)
            await ctx.fire("loop_body")
        await ctx.fire("completed")
```

### `@parallel_node`
Alias de `@engine_node` para fork/join explícito. El motor lo trata igual que un `@engine_node`. Solo existe para el nodo builtin `Parallel`; para la mayoría de casos, el fan-out nativo + AND en `exec_in` es suficiente.

---

## ExecContext

Contexto **unificado y serializable** pasado como primer argumento a `run()` en todos los nodos.

```python
class ExecContext:
    async def fire(self, pin_name: str) -> None            # bloqueante: ejecuta subgrafo completo
    def set_output(self, pin_name: str, value: Any)        # escribe data output en GraphState
    def get_variable(self, name: str) -> Any               # lee variable del GraphState
    def set_variable(self, name: str, value: Any)          # escribe variable en el GraphState
    def emit_event(self, event_name: str, payload: Any)    # publica al EventBroker
    async def exec_outputs_except(self, *exclude: str) -> list[str]  # descubre exec outputs del nodo
```

### Serialización y resolución de handles

`ExecContext` solo guarda strings (`node_id`, `graph_id`, `state_path`). Los handles Ray se adquieren bajo demanda y se cachean localmente:

```python
def __getstate__(self):
    # Excluye handles y callbacks — se reacquieren en el proceso destino
    return {"_node_id": ..., "_graph_id": ..., "_state_path": ...,
            "_engine_handle": None, "_state_handle": None, "_output_writer": None}
```

- `fire()` → `await engine_actor.fire.remote(node_id, pin_name)` — localiza el engine por `ray.get_actor(f"engine_{graph_id}")`
- `set_output()` en **`@engine_node`**: usa `_output_writer` callback (lambda al engine), **sin llamada remota** (evita self-call deadlock en el event loop del actor engine)
- `set_output()` en **`@ray_node`**: `ray.get(engine.set_output.remote(...))` — llama al engine desde el proceso del actor
- `get_variable()` / `set_variable()`: acceden directamente al `GraphState` actor (`gs_{graph_id}`) sin pasar por el engine

**En `@ray_node` pure (sin exec pins)**: `run()` se llama sin `ctx` desde `_make_data_task`.

---

## Pin implícito `meta`

Todos los nodos exponen automáticamente un data output `meta: dict`, inyectado por el engine tras cada ejecución. No se declara en el nodo.

```python
{
    "id": "add_1",               # id de la instancia
    "type": "Add",               # nombre de la clase del nodo
    "flow": "mi_flow",           # nombre del flow declarante
    "started_at": 1718100000.123,
    "duration_ms": 45.2,
}
```

El engine escribe `meta` con `duration_ms=0.0` **antes** de llamar `run()`, y lo actualiza con el timing real **después**. Esto evita que downstream lea `None` cuando un nodo dispara `ctx.fire()` durante su propia ejecución.

El validator reconoce `"node_id.meta"` como referencia válida (tipo `"dict"`).

---

## Tipos de pines

| Descriptor | Tipo | Descripción |
|---|---|---|
| `Input("int", default=0)` | data input | Recibe un valor. Tipo canónico string. |
| `Output("str")` | data output | Produce un valor. |
| `ExecInput()` | exec input | Recibe señal de ejecución. |
| `ExecOutput()` | exec output | Dispara señal de ejecución. |

**Tipos permitidos**: `int`, `float`, `str`, `bool`, `list`, `dict`, `Any`, `list[T]`, `dict[str, T]`.

La compatibilidad es **estricta**: no hay coerción implícita. `int` y `float` son incompatibles. Usar nodos `ToInt`, `ToFloat`, `ToStr`, `ToBool` para casteos explícitos.

Los tipos de pines son siempre **strings canónicos** — nunca clases Python ni anotaciones de tipo.

---

## Engine — ciclo de ejecución

`FlowEngine` es un **actor Ray async** (`@ray.remote`) con nombre `engine_{graph_id}` en namespace `"rayflow"`. `FlowExecutor` es un wrapper síncrono que:

1. Crea los actores `@ray_node` en el proceso del **driver** (donde `py_class` está disponible directamente).
2. Pasa los handles al constructor de `FlowEngine` (los handles son serializables).
3. Llama `ray.get(engine.execute.remote())` y limpia los actores al terminar.

```
_fire(node_id) — método async del actor FlowEngine
  ├─ subflow_entry != None  → _fire_callflow_node()  (CallFlow shell, inline)
  ├─ is_engine_node / is_parallel → _fire_engine_node()  (local, instancia Python)
  └─ @ray_node exec         → _fire_ray_node()  (actor Ray remoto)
```

- **`_fire_callflow_node()`**: siembra variables del subflow `isolated`, dispara `subflow_entry` (bloqueante), reúne los inputs del `subflow_exit` como dict `result`, continúa hacia `exec_out`.
- **`_fire_engine_node()`**: instancia el nodo localmente, crea `ExecContext` con `_output_writer` (callback directo a `_write_node_outputs`), llama `await run(ctx, **inputs)`.
- **`_fire_ray_node()`**: llama `await actor.run_with_ctx.remote(ctx, **resolved)`, cede el event loop del engine mientras espera — permitiendo re-entrancy.

### Re-entrancy del actor engine

El `FlowEngine` es un async actor: cuando está suspendido en `await actor.run_with_ctx.remote(...)`, su event loop está libre para procesar nuevas llamadas remotas. Esto habilita que los `@ray_node` llamen `engine.fire.remote()` y `engine.set_output.remote()` durante su propio `run()` — sin deadlock. El engine procesa esas llamadas mientras espera el resultado del nodo.

### Ciclo de vida de actores `@ray_node`

Los actores se crean en `FlowExecutor.execute()` (proceso driver) con nombre único `{node_id}_{graph_id}` en namespace `"rayflow"`. Se destruyen con `ray.kill()` al terminar. Todos los nodos del mismo flow comparten el mismo `FlowEngine` y los mismos handles.

- Los actores **no** se crean en tiempo de ejecución ni por rama — uno por nodo exec por ejecución.
- `NodeMeta.__getstate__/__setstate__` excluye `ray_handle` del pickle y lo reconstruye en el worker a partir de `py_class`.
- Clases `@ray_node` definidas localmente (ej. en tests) deben registrarse en el catálogo antes de compilar el flow.

### Resolución de inputs (`_resolve_pin`)

1. Output vigente en `GraphState` (path normal post-ejecución).
2a. `@engine_node` pure (sin exec pins) → `_eval_pure_engine_node()` bajo demanda.
2b. `@ray_node` pure (sin exec pins) → task Ray bajo demanda.
3. Default del pin consumidor (fallback).

### Pure nodes (nodos lazy)

Un nodo **sin exec pins** se evalúa bajo demanda cuando otro nodo necesita su output.

```python
@engine_node  # pure: sin ExecInput ni ExecOutput
class Get:
    variable_name = Input("str", default="")
    value = Output("Any")

    def run(self, ctx: ExecContext, variable_name: str) -> dict:
        return {"value": ctx.get_variable(variable_name)}
```

Para pure `@engine_node`: `return {"pin": value}` es válido (va por `_eval_pure_engine_node`).
Para pure `@ray_node`: `run(**inputs)` sin `ctx`.

### AND/OR en `exec_in` múltiple

- **`"exec_in": "a"`** — un solo predecesor, comportamiento estándar.
- **`"exec_in": ["a", "b"]`** — **AND**: espera que todos los predecesores completen.
- **`"exec_in": {"or": ["a", "b"]}`** — **OR**: dispara con el primero que llegue.

El engine usa `_exec_arrivals: dict[str, set[str]]` para AND-joins. En OR, el nodo dispara inmediatamente sin conteo.

```json
{ "id": "join", "type": "FlowOutput", "exec_in": ["a", "b"], "inputs": {"r0": "a.result", "r1": "b.result"} }
{ "id": "merge", "exec_in": {"or": ["branch.true", "branch.false"]} }
```

---

## Flatten — namespace plano de nodos

En build time, `flatten()` expande recursivamente cada `CallFlow` **inline** en un único grafo plano. No hay subflows ni ejecutores anidados en runtime: todo es un namespace plano con ids tipo ruta S3.

```
padre/add_1
padre/sub/add_1          ← nodo de un CallFlow "sub"
padre/sub/sub2/add_1     ← CallFlow anidado
```

- Reutiliza `FlowInput`/`FlowOutput` del subflow como puntos de empalme.
- El `CallFlow` shell guarda `subflow_entry`/`subflow_exit` y `subflow_vars`.
- **Subflow estático**: el input `flow` debe ser un dict inline o ruta conocida en build time.

Campos en `NodeDef` producidos por flatten: `state_path`, `subflow_of`, `iface`, `subflow_entry`, `subflow_exit`, `subflow_vars`, `flow_name`.

---

## Paralelismo

### Fan-out exec — concurrente por defecto

Múltiples nodos con el mismo `exec_in` se disparan **concurrentemente** via `asyncio.gather`:

```json
{ "id": "nodo_a", "exec_in": "origen" },
{ "id": "nodo_b", "exec_in": "origen" }
```

`@ray_node` corren en paralelo real (procesos Ray); `@engine_node` se intercalan cooperativamente en el event loop.

**Condición de carrera**: dos ramas que escriben la misma variable con `Set` producen resultado no determinista — error de diseño del flow.

### Nodo `Parallel` — fork/join explícito

```json
{ "id": "par", "type": "Parallel", "exec_in": "entry" },
{ "id": "rama_a", "type": "ProcessA", "exec_in": "par.branch_0" },
{ "id": "rama_b", "type": "ProcessB", "exec_in": "par.branch_1" },
{ "id": "merge",  "type": "Merge",    "exec_in": "par.joined" }
```

Las ramas se inyectan dinámicamente en build a partir del wiring del JSON. `Parallel.run()` usa `await ctx.exec_outputs_except("joined")` para descubrir sus pines de rama.

---

## Nodos builtin

| Nodo | Decorator | Exec pins | Descripción |
|---|---|---|---|
| `OnStart` | `@engine_node` | sí | Punto de entrada sin parámetros |
| `FlowInput` | `@engine_node` | sí | Punto de entrada con parámetros del flow |
| `FlowOutput` | `@engine_node` | sí | Punto de salida del flow |
| `OnEvent` | `@engine_node` | sí | Entrada por evento; `event_name` es config estática; expone `payload` |
| `EmitEvent` | `@engine_node` | sí | Publica al EventBroker via `ctx.emit_event()` |
| `Branch` | `@engine_node` | sí | Desvío condicional `true`/`false` |
| `Sequence` | `@engine_node` | sí | Dispara `then_0`, `then_1`, `then_2` en orden secuencial |
| `Parallel` | `@parallel_node` | sí | Fork/join — lanza N ramas concurrentes; pin `joined` al terminar todas |
| `ForEach` | `@engine_node` | sí | Itera array; `loop_body` por elemento (bloqueante); `completed` al final |
| `Map` | `@engine_node` | sí | Aplica un nodo del catálogo a cada elemento; devuelve `result: list` |
| `Get` | `@engine_node` | **no** | Lee variable — pure node, evaluado bajo demanda |
| `Set` | `@engine_node` | sí | Escribe variable via `ctx.set_variable()` |
| `CallFlow` | `@engine_node` | sí | Ejecuta subflow inline. `isolated=True`: variables en namespace propio. Output `result: dict` |
| `Add` | `@ray_node` | sí | Suma dos enteros |
| `GreaterThan` | `@ray_node` | sí | Compara dos enteros, devuelve bool |
| `ToInt/ToFloat/ToStr/ToBool` | `@ray_node` | sí | Casteos explícitos |

### Nodo Map

Aplica un nodo del catálogo a cada elemento de un array. El elemento se pasa al **primer data input** del nodo; los demás inputs usan sus defaults declarados. El **primer data output** de cada invocación se recoge en `result: list`.

Funciona con cualquier nodo (pure o exec, engine o ray_node). El exec flow del nodo aplicado se ignora — Map solo captura datos via `_MapCaptureCtx`.

```json
{"id": "m", "type": "Map", "exec_in": "entry",
 "inputs": {"array": "entry.items", "node_type": "ToStr"}}
```

`node_type` es un **string literal** en el JSON (nombre del tipo en el catálogo). Error en runtime si el tipo no existe o no tiene inputs/outputs.

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

`exec_in` acepta:
- `"node_id"` — exec output por defecto del nodo fuente.
- `"node_id.pin_name"` — exec output específico (ej. `"branch.true"`).
- `["a", "b"]` — AND-join.
- `{"or": ["a", "b"]}` — OR-join.

---

## API pública

```python
import rayflow

# Síncrono
outputs = rayflow.run("flow.json", x=5, y=3)
outputs = rayflow.run("suma", x=5)  # resuelve flows/suma.json en el workspace

# Asíncrono (devuelve ObjectRef de Ray)
ref = rayflow.run_async("flow.json", x=5)
outputs = ray.get(ref)

# Flow residente por eventos
graph_id = rayflow.serve_events("flow.json")
rayflow.stop(graph_id, ["mi_evento"])
```

Cada ejecución se aísla por un `graph_id` UUID propio — ejecuciones concurrentes no colisionan.

---

## API REST (CLI `rayflow serve`)

```bash
rayflow serve --file suma.json --file otro.json --port 8000
```

Carga y valida cada flow al arrancar (falla si un flow no compila o si dos comparten `name`).

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Healthcheck |
| `GET` | `/flows` | Lista flows servidos con su interfaz |
| `GET` | `/flows/{name}` | Interfaz de un flow |
| `POST` | `/flows/{name}/run` | Ejecuta el flow; body JSON = inputs; devuelve outputs |

FastAPI y uvicorn son dependencias requeridas incluidas en la instalación base.

---

## Sistema de eventos (EventBroker)

El `EventBroker` (`events/bus.py`) es un único actor Ray detached y global. Pub/sub **fire-and-forget** entre flows. El aislamiento es por **nombre exacto** del evento:

```
"ventas/order_created"   ← namespace "ventas"
"inventario/stock_low"
"tick"                   ← namespace global
```

- Matching **exacto** por nombre completo. Emisor y receptor deben usar el mismo string.
- No persiste mensajes — si nadie escucha, el evento se pierde.
- `publish_count(event_name)` para introspección.

**Flujo**: `EmitEvent` → `ctx.emit_event(name, payload)` → `broker.publish` → `_run_event_flow.remote()` por cada suscriptor.

`OnEvent` lleva `event_name` como configuración estática, no como input de ejecución.

---

## GraphState y graph_id

Cada ejecución crea un único actor `GraphState` con nombre único:

```python
graph_id = str(uuid.uuid4())
state = GraphState.options(name=f"gs_{graph_id}", namespace="rayflow", lifetime="detached").remote(var_defaults)
```

Destruido con `ray.kill(state)` al terminar el flow. Los tres actores por ejecución son:
- `gs_{graph_id}` — GraphState (variables + outputs de nodos)
- `engine_{graph_id}` — FlowEngine (orquestador)
- Uno por nodo `@ray_node` exec: `{node_id}_{graph_id}`

### Aislamiento de variables por `state_path`

Un único `GraphState` guarda todas las variables del flow y sus subgrafos. El aislamiento de subflows `isolated=True` se logra prefijando la clave con `state_path`:

```
contador            ← flow raíz (state_path None)
padre/sub/contador  ← subflow aislado (state_path "padre/sub")
```

- `isolated=True` → `state_path` propio → claves prefijadas → no pisa al padre.
- `isolated=False` → `state_path` heredado → comparte variables con el padre.
- `_var_key(state_path, var_name)` implementa el prefijado en `executor.py`.

**Limitación en `@ray_node`**: `ExecContext.get_variable(name)` en un worker remoto usa el `state_path` del ExecContext serializado. Si el nodo está dentro de un subflow aislado, el `state_path` está correctamente en el ctx serializado — funciona. Sin embargo, si `get_variable` es llamado directamente desde `run()` de un `@ray_node`, debe usarse el nombre completo de la variable (incluyendo el prefijo del subflow si aplica), porque el ctx ya lo prefija automáticamente.

---

## Convenciones del código

### Declaración de pines

Los tipos de pines son **siempre strings canónicos** — nunca clases Python:

```python
# Correcto
a = Input("int", default=0)
result = Output("list[str]")

# Incorrecto — nunca hacer esto
a = Input(int)  # ← error
```

### `@ray_node` y `@engine_node` con exec pins: mismo contrato

```python
@ray_node   # o @engine_node — mismo API
class MyNode:
    exec_in = ExecInput()
    value = Output("str")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, ...) -> None:
        ctx.set_output("value", "hola")  # ✓ antes del fire
        await ctx.fire("exec_out")
        # return {"value": "hola"}  ← RuntimeError en @engine_node; ignorado en @ray_node
```

### `@engine_node` pure (sin exec pins): usa `return`

```python
@engine_node
class Compute:
    x = Input("int", default=0)
    result = Output("int")

    def run(self, ctx: ExecContext, x: int) -> dict:
        return {"result": x * 2}  # ✓ correcto para pure nodes
```

### Nodos `@ray_node` deben ser serializables

Las clases definidas en tests o en `__main__` deben registrarse en el catálogo antes de compilar el flow. Para distribución a workers, colocar en `custom_nodes/` y usar `load_custom_nodes_package()`.

---

## Archivos clave

| Archivo | Responsabilidad |
|---|---|
| `rayflow/nodes/decorators.py` | `@ray_node`, `@engine_node`, `@parallel_node`, `ExecContext` (unificado), `NodeMeta`, `_MapCaptureCtx` |
| `rayflow/engine/executor.py` | `FlowEngine` (actor Ray async), `FlowExecutor` (wrapper síncrono), `_var_key`, AND-join vía `_exec_arrivals` |
| `rayflow/build/validator.py` | `flatten()`, `build()`, `BuiltFlow`, `ResolvedNode`, detección de ciclos |
| `rayflow/schema/models.py` | `FlowDef`, `NodeDef` (con campos del flatten), `VariableDef`, `PinKind` |
| `rayflow/types.py` | `parse_type`, `compatible`, tipos canónicos |
| `rayflow/state/actor.py` | `GraphState` — actor Ray con variables y outputs de nodos |
| `rayflow/events/bus.py` | `EventBroker` — actor global pub/sub fire-and-forget |
| `rayflow/nodes/builtin/` | Nodos builtin organizados por dominio |
| `rayflow/nodes/loader.py` | `NodeCatalog` — descubrimiento y registro |
| `rayflow/workspace.py` | Convenciones de directorio: `custom_nodes/`, `flows/` |
| `rayflow/api.py` | API pública: `run`, `run_async`, `serve_events`, `stop` |
| `rayflow/server.py` | API REST (FastAPI) |
| `rayflow/cli.py` + `__main__.py` | CLI: `rayflow serve --file …` |
