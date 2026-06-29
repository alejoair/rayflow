# CLAUDE.md

Guía para Claude Code al trabajar en este repositorio.

## Carpeta de pruebas

Los flows y nodos custom de prueba viven en `C:\Users\alejandro.cuartas\Desktop\rayflow_sandbox\`:
- `flows/` — flows JSON de prueba (no en el repo de Rayflow)
- `custom_nodes/` — nodos custom de prueba del usuario

Al lanzar el servidor desde el sandbox, Ray y el editor los detectan automáticamente:
```bash
cd C:\Users\alejandro.cuartas\Desktop\rayflow_sandbox
rayflow serve --port 8000
```

## Comandos de desarrollo

```bash
# Instalar en modo editable
pip install -e .

# Lanzar el servidor (editor visual + API REST)
rayflow serve --port 8000
# o equivalentemente:
python -m rayflow serve --port 8000

# Con flows precargados
rayflow serve --file flows/suma.json --port 8000

# Con logs de actores Ray (prints incluidos) redirigidos a consola
rayflow serve --port 8000 --debug

# Ejecutar tests
pip install -e ".[dev]"
pytest tests/
```

El servidor sirve:
- Editor visual en `http://localhost:8000/editor`
- API REST en `http://localhost:8000/flows`
- Health check en `http://localhost:8000/health`

## Arquitectura general

```
Editor visual (browser) ←→ FastAPI (rayflow/server.py) ←→ Ray actors/tasks
         ↓                           ↓
  editor/frontend/ (React+Vite)   rayflow/engine/executor.py
   → build a editor/static/dist/  (lo que sirve el server)
```

### Principios de diseño

1. **Un nodo = una clase Python** decorada con `@ray_node` o `@engine_node`
2. **Namespace plano**: `flatten()` expande subflows inline en build time (ids tipo `padre/sub/nodo`)
3. **Ejecución secuencial de control, paralela de datos**: exec pins son secuenciales; data pins se evalúan en paralelo vía Ray
4. **Tipos siempre strings canónicos**: `"int"`, `"str"`, `"list[str]"` — nunca clases Python

## Frontend (editor visual)

### Stack
- **React 18** + **TypeScript** + **Vite**
- **@xyflow/react 12**: canvas de grafos
- **shadcn/ui** (componentes: Button, Input, Dialog, Select, etc.)
- **@uiw/react-codemirror** + **@codemirror/lang-python**: editor de código Python para nodos custom
- Build: `npm run build` desde `rayflow/editor/frontend/` → genera `rayflow/editor/static/dist/`

```bash
cd rayflow/editor/frontend
npm install
npm run build      # build de producción
npm run dev        # servidor de desarrollo (puerto 5173)
npx tsc --noEmit   # verificar tipos sin compilar
```

### Componentes clave (`src/components/`)
| Archivo | Rol |
|---------|-----|
| `App.tsx` | Raíz: layout, carga de catálogo y lista de flows |
| `FlowCanvas.tsx` | Canvas React Flow, animaciones de ejecución |
| `NodeCard.tsx` | Renderizado de nodo en el canvas (handles, pines, badge RAY/LOCAL). `has-error` se activa para tipo desconocido O cuando `data.hasValidationError` es true (inyectado desde FlowCanvas) |
| `NodePalette.tsx` | Sidebar izq: paleta de nodos arrastrables (colapsable) |
| `VariablesPanel.tsx` | Sidebar izq: gestión de variables del flow (colapsable) |
| `CustomNodesPanel.tsx` | Sidebar izq: editor CodeMirror de nodos custom (colapsable) |
| `PropertiesPanel.tsx` | Sidebar der: propiedades del nodo seleccionado |
| `RunsPanel.tsx` | Footer: ejecutar flow, historial de runs con duración. Chip de estado clickable para cargar en Ray manualmente cuando el flow no está cargado |
| `FlowSettingsDialog.tsx` | Modal de inputs/outputs del flow |

