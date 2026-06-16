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
- **React 18** + **htm** (sin build, vía ESM importmap)
- **@xyflow/react 12**: canvas de grafos
- Todos los módulos se cargan desde CDN (`esm.sh`)

### Importmap crítico (`editor/static/index.html`)
```json
{
  "react":         "https://esm.sh/react@18.3.1",
  "react-dom/client": "https://esm.sh/react-dom@18.3.1/client",
  "htm":           "https://esm.sh/htm@3.1.1",
  "@xyflow/react": "https://esm.sh/@xyflow/react@12.3.6?external=react,react-dom"
}
```

**Importante**: `@xyflow/react` debe usar `?external=react,react-dom` para evitar instancias duplicadas de React. Todos los componentes deben ligar `htm` a `createElement` localmente:

```js
import htm from 'htm';
import { createElement, useState } from 'react';
const html = htm.bind(createElement);
```

**Nunca** usar `import { html } from 'htm/react'` — genera instancias duplicadas de React.

### Archivos del editor
- `editor/static/index.html` — punto de entrada, importmap
- `editor/static/App.js` — componente raíz
- `editor/static/FlowCanvas.js` — canvas React Flow
- `editor/static/NodePalette.js` — paleta de nodos (sidebar izquierdo)
- `editor/static/NodeCard.js` — renderizado de nodos en el canvas
- `editor/static/PropertiesPanel.js` — panel de propiedades (sidebar derecho)
- `editor/static/FlowManager.js` — header: selección, creación y borrado de flows
- `editor/static/RunPanel.js` — footer: ejecución de flows
- `editor/static/api.js` — cliente HTTP para la API del editor
- `editor/static/translator.js` — conversión entre formato rayflow JSON y React Flow

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

## API REST del editor (`rayflow/editor/routes.py`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/editor/nodes` | Catálogo de nodos disponibles |
| `GET` | `/editor/flows` | Lista flows en `flows/` |
| `GET` | `/editor/flows/{name}` | Flow JSON |
| `POST` | `/editor/flows` | Crear flow |
| `PUT` | `/editor/flows/{name}` | Actualizar flow |
| `DELETE` | `/editor/flows/{name}` | Borrar flow |
| `POST` | `/editor/validate` | Validar flow (body = flow JSON completo) |
| `POST` | `/editor/flows/{name}/run` | Ejecutar flow |
| `POST` | `/editor/flows/{name}/serve-events` | Suscribir al event bus |
| `DELETE` | `/editor/flows/{name}/serve-events/{graph_id}` | Desuscribir |
| `GET` | `/editor/types/check` | Verificar compatibilidad de tipos |

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

## Archivos clave del backend

| Archivo | Responsabilidad |
|---------|----------------|
| `rayflow/server.py` | FastAPI app, monta editor estático y router del editor |
| `rayflow/editor/routes.py` | Endpoints del editor visual |
| `rayflow/editor/storage.py` | CRUD de flows en disco |
| `rayflow/engine/executor.py` | `FlowEngine` (actor Ray async), `FlowExecutor` |
| `rayflow/build/validator.py` | `flatten()`, `build()`, validación de tipos |
| `rayflow/nodes/decorators.py` | `@ray_node`, `@engine_node`, `ExecContext` |
| `rayflow/nodes/registry.py` | Catálogo global de nodos |
| `rayflow/state/actor.py` | `GraphState` — variables y outputs por ejecución |
| `rayflow/events/bus.py` | `EventBroker` — pub/sub entre flows |
| `rayflow/api.py` | API pública: `run()`, `run_async()`, `serve_events()`, `stop()` |
| `rayflow/cli/main.py` | CLI: `rayflow serve` |
| `rayflow/workspace.py` | Convenciones de directorio: `custom_nodes/`, `flows/` |
