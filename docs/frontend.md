# Editor visual — frontend

Editor visual del flow, servido en `http://localhost:8000/editor`.

> Nota: la guía de arquitectura y las convenciones de UI viven en `CLAUDE.md`
> (sección "Frontend (editor visual)"). Este documento describe las features de
> usuario del editor. El código fuente está en `rayflow/editor/frontend/`.

## Stack

- **React 18** + **TypeScript** + **Vite** (build real, no importmap).
- **@xyflow/react 12** para el canvas de grafos.
- **shadcn/ui** para componentes (Button, Dialog, Select, Tabs, …).
- **@uiw/react-codemirror** + **@codemirror/lang-python** para el editor de nodos custom.
- **Zustand** para el estado (tabs, runs, catálogo).

Build de producción: `npm run build` desde `rayflow/editor/frontend/` genera
`rayflow/editor/static/dist/`, que es lo que sirve el servidor FastAPI. En
desarrollo, `npm run dev` levanta Vite en el puerto 5173.

## Componentes (`src/components/`)

| Componente | Rol |
|------------|-----|
| `App.tsx` | Raíz: layout, carga de catálogo y lista de flows, sistema de tabs |
| `FlowCanvas.tsx` | Canvas React Flow; animación de ejecución en vivo |
| `NodeCard.tsx` | Render de un nodo (handles, pines, badge RAY/LOCAL, estado de error) |
| `NodePalette.tsx` | Sidebar izq: paleta de nodos arrastrables (colapsable) |
| `VariablesPanel.tsx` | Sidebar izq: gestión de variables del flow (colapsable) |
| `CustomNodesPanel.tsx` | Sidebar izq: editor CodeMirror de nodos custom (colapsable) |
| `CodeEditor.tsx` | Wrapper de CodeMirror con resaltado Python/Rayflow |
| `PropertiesPanel.tsx` | Sidebar der: propiedades del nodo seleccionado |
| `RunsPanel.tsx` | Footer: ejecutar el flow, historial de runs con duración |
| `FlowSettingsDialog.tsx` | Modal de inputs/outputs (interfaz) del flow |

## Otros archivos clave

- `src/lib/api.ts` — cliente HTTP tipado (todas las llamadas al backend).
- `src/lib/translator.ts` — conversión flowDef JSON ↔ React Flow nodes/edges.
- `src/store/flowStore.ts` — store Zustand: tabs, runs, catálogo. Persiste el
  working state en localStorage.
- `src/hooks/useRunStream.ts` — streaming SSE + animación de ejecución, con
  reconexión automática al run activo si se cae la conexión.

## Features

- **Multi-tab**: varios flows (y nodos custom) abiertos simultáneamente.
- **Drag & drop** desde la paleta al canvas; conexiones por handles.
- **Validación de tipos en vivo**: al conectar un data edge se verifica la
  compatibilidad contra el backend; una conexión inválida se rechaza.
- **Edición de propiedades**: inputs literales por tipo, rename de id, etc.
- **Variables e interfaz**: paneles dedicados para variables y para los
  inputs/outputs del flow.
- **Nodos custom en el navegador**: editor CodeMirror con hot reload del
  catálogo (guardar valida sintaxis Python y recarga sin reiniciar).
- **Ejecución observable**: al correr un flow, el canvas anima nodos y aristas
  en tiempo real vía SSE; el footer muestra resultado e historial de runs.
- **Persistencia de layout**: la posición de cada nodo se guarda en el campo
  `ui` del JSON del flow.

## Tipos de exec_in soportados por el traductor

`single` (`"nodo"`), AND (`["a","b"]`) y OR (`{"or":["a","b"]}`).