### Otros archivos clave
- `src/lib/api.ts` — cliente HTTP tipado (todas las llamadas al backend)
- `src/lib/translator.ts` — conversión flowDef JSON ↔ React Flow nodes/edges
- `src/store/flowStore.ts` — Zustand store (tabs, runs, catálogo, animMinMs). Exporta `selectActiveTab` como selector puro — usar siempre en lugar de acceder al tab via destructuring directo
- `src/hooks/useRunStream.ts` — SSE streaming + sistema de animación con agrupación paralela. Captura `run_id` del evento `run_start` y reconecta automáticamente (hasta 5 reintentos, backoff 500 ms) si el stream cae con el run todavía activo. Expone `abort()` para cancelar el stream SSE activo

## Sistema de nodos

### Decoradores
- `@ray_node` — corre en proceso Ray remoto (actor con exec pins, task sin exec pins)
- `@engine_node` — corre directamente dentro del FlowEngine (sin RPC); usar para lógica de control ligera
- `@parallel_node` — alias de `@engine_node`, para fork/join explícito

La elección entre `@ray_node` y `@engine_node` afecta el despliegue y el estado — el contrato de `run()` es idéntico (`ctx.set_output()`, `await ctx.fire()`), pero:

- **`@ray_node` con exec pins es stateful**: el actor Ray se instancia una vez en `load()` y persiste hasta `unload()`. La misma instancia atiende todas las ejecuciones — atributos en `self.__init__` o acumulados en `run()` persisten entre requests.
- **`@engine_node` es stateless**: se instancia y descarta en cada ejecución del nodo. No puede acumular estado en `self`.

### Nodo con exec pins
```python
@ray_node   # o @engine_node — mismo contrato, distinto despliegue
class MiNodo:
    exec_in   = ExecInput()
    valor     = Input("int", default=0)
    resultado = Output("str")
    exec_out  = ExecOutput()

    async def run(self, ctx: ExecContext, valor: int) -> None:
        ctx.set_output("resultado", str(valor))
        await ctx.fire("exec_out")
```

### Nodo pure (sin exec pins)
```python
@engine_node   # o @ray_node
class MiPure:
    x      = Input("int", default=0)
    result = Output("int")

    async def run(self, ctx: ExecContext, x: int) -> dict:
        return {"result": x * 2}
```

### Estado en nodos

| | Entre iteraciones del mismo `run()` | Entre ejecuciones del flow |
|---|---|---|
| `@engine_node` | Variables locales Python en el stack de `run()` — funciona porque `_local_fire` cede y retoma en el mismo frame | Solo via `ctx.get_variable()`/`ctx.set_variable()` → GraphState |
| `@ray_node` con exec pins | Variables locales Python o atributos `self` (el actor persiste) | Atributos `self.__init__` o `ctx.get_variable()` → GraphState |

Un engine_node se reinstancia en cada ejecución del flow — no puede acumular estado en `self` entre requests. Un ray_node con exec pins es un actor Ray persistente (vive de `load()` a `unload()`) — sí puede tener estado en `self`.

### Cómo funciona `ctx.fire()` internamente
- En un **engine_node**: llama `_local_fire` directamente dentro del FlowEngine — invoca `_run_loop` sin RPC, sin self-call. Esto permite que nodos de loop (`ForEach`, `While`) hagan `await ctx.fire("loop_body")` a mitad de `run()` sin deadlock.
- En un **ray_node**: el `ExecContext` viaja serializado al actor remoto; `_fire_handler` se descarta y `ctx.fire()` hace RPC al engine (`engine.fire.remote()`), que es el camino legítimo desde un proceso externo.

### Buffer `_pending_outputs` en engine_nodes

`ctx.set_output()` en un engine_node **no escribe directamente al `GraphState`** (eso requeriría `await` dentro de un método sync, o `ray.get()` bloqueante dentro del actor FlowEngine — ambos problemáticos). En cambio, acumula en `ctx._pending_outputs` (dict local en memoria).

El FlowEngine flushea ese buffer con `await` en dos momentos:
1. **Antes de `_local_fire(pin)`** — solo si hay nodos destino que vayan a leer los outputs. Esto permite que un loop como `ForEach` haga `ctx.set_output("element", item)` + `await ctx.fire("loop_body")` en cada iteración: el flush ocurre antes de que el nodo del body corra.
2. **Al finalizar `run()`** — para outputs que no tienen sucesor exec (p.ej. nodos pure o último nodo de una cadena).

