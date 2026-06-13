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
│   │   └── executor.py        # FlowEngine (async), FlowExecutor (wrapper síncrono)
│   ├── nodes/
│   │   ├── decorators.py      # @ray_node, @engine_node, @parallel_node, ExecContext
│   │   ├── loader.py          # NodeCatalog: descubrimiento y registro de nodos
│   │   ├── registry.py        # Singleton del catálogo global
│   │   └── builtin/
│   │       ├── control.py     # OnStart, FlowInput, FlowOutput, Branch, Sequence, ForEach, Parallel
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

### `@ray_node`
Ejecutado como actor o task de Ray (proceso remoto, distribuido).

- **Con exec pins** → actor Ray (estado persistente entre llamadas).
- **Sin exec pins** → task Ray puro (función sin estado, evaluado bajo demanda).
- `ctx.fire(pin)` solo **acumula** el nombre en `ctx.fired`; el engine los recoge al terminar `run()`.
- El decorador inyecta automáticamente `run_with_ctx(ctx, **inputs)` → devuelve `(fired_pins, outputs_dict)`.

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

- `run()` puede ser `def` o `async def`; si es async, el engine lo awaita.
- `await ctx.fire(pin)` es **bloqueante**: ejecuta el subgrafo conectado completo antes de retornar.
- **Para nodos con exec pins**: `ctx.set_output(pin, value)` es el **único** canal de data outputs. `return` con datos lanza `RuntimeError`.
- **Para pure nodes (sin exec pins)**: `return {"pin": value}` funciona correctamente porque van por `_eval_pure_engine_node`, no por `_fire_engine_node`.
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
Especialización de `@engine_node` para fork/join explícito. El engine trata las ramas (`branch_0`, `branch_1`, …) con `asyncio.gather`. El pin `joined` se dispara cuando todas las ramas completan. Solo existe para el nodo builtin `Parallel`; para la mayoría de casos, el fan-out nativo + AND en `exec_in` es suficiente.

---

## ExecContext

Pasado como primer argumento a `run()` en ambos tipos de nodo.

```python
class ExecContext:
    async def fire(self, pin_name: str) -> None      # await en @engine_node; acumula en @ray_node
    def set_output(self, pin_name: str, value: Any)  # obligatorio en @engine_node con exec pins
    def get_variable(self, name: str) -> Any         # lee variable del GraphState
    def set_variable(self, name: str, value: Any)    # escribe variable en el GraphState
    def emit_event(self, event_name: str, payload: Any = None)  # publica al EventBroker
```

**En `@ray_node` con exec pins** usa `_SerializableExecContext` (serializable, viaja al proceso del actor):
- `fire()` solo appenda a `self.fired` (no async, no ejecuta subgrafos).
- `set_output()` es **no-op** (los outputs se devuelven via `return`).
- `get_variable(name)` / `set_variable(name, value)` resuelven el `GraphState` vía `ray.get_actor(f"gs_{graph_id}")`. **Importante**: no usan `state_path` — el nombre de la variable debe ser su clave completa (sin prefijo del subflow).
- `emit_event()` publica al broker via `get_event_broker()`.

**En `@engine_node`** usa callbacks directos al engine (locales, async-aware).

**En `@ray_node` sin exec pins** (pure task): no recibe `ctx` — `_make_data_task` llama a `run(**inputs)` sin contexto.

---

## Pin implícito `meta`

Todos los nodos exponen automáticamente un data output `meta: dict`, inyectado por el engine tras cada ejecución. No se declara en el nodo.

```python
{
    "id": "add_1",               # id de la instancia (ruta plana si viene de CallFlow)
    "type": "Add",               # nombre de la clase del nodo
    "flow": "mi_flow",           # nombre del flow DECLARANTE (el subflow, no el raíz)
    "started_at": 1718100000.123,
    "duration_ms": 45.2,
}
```

El validator reconoce `"node_id.meta"` como referencia válida (caso especial en `build/validator.py` donde `src_pin == "meta"` asigna tipo `"dict"`).

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

