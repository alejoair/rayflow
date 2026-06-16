# Editor visual — Features actuales

## Stack técnico

- **React 18** vía ESM importmap (sin build, sin npm)
- **htm** ligado a `React.createElement` en cada componente
- **@xyflow/react 12** para el canvas de grafos
- Servido como archivos estáticos desde `rayflow/editor/static/`
- Accesible en `http://localhost:8000/editor`

---

## Layout de la UI

```
┌─────────────────── Header (FlowManager) ────────────────────┐
│ Selector de flow │ + Nuevo │ Guardar │ Validar │ Borrar │ Badge │
├──────────┬──────────────────────────────┬────────────────────┤
│          │                              │                    │
│  Paleta  │         Canvas               │   Propiedades      │
│  (izq)   │      (FlowCanvas)            │   (der)            │
│          │                              │                    │
├──────────┴──────────────────────────────┴────────────────────┤
│                   Footer (RunPanel)                          │
│         Inputs del flow │ ▶ Ejecutar │ Resultado             │
└──────────────────────────────────────────────────────────────┘
```

---

## Componentes

### FlowManager (header)
- Selector dropdown para abrir un flow existente
- Botón **+ Nuevo**: abre modal para crear flow con nombre, inputs JSON y outputs JSON
- Botón **Guardar**: persiste el flow actual en disco (PUT al backend)
- Botón **Validar**: ejecuta build time validation y muestra errores
- Botón **Borrar**: confirma y elimina el flow activo
- Badge de estado: `✓ Válido` / `✗ N error(es)` / `—`

### NodePalette (sidebar izquierdo)
- Lista todos los nodos del catálogo (builtin + custom)
- Buscador por nombre en tiempo real
- Nodos agrupados en dos secciones: **Builtin** y **Custom**
- Tags por tipo de nodo: `exec`/`pure`, `engine`/`ray`/`parallel`
- Drag & drop al canvas para añadir nodos

### FlowCanvas (área central)
- Canvas interactivo basado en React Flow
- **Drag & drop** desde la paleta: detecta la posición del drop y crea el nodo
- **Conexiones**: click y arrastre desde handles
  - Exec edges (blancas, animadas): entre exec pins
  - Data edges (grises): entre data pins
- **Validación de tipo en conexión**: llama a `/editor/type-check` antes de crear una data edge; si los tipos son incompatibles, muestra toast de error y rechaza la conexión
- **Selección de nodo**: click en nodo abre el panel de propiedades
- **Borrar nodo/edge**: tecla `Delete`
- MiniMap, controles de zoom/pan y fondo punteado
- Estado vacío: mensaje "Arrastra nodos desde la paleta"

### NodeCard (nodo en el canvas)
- Header con nombre del tipo
- Exec input handle (blanco, izquierda del header) si el nodo tiene `exec_in`
- Exec output handle(s) (blanco, derecha del header) — el primero en el header, los adicionales como filas separadas
- Data input handles (izquierda, coloreados por tipo)
- Data output handles (derecha, coloreados por tipo)
- Label y tipo de cada pin visible
- Estado de error si el tipo no está en el catálogo

### PropertiesPanel (sidebar derecho)
- Muestra el nodo seleccionado
- **ID editable**: rename inline (blur o Enter aplica el cambio, actualiza todos los edges que referencian ese nodo)
- **Tipo**: read-only
- **Inputs literales**: formulario dinámico para pins sin conexión entrante
  - `int`/`float` → `<input type="number">`
  - `str` → `<input type="text">`
  - `bool` → checkbox
  - `list`/`dict` → textarea JSON
  - `node_type` → select con todos los tipos del catálogo
  - `flow` → select con flows disponibles
- **Pins conectados**: lista los pins que ya tienen arista (no editables)
- **Errores de validación** del nodo actual (filtrados por id y tipo)

### RunPanel (footer)
- Inputs del flow activo como campos editables (con coerción de tipos: int, float, bool, list, dict)
- Botón **▶ Ejecutar** (deshabilitado si hay errores de validación o está ejecutando)
- Muestra resultado JSON formateado al terminar
- Muestra error si el flow falla

---

## Sistema de colores de tipos

| Tipo | Variable CSS |
|------|-------------|
| `int` | `--type-int` |
| `float` | `--type-float` |
| `str` | `--type-str` |
| `bool` | `--type-bool` |
| `list` | `--type-list` |
| `dict` | `--type-dict` |
| `Any` | `--type-any` |

---

## Persistencia de posiciones

Las posiciones `(x, y)` de cada nodo en el canvas se guardan en el campo `ui` del JSON del flow:

```json
{ "id": "add_1", "type": "Add", "ui": { "x": 300, "y": 120 }, ... }
```

Al abrir un flow, si un nodo no tiene `ui`, se asigna posición automática en grilla (4 columnas, 220px × 180px de separación).

---

## Traducción FlowDef ↔ React Flow (`translator.js`)

- `flowDefToRF(flowDef, catalog)` → convierte el JSON del flow a nodes/edges de React Flow
- `rfToFlowDef(rfNodes, rfEdges, flowMeta)` → serializa el estado del canvas a JSON de flow
- Soporta los tres modos de `exec_in`: single (`"nodo"`), AND (`["a","b"]`), OR (`{"or":["a","b"]}`)
- `typeColor(type)` → devuelve la variable CSS del color para un tipo de pin

---

## Comunicación con el backend (`api.js`)

| Función | Método | Ruta |
|---------|--------|------|
| `getNodes()` | GET | `/editor/nodes` |
| `getFlows()` | GET | `/editor/flows` |
| `getFlow(name)` | GET | `/editor/flows/{name}` |
| `createFlow(body)` | POST | `/editor/flows` |
| `updateFlow(name, body)` | PUT | `/editor/flows/{name}` |
| `deleteFlow(name)` | DELETE | `/editor/flows/{name}` |
| `validateFlow(body)` | POST | `/editor/validate` |
| `typeCheck(from, to)` | POST | `/editor/type-check` |
| `runFlow(name, inputs)` | POST | `/editor/flows/{name}/run` |

---

## Notificaciones (toasts)

Sistema de toasts en `App.js`: aparecen 3.5 segundos y desaparecen solos.
- `info` — azul
- `success` — verde
- `error` — rojo

Usados en: guardado, validación, conexiones incompatibles, errores de ejecución.

---

## Lo que falta / pendiente

- Soporte visual para nodos con múltiples exec outputs (solo se muestra el primero en el header; los adicionales se renderizan como filas pero sin handle múltiple en la posición correcta)
- No hay soporte de AND/OR join mode editable desde la UI (se serializa correctamente pero no se puede cambiar visualmente)
- No hay undo/redo
- No hay zoom to fit automático al abrir un flow con posiciones guardadas
- Las posiciones UI se guardan solo al hacer **Guardar** explícitamente