```python
# En _fire_engine_node (executor.py):
async def _engine_fire(pin: str) -> None:
    targets = rnode.exec_targets.get(pin, [])
    if ctx._pending_outputs and targets:
        await self._write_node_outputs(node_id, ctx._pending_outputs.copy())
        ctx._pending_outputs.clear()
    await self._local_fire(node_id, rnode, pin)

ctx._output_writer = lambda nid, pin, val: None  # set_output acumula localmente
ctx._fire_handler = _engine_fire
```

`_pending_outputs` se vacía en serialización (`__getstate__`) — si el ctx viaja a un worker Ray, el buffer queda limpio y el nodo usa la ruta normal (`ray.get(engine.set_output.remote(...))`).

### RunQueue y eventos de ejecución (SSE)

Cada flow cargado tiene un actor `RunQueue` persistente (`queue_{flow_name}`, lifetime="detached"), que se crea en `load()` y se destruye en `unload()`. Internamente mantiene un `dict[run_id → asyncio.Queue]`: cada ejecución reserva una entrada con `create_run(run_id)` y la libera con `close_run(run_id)` al terminar.

El FlowEngine empuja eventos a la sub-queue del run activo; FastAPI los consume via `get(run_id)` bloqueante y los reenvía como SSE al cliente. El driver llama `await queue.get.remote(run_id)` desde un async generator, evitando el overhead de `run_in_executor`.

**Eventos SSE emitidos** (en orden de aparición):

| Evento | Campos extra | Quién lo emite |
|--------|-------------|----------------|
| `run_start` | `run_id` | `execute_async()` — primer evento, antes de lanzar el engine |
| `node_start` | `node_id`, `node_type`, `ts` | `FlowEngine` |
| `edge_fire` | `from`, `to`, `pin`, `ts` | `FlowEngine` |
| `node_done` | `node_id`, `node_type`, `duration_ms`, `ts` | `FlowEngine` |
| `flow_done` | `result`, `ts` | `FlowEngine` |
| `flow_error` | `error`, `ts` | `FlowEngine` |

**Regla crítica de rendimiento**: `node_start`, `node_done` y `edge_fire` se empujan **fire-and-forget** (sin `await`):

```python
self._run_queue.push.remote(self._run_id, {...})  # NO await — fire-and-forget
```

Si se usara `await`, el FlowEngine (actor Ray con event loop secuencial) bloquearía esperando la confirmación del push. El orden FIFO está garantizado por el event loop secuencial del actor `RunQueue`, así que `await` es innecesario para correctitud.

`flow_done` y `flow_error` sí usan `await` — para garantizar que el evento llegue antes de que el driver cierre la sub-queue.

**Reconexión SSE**: si el cliente pierde la conexión mientras el flow corre, puede reconectarse usando el `run_id` recibido en `run_start`:

```
GET /editor/flows/{name}/run/{run_id}/stream
```

Este endpoint consume la sub-queue existente sin relanzar la ejecución ni cerrarla. El frontend (`useRunStream.ts`) lo hace automáticamente: hasta 5 reintentos con backoff lineal de 500 ms, solo si no se había recibido un evento terminal (`flow_done`/`flow_error`) antes de que el stream cayera.

### Descubrimiento de nodos
El servidor carga nodos desde:
1. `rayflow/nodes/builtin/` — nodos built-in del paquete
2. `./custom_nodes/` — nodos del usuario en el directorio de trabajo

## API REST del editor