`FlowEngine` es una clase Python local (no actor Ray). `FlowExecutor` es un wrapper fino síncrono para compatibilidad con la API pública. El motor es completamente **async**: `execute()` lanza `asyncio.run(_run_and_collect())` como borde sync→async.

```
_fire(node_id)
  ├─ subflow_entry != None  → _fire_callflow_node()  (CallFlow shell, inline)
  ├─ is_parallel            → _fire_parallel_node()  (fork/join vía asyncio.gather)
  ├─ is_engine_node         → _fire_engine_node()    (local, await ctx.fire() bloqueante)
  └─ @ray_node              → _fire_ray_node()       (actor Ray, await result_ref)
```

- **`_fire_callflow_node()`**: siembra variables del subflow `isolated`, dispara `subflow_entry` (bloqueante), reúne los inputs resueltos del `subflow_exit` como dict `result`, continúa hacia `exec_out`.
- **`_fire_engine_node()`**: instancia el nodo, construye `ExecContext` con callbacks async locales, llama `await run(ctx, **inputs)`. Si `run()` retorna un dict no-vacío, lanza `RuntimeError`.
- **`_fire_ray_node()`**: llama `actor.run_with_ctx.remote(ctx, **resolved)`, awaita el `ObjectRef` (cede el event loop), recoge `(fired_pins, outputs)` y los traduce a `node_id`s via `exec_targets`.
- **`_fire_parallel_node()`**: lanza todas las ramas `branch_N` con `asyncio.gather`, luego retorna los targets de `joined`.

Los data outputs de cada nodo se escriben en `GraphState` y se leen bajo demanda al resolver inputs posteriores.

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
Para pure `@ray_node`: la función recibe solo `**inputs` (sin `ctx`).

### AND/OR en `exec_in` múltiple

- **`"exec_in": "a"`** — un solo predecesor, comportamiento estándar.
- **`"exec_in": ["a", "b"]`** — **AND**: espera que todos los predecesores completen.
- **`"exec_in": {"or": ["a", "b"]}`** — **OR**: dispara con el primero que llegue.

El engine usa `_exec_arrivals: dict[str, set[str]]` para AND-joins. En OR, el nodo dispara inmediatamente sin conteo.

```json
{ "id": "join", "type": "FlowOutput", "exec_in": ["a", "b"], "inputs": {"r0": "a.result", "r1": "b.result"} }
{ "id": "merge", "exec_in": {"or": ["branch.true", "branch.false"]} }
```

### Ciclo de vida de actores `@ray_node`

Los actores se crean **una sola vez** al inicio en `FlowEngine._spawn_actors()`, con nombre único `{node_id}_{graph_id}` en namespace `"rayflow"`. Se destruyen con `ray.kill()` al terminar. Las ramas del `Parallel` y los subgrafos del mismo flow **comparten** el mismo `FlowEngine` y acceden a los mismos handles.

- Los actores **no** se crean en tiempo de ejecución ni por rama — singleton por flow.
- `NodeMeta.__getstate__/__setstate__` excluye `ray_handle` del pickle y lo reconstruye en el worker a partir de `py_class`.
- Clases `@ray_node` definidas localmente (ej. en tests) deben registrarse en el catálogo antes de compilar el flow.

---

## Flatten — namespace plano de nodos

En build time, `flatten()` expande recursivamente cada `CallFlow` **inline** en un único grafo plano. No hay subflows ni ejecutores anidados en runtime: todo es un namespace plano con ids tipo ruta S3 (`/` es parte del nombre, no un contenedor).

```
padre/add_1
padre/sub/add_1          ← nodo de un CallFlow "sub"
padre/sub/sub2/add_1     ← CallFlow anidado
```

