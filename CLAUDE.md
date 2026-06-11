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
```

En `@ray_node` viaja serializado al proceso del actor (`_SerializableExecContext`).
En `@engine_node` es local con callbacks al engine.

---

## Pin implícito `meta`

Todos los nodos (tanto `@ray_node` como `@engine_node`) exponen automáticamente un data output `meta` de tipo `dict`, inyectado por el engine tras cada ejecución. No se declara en el nodo — siempre está disponible.

```python
{
    "id": "add_1",        # id de la instancia en el grafo (definido por el usuario en el JSON)
    "type": "Add",        # nombre de la clase del nodo
    "flow": "mi_flow",    # nombre del flow que contiene el nodo
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

`FlowExecutor._run_loop()` mantiene una cola BFS de `node_id`s a disparar.

```
_fire(node_id)
  ├─ is_engine_node → _fire_engine_node()  (local, ctx.fire() bloqueante)
  └─ @ray_node      → _fire_ray_node()     (actor Ray, ctx acumula pins)
```

- **`_fire_engine_node()`**: instancia el nodo, crea `ExecContext` con callbacks locales, llama `run(ctx, **inputs)`. Cada `ctx.fire(pin)` llama `_run_loop(target)` síncronamente. Devuelve `[]` al BFS externo (los subgrafos ya se ejecutaron).
- **`_fire_ray_node()`**: llama `actor.run_with_ctx.remote(ctx, **inputs)`, hace `ray.get()`, recoge `fired_pins` del ctx devuelto, los traduce a `node_id`s via `exec_targets` y los encola en el BFS.

Los data outputs de cada nodo se escriben en `GraphState` (actor Ray) y se leen bajo demanda al resolver inputs de nodos posteriores.

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
Fork/join con paralelismo real vía Ray. Cada rama corre en su propio `FlowExecutor` parcial lanzado como task Ray (`_run_subgraph_task`), compartiendo el mismo `GraphState` actor.

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

---

## Nodos builtin

| Nodo | Tipo | Descripción |
|---|---|---|
| `OnStart` | `@engine_node` | Punto de entrada sin parámetros |
| `FlowInput` | `@engine_node` | Punto de entrada con parámetros |
| `FlowOutput` | `@engine_node` | Punto de salida del flow |
| `OnEvent` | `@engine_node` | Entrada por evento externo |
| `EmitEvent` | `@engine_node` | Emite evento al bus global |
| `Branch` | `@engine_node` | Desvío condicional true/false |
| `Sequence` | `@engine_node` | Dispara then_0/then_1/then_2 en orden |
| `Parallel` | `@parallel_node` | Fork/join — lanza branch_0/1/2 en paralelo, joined al terminar |
| `ForEach` | `@engine_node` | Itera array, dispara loop_body por elemento |
| `Get` | `@engine_node` | Lee variable del GraphState |
| `Set` | `@engine_node` | Escribe variable en el GraphState |
| `Add` | `@ray_node` | Suma dos enteros |
| `ToInt/ToFloat/ToStr/ToBool` | `@ray_node` | Casteos explícitos |

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

# Flow residente por eventos
graph_id = rayflow.serve("flow.json")
rayflow.stop(graph_id, ["mi_evento"])
```

---

## Archivos clave

| Archivo | Responsabilidad |
|---|---|
| `rayflow/nodes/decorators.py` | `@ray_node`, `@engine_node`, `ExecContext`, descriptores de pin, `NodeMeta` |
| `rayflow/engine/executor.py` | `FlowExecutor` — ciclo BFS, `_fire_engine_node`, `_fire_ray_node` |
| `rayflow/build/validator.py` | Valida el flow y produce `BuiltFlow` con `exec_targets` resueltos |
| `rayflow/schema/models.py` | `FlowDef`, `NodeDef`, `PinKind` |
| `rayflow/types.py` | Sistema de tipos de data pins, `parse_type`, `compatible` |
| `rayflow/state/actor.py` | `GraphState` — actor Ray con variables y outputs de nodos |
| `rayflow/nodes/builtin/` | Nodos builtin organizados por dominio |
| `rayflow/api.py` | API pública: `run`, `run_async`, `serve`, `stop` |