### Flows (`rayflow/editor/routes.py`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/editor/info` | Workspace activo: `{cwd}` |
| `GET` | `/editor/nodes` | Catálogo de nodos disponibles |
| `GET` | `/editor/nodes/{node_type}` | Spec de un tipo de nodo concreto |
| `GET` | `/editor/types` | Tipos canónicos y reglas de compatibilidad |
| `POST` | `/editor/type-check` | Verificar compatibilidad entre dos tipos |
| `GET` | `/editor/flows` | Lista flows en `flows/` |
| `GET` | `/editor/flows/{name}` | Flow JSON |
| `POST` | `/editor/flows` | Crear flow |
| `PUT` | `/editor/flows/{name}` | Actualizar flow |
| `DELETE` | `/editor/flows/{name}` | Borrar flow |
| `POST` | `/editor/validate` | Validar flow (body = flow JSON completo) |
| `POST` | `/editor/flows/{name}/load` | Cargar flow en Ray (precaché) |
| `DELETE` | `/editor/flows/{name}/load` | Descargar flow de Ray |
| `GET` | `/editor/flows/loaded` | Lista todos los flows cargados en Ray con su interfaz (inputs/outputs) |
| `GET` | `/editor/flows/{name}/loaded` | Estado de carga de un flow concreto |
| `POST` | `/editor/flows/{name}/run` | Ejecutar flow (SSE stream); primer evento es `run_start` con `run_id` |
| `GET` | `/editor/flows/{name}/run/{run_id}/stream` | Reconectar a un run activo (SSE stream sin relanzar ejecución) |
| `POST` | `/editor/flows/{name}/serve-events` | Suscribir al event bus |
| `DELETE` | `/editor/flows/{name}/serve-events/{graph_id}` | Desuscribir |

### Nodos custom (`rayflow/editor/custom_nodes_routes.py`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/editor/custom-nodes` | Lista archivos `.py` en `custom_nodes/` |
| `GET` | `/editor/custom-nodes/{name}/source` | Código fuente de un nodo |
| `POST` | `/editor/custom-nodes` | Crear nuevo archivo (body: `{name, source?}`) |
| `PUT` | `/editor/custom-nodes/{name}/source` | Guardar código editado |
| `DELETE` | `/editor/custom-nodes/{name}` | Eliminar archivo |
| `POST` | `/editor/custom-nodes/reload` | Recargar catálogo desde disco (hot reload) |