- Reutiliza `FlowInput`/`FlowOutput` del subflow como puntos de empalme — sin nodos builtin implícitos nuevos.
- El `CallFlow` shell guarda `subflow_entry`/`subflow_exit` (ids del entry/exit del subgrafo) y `subflow_vars` (variables del subflow aislado a sembrar).
- **Subflow estático**: el input `flow` debe ser un dict inline o ruta conocida en build. No se puede elegir el subflow en runtime.

Campos en `NodeDef` producidos por flatten: `state_path`, `subflow_of`, `iface`, `subflow_entry`, `subflow_exit`, `subflow_vars`, `flow_name`.

---

## Paralelismo

### Fan-out exec — concurrente por defecto

Múltiples nodos con el mismo `exec_in` se disparan **concurrentemente** via `asyncio.gather`:

```json
{ "id": "nodo_a", "exec_in": "origen" },
{ "id": "nodo_b", "exec_in": "origen" }
```

`exec_targets` en `ResolvedNode` es `dict[str, list[str]]`. `@ray_node` corren en paralelo real (procesos Ray); `@engine_node` se intercalan cooperativamente en el event loop.

**Condición de carrera**: dos ramas que escriben la misma variable con `Set` producen resultado no determinista — error de diseño del flow.

### Nodo `Parallel` — fork/join explícito

```json
{ "id": "par", "type": "Parallel", "exec_in": "entry" },
{ "id": "rama_a", "type": "ProcessA", "exec_in": "par.branch_0" },
{ "id": "rama_b", "type": "ProcessB", "exec_in": "par.branch_1" },
{ "id": "merge",  "type": "Merge",    "exec_in": "par.joined" }
```

Las ramas se inyectan dinámicamente en build a partir del wiring del JSON.

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
| `Get` | `@engine_node` | **no** | Lee variable — pure node, evaluado bajo demanda |
| `Set` | `@engine_node` | sí | Escribe variable via `ctx.set_variable()` |
| `CallFlow` | `@engine_node` | sí | Ejecuta subflow inline. `isolated=True`: variables en namespace propio. Output `result: dict` |
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

Requiere: `pip install 'rayflow[serve]'` (FastAPI + uvicorn).

---

## Sistema de eventos (EventBroker)

El `EventBroker` (`events/bus.py`) es un único actor Ray detached y global. Pub/sub **fire-and-forget** entre flows. El aislamiento es por **nombre exacto** del evento (namespace por convención, no por estructura):

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

Destruido con `ray.kill(state)` al terminar el flow.

### Aislamiento de variables por `state_path`

Un único `GraphState` guarda todas las variables del flow y sus subgrafos. El aislamiento de subflows `isolated=True` se logra prefijando la clave con `state_path` (estilo bucket S3):

```
contador            ← flow raíz (state_path None)
padre/sub/contador  ← subflow aislado (state_path "padre/sub")
```

- `isolated=True` → `state_path` propio → claves prefijadas → no pisa al padre.
- `isolated=False` → `state_path` heredado → comparte variables con el padre.
- Los outputs de nodos no se prefijan (su id ya es único como ruta).
- `_var_key(state_path, var_name)` implementa el prefijado en `executor.py`.

**Limitación en `@ray_node`**: `_SerializableExecContext.get_variable(name)` pasa `name` directamente al actor de estado, sin prefijo de `state_path`. Los actores Ray no conocen el subflow en el que están.

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

### `@engine_node` con exec pins: solo `ctx.set_output()`

```python
@engine_node
class MyNode:
    exec_in = ExecInput()
    value = Output("str")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, ...) -> None:
        ctx.set_output("value", "hola")  # ✓ correcto
        await ctx.fire("exec_out")
        # return {"value": "hola"}  ← RuntimeError
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
| `rayflow/nodes/decorators.py` | `@ray_node`, `@engine_node`, `@parallel_node`, `ExecContext`, `_SerializableExecContext`, descriptores de pin, `NodeMeta` |
| `rayflow/engine/executor.py` | `FlowEngine` (motor async), `FlowExecutor` (wrapper síncrono), `_var_key`, AND-join vía `_exec_arrivals` |
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
