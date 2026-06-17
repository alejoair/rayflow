# CLAUDE.md

Guía para Claude Code al trabajar en este repositorio.

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
  editor/static/*.js          rayflow/engine/executor.py
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
| `NodeCard.tsx` | Renderizado de nodo en el canvas (handles, pines, badge RAY/LOCAL) |
| `NodePalette.tsx` | Sidebar izq: paleta de nodos arrastrables (colapsable) |
| `VariablesPanel.tsx` | Sidebar izq: gestión de variables del flow (colapsable) |
| `CustomNodesPanel.tsx` | Sidebar izq: editor CodeMirror de nodos custom (colapsable) |
| `PropertiesPanel.tsx` | Sidebar der: propiedades del nodo seleccionado |
| `RunsPanel.tsx` | Footer: ejecutar flow, historial de runs con duración |
| `FlowSettingsDialog.tsx` | Modal de inputs/outputs del flow |

### Otros archivos clave
- `src/lib/api.ts` — cliente HTTP tipado (todas las llamadas al backend)
- `src/lib/translator.ts` — conversión flowDef JSON ↔ React Flow nodes/edges
- `src/store/flowStore.ts` — Zustand store (tabs, runs, catálogo, animMinMs)
- `src/hooks/useRunStream.ts` — SSE streaming + sistema de animación con agrupación paralela

## Sistema de nodos

### Decoradores
- `@ray_node` — corre en proceso Ray remoto (actor con exec pins, task sin exec pins)
- `@engine_node` — corre localmente en el event loop del engine
- `@parallel_node` — alias de `@engine_node`, para fork/join explícito

### Nodo con exec pins
```python
@ray_node   # o @engine_node
class MiNodo:
    exec_in  = ExecInput()
    valor    = Input("int", default=0)
    resultado = Output("str")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, valor: int) -> None:
        ctx.set_output("resultado", str(valor))  # antes del fire
        await ctx.fire("exec_out")
```

### Nodo pure (sin exec pins)
```python
@engine_node
class MiPure:
    x      = Input("int", default=0)
    result = Output("int")

    def run(self, ctx: ExecContext, x: int) -> dict:
        return {"result": x * 2}
```

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
| `POST` | `/editor/flows/{name}/run` | Ejecutar flow (SSE stream) |
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
       └─ spawn GraphState actor  (gs_{flow_name}, lifetime="detached")

execute(flow_name, inputs)
  └─ crea RunQueue temporal (actor detached)
  └─ engine.execute.remote(inputs, queue)  ← no bloquea
  └─ driver drena queue (sleep 0.05s loop) → SSE al cliente
  └─ al llegar flow_done/flow_error → kill RunQueue

unload(flow_name)
  └─ kill actors @ray_node + FlowEngine + GraphState
```

**GraphState** persiste entre ejecuciones del mismo flow cargado: las variables mantienen su valor entre requests. Se resetean los outputs de nodos en cada `execute()`, pero no las variables.

**Serialización de `execute()`**: el `FlowEngine` es un actor Ray — si llega un segundo request mientras el primero corre, Ray lo encola (event loop del actor es secuencial).

## Sistema de eventos

```
serve_events(flow_json)          # igual que load() + suscripción al broker
  └─ EventBroker.subscribe(event_name, flow_name, graph_id)

EmitEvent node → ctx.emit_event(name, payload)
  └─ EventBroker.publish(name, payload)   # fire-and-forget
       └─ _run_event_flow.remote(flow_name, name, payload)  # Ray task
            └─ lf.execute({"payload": payload}, queue)

stop(graph_id, event_names)
  └─ EventBroker.unsubscribe() + unload()
```

- El matching del `EventBroker` es **exacto por string** (incluyendo namespace, p.ej. `"ventas/order_created"`).
- Si nadie está suscrito al evento, se pierde — no hay persistencia.
- Un flow de eventos debe declarar los eventos en su campo `events` y tener nodo `OnEvent`.
- `OnEvent` puede coexistir con `OnStart` en el mismo flow (distintos puntos de entrada).

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
| `rayflow/api.py` | API pública: `run()`, `load()`, `execute()`, `serve_events()`, `stop()` |
| `rayflow/cli/main.py` | CLI: `rayflow serve` |
| `rayflow/workspace.py` | Convenciones de directorio: `custom_nodes/`, `flows/` |