El endpoint de guardar/crear valida sintaxis Python con `ast.parse()` antes de escribir el archivo, y llama `reset_catalog()` + `get_catalog()` para hacer hot reload sin reiniciar el servidor. Los módulos `custom_nodes.*` cacheados en `sys.modules` se eliminan antes del reload para forzar reimportación.

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
    { "id": "entry", "type": "OnStart" },
    { "id": "add", "type": "Add", "exec_in": "entry", "inputs": { "a": "entry.x", "b": 10 } },
    { "id": "exit", "type": "FlowOutput", "exec_in": "add", "inputs": { "result": "add.result" } }
  ]
}
```

`FlowInput` existe como alias de `OnStart` por compatibilidad hacia atrás, pero el nombre canónico es `OnStart`.

Los flows se guardan en `flows/` dentro del directorio de trabajo.

## Reglas de UI (frontend Vite)

> Tailwind v4 no genera clases de forma fiable en este proyecto. **Usar siempre `style={{}}`** para espaciado, colores y tamaños. Tailwind solo se usa para utilidades que sí se detectan en build time (p.ej. `className="flex flex-col overflow-hidden"`).

### Tokens de color (CSS vars definidos en `src/index.css`)
| Variable | Uso |
|---|---|
| `var(--background)` | Fondo de la app |
| `var(--card)` | Fondo de paneles, header, sidebars, modales |
| `var(--secondary)` | Fondo de inputs, items hover |
| `var(--border)` | Bordes y divisores |
| `var(--foreground)` | Texto principal |
| `var(--muted-foreground)` | Texto secundario, labels, placeholders |
| `var(--primary)` | Azul de acento, tab activa, marca |
| `var(--destructive)` | Rojo de error/borrar |

### Escala tipográfica
| Uso | `fontSize` |
|---|---|
| Label de sección (uppercase) | 11px + `fontWeight: 600` + `letterSpacing: '0.06em'` |
| Texto body / inputs | 13px |
| Texto principal UI | 14px |
| Título de modal | 15px + `fontWeight: 600` |

### Espaciado base
- **Gap entre elementos de un mismo nivel**: 8px
- **Padding interno de paneles/sidebars**: 16px horizontal, 12px vertical
- **Padding interno de items de lista**: `10px 12px`
- **Padding interno de modales**: 24px
- **Altura de inputs y botones**: 32px
- **Separador entre secciones dentro de un modal**: `div` de 1px con `background: var(--border)` y margen vertical 4px

### Modales (Dialog)
```tsx
<DialogContent style={{ maxWidth: 480, padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}
  className="bg-[var(--card)] border-[var(--border)] text-[var(--foreground)]">
  <DialogHeader>
    <DialogTitle style={{ fontSize: 15, fontWeight: 600 }}>Título</DialogTitle>
  </DialogHeader>
  {/* secciones con gap: 20 entre ellas */}
  <div style={{ height: 1, background: 'var(--border)' }} /> {/* divisor entre secciones */}
  <DialogFooter style={{ marginTop: 4 }}>
    <Button variant="ghost" style={{ fontSize: 13 }}>Cancelar</Button>
    <Button style={{ fontSize: 13 }}>Confirmar</Button>
  </DialogFooter>
</DialogContent>
```

### Labels de sección
```tsx
<div style={{
  fontSize: 11, fontWeight: 600,
  color: 'var(--muted-foreground)',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  marginBottom: 10,
}}>Título sección</div>
```

### Botones
El componente `<Button>` en `src/components/ui/button.tsx` está reescrito con `style={}` en lugar de Tailwind. Los variantes disponibles son `default` (azul), `outline` (borde gris), `destructive` (rojo), `ghost` (transparente). No usar `buttonVariants` ni `cva` — ambos dependen de Tailwind.

### Badges / chips inline
No usar el componente `<Badge>` de shadcn (tiene problemas de tipos). Usar spans directos:
```tsx
<span style={{
  display: 'inline-flex', alignItems: 'center',
  borderRadius: 5, padding: '2px 8px',
  fontSize: 11, fontWeight: 500, lineHeight: '18px',
  border: '1px solid var(--border)',
  color: 'var(--muted-foreground)',
}}>etiqueta</span>
```

## Ciclo de vida de un flow en Ray

```
load(flow_json)
  └─ build()               # valida + produce BuiltFlow
  └─ LoadedFlow.load()
       ├─ spawn @ray_node actors  (uno por nodo exec con decorator ray_node)
       ├─ spawn FlowEngine actor  (engine_{flow_name}, lifetime="detached")
       ├─ spawn GraphState actor  (gs_{flow_name}, lifetime="detached")
       └─ spawn RunQueue actor    (queue_{flow_name}, lifetime="detached")

execute(flow_name, inputs)
  └─ genera run_id (uuid hex 8 chars)
  └─ queue.create_run(run_id)           # reserva sub-queue en el actor persistente
  └─ yield {"event": "run_start", "run_id": run_id}  ← primer evento SSE
  └─ engine.execute.remote(inputs, queue, run_id)  ← no bloquea
  └─ driver consume queue.get(run_id) → SSE al cliente
  └─ al llegar flow_done/flow_error → queue.close_run(run_id)

unload(flow_name)
  └─ kill actors @ray_node + FlowEngine + GraphState + RunQueue
```

**GraphState** persiste entre ejecuciones del mismo flow cargado: las variables mantienen su valor entre requests. Se resetean los outputs de nodos en cada `execute()`, pero no las variables.

**Serialización de `execute()`**: el `FlowEngine` es un actor Ray **async**, así que Ray **intercala** las llamadas a `execute()` en su event loop — NO las serializa solo. Como el estado por-run vive en `self` (`_run_id`, `_run_queue`, `_output_refs`, `_exec_arrivals`) y los outputs del nodo de entrada van al `GraphState` compartido, dos ejecuciones simultáneas se pisarían (todas devolverían el resultado de la última). Un `asyncio.Lock` por engine (`self._exec_lock`) serializa `execute()` explícitamente: si llega un segundo request mientras el primero corre, espera a que termine.

## Sistema de eventos

```
serve_events(flow_json)          # igual que load() + suscripción al broker
  └─ EventBroker.subscribe(event_name, flow_name, graph_id)

EmitEvent node → ctx.emit_event(name, payload)
  └─ EventBroker.publish(name, payload)   # fire-and-forget
       └─ _run_event_flow.remote(flow_name, name, payload)  # Ray task (corre en un worker)
            └─ ray.get_actor("engine_{flow_name}") + ray.get_actor("queue_{flow_name}")  # por nombre
            └─ engine.execute.remote({"payload": payload}, queue, run_id)

stop(graph_id, event_names)
  └─ EventBroker.unsubscribe() + unload()
```

- `_run_event_flow` corre como task `@ray.remote` en un **worker distinto del proceso driver**, donde el registro `_loaded_flows` está vacío. Por eso resuelve el flow receptor por sus **actores detached con nombre** (`engine_{flow}`/`queue_{flow}`), no con `get_loaded_flow()`. Y como dispara `engine.execute` directamente, varios eventos sobre el mismo flow generan ejecuciones concurrentes serializadas por el `_exec_lock` del engine.
- El matching del `EventBroker` es **exacto por string** (incluyendo namespace, p.ej. `"ventas/order_created"`).
- Si nadie está suscrito al evento, se pierde — no hay persistencia.
- Un flow de eventos debe declarar los eventos en su campo `events` y tener nodo `OnEvent`.
- `OnEvent` puede coexistir con `OnStart` en el mismo flow (distintos puntos de entrada).

### Triggers por cambio de variable (`OnVariableChange`)

Un flow puede dispararse cuando una variable del estado cambia, reusando el mismo bus:

```
Set escribe variable vigilada → GraphState.set_variable
  └─ si cambió el valor: broker.publish("var:{source}/{var}", {value, old, variable})  # fire-and-forget
       └─ _run_event_flow.remote(flow_vigía, "var:...", payload)
            └─ engine.execute(payload_como_flow_inputs, queue, run_id)  # OnVariableChange expone value/old
```

- **`OnVariableChange`** (nodo de entrada, `events.py`) declara `variable` y `source` (flow dueño; vacío = el propio). Sus outputs `value`/`old` los inyecta el engine. Es un punto de entrada como `OnEvent` (lo reconoce `_find_entry`).
- El registro lo hace `serve_events`: suscribe el flow vigía al evento sintético `var:{source}/{var}` **y** marca la variable como vigilada en el `GraphState` del flow fuente (`gs.watch_variable`). Solo las variables vigiladas publican (sin amplificación sobre el resto).
- `GraphState.set_variable` **solo publica si el valor cambió** (compara viejo vs nuevo, resolviendo `ObjectRef`). Escribir el mismo valor no dispara.
- **Orden de carga**: el flow fuente debe estar cargado antes que el vigía (su `gs_{source}` debe existir al registrar). Por eso `LoadedFlow.load` ahora **espera** a que el engine termine `__init__` (`ray.get(engine.get_graph_id.remote())`) antes de devolver: garantiza que `gs_{flow}` sea localizable por nombre apenas `load()` retorna.
- **Riesgo conocido**: un flow que vigila su propia variable y la reescribe en el run disparado puede entrar en bucle; la defensa actual es "solo dispara si cambió". Un guard de profundidad queda pendiente.

## Archivos clave del backend

| Archivo | Responsabilidad |
|---------|----------------|
| `rayflow/server.py` | FastAPI app, monta editor estático y ambos routers |
| `rayflow/editor/routes.py` | Endpoints de flows, catálogo y ejecución |
| `rayflow/editor/custom_nodes_routes.py` | CRUD de nodos custom + hot reload del catálogo |
| `rayflow/editor/storage.py` | CRUD de flows en disco |
| `rayflow/engine/executor.py` | `FlowEngine` (actor Ray), `LoadedFlow` (ciclo de vida) |
| `rayflow/build/validator.py` | `flatten()`, `build()`, validación de tipos |
| `rayflow/nodes/decorators.py` | `@ray_node`, `@engine_node`, `@parallel_node`, `ExecContext` |
| `rayflow/nodes/loader.py` | `NodeCatalog`: registro, aliases, carga desde disco |
| `rayflow/nodes/registry.py` | Singleton del catálogo, `reset_catalog()` para hot reload |
| `rayflow/state/actor.py` | `GraphState` — variables (persistentes) y outputs de nodos |
| `rayflow/events/bus.py` | `EventBroker` — pub/sub fire-and-forget entre flows |
| `rayflow/api.py` | API pública: `run()`, `load()`, `execute()`, `execute_async()`, `serve_events()`, `stop()` |
| `rayflow/cli/main.py` | CLI: `rayflow serve` |
| `rayflow/workspace.py` | Convenciones de directorio: `custom_nodes/`, `flows/` |
