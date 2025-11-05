# Editor Visual

## Vista Principal

El editor usa **Ant Design Layout system** para una interfaz profesional y responsive.

```
┌────────────────────────────────────────────────────────────┐
│  Header                                                     │
│  [≡] RayFlow Editor  [Save Flow] [Run Flow] [≡]           │
├──────────┬────────────────────────────────────────┬────────┤
│          │                                        │        │
│  Node    │          Canvas                        │ Inspec │
│  Library │                                        │ tor    │
│          │     [Node Graph Area]                  │        │
│  [tree]  │                                        │ [props]│
│  [search]│                                        │        │
│          │                                        │        │
└──────────┴────────────────────────────────────────┴────────┘
```

## Componentes

### 1. Header
**Archivo:** `components/Header.js`

- Logo y título
- Botones de acción: Save, Run
- Toggles para colapsar sidebars
- Usa Ant Design Button, Space, Typography

### 2. Node Library (Left Sidebar)
**Archivo:** `components/NodeList.js`

**Features:**
- Tree component con jerarquía de nodos
- Select dropdown para filtrar por categoría (builtin/user/all)
- Input.Search para búsqueda en tiempo real
- Tags para identificar tipos
- Collapsible con Animation.Sider

**Estructura del Tree:**
```
📁 All Nodes
├── 📦 Built-in Nodes
│   ├── 🎯 Math Add
│   ├── 🎯 Math Subtract
│   └── 🎯 Get Variable
└── 👤 User Nodes
    ├── 👤 My Custom Node
    └── 👤 Another Node
```

**Interacciones:**
- **Click:** Selecciona nodo y muestra propiedades en Inspector
- **Drag:** Arrastra nodo al canvas para crear instancia

### 3. Canvas (Center)
**Archivo:** `components/Canvas.js`

**Librería:** React Flow 11.11.4

**Features:**
- Visual node graph editor
- Drag and drop de nodos desde library
- Conexiones exec (blanco) y data (azul)
- Custom nodes con handles específicos
- Zoom, pan, fit view
- Background con patrón de puntos
- Shortcuts button

**Custom Nodes:**
- Tema oscuro (#1a1a1a)
- 4 handles por nodo:
  - exec-in (30%, white, 12px)
  - exec-out (30%, white, 12px)
  - data-in (70%, blue, 10px)
  - data-out (70%, blue, 10px)
- Borde azul cuando seleccionado
- Smooth transitions

**Validaciones:**
- Exec solo con exec
- Data solo con data
- Un solo input por handle
- Outputs pueden ir a múltiples destinos

**Shortcuts Modal:**
- Botón flotante top-right
- Organizado por categorías
- Muestra reglas de conexión
- Usa Ant Design Modal, Card, Descriptions

### 4. Inspector (Right Sidebar)
**Archivo:** `components/Inspector.js`

**Features:**
- Muestra propiedades del nodo seleccionado
- Cards organizadas por secciones:
  - Node Properties (name, type, path)
  - Code Editor placeholder
- Empty state cuando no hay selección
- Close button para deseleccionar
- Collapsible con Layout.Sider

## Funcionalidades Implementadas

### Drag and Drop
1. Usuario arrastra nodo desde Node Library
2. `onDragStart` en NodeList guarda datos en DataTransfer
3. Usuario arrastra sobre Canvas
4. `onDragOver` en Canvas permite drop
5. `onDrop` en Canvas:
   - Lee datos del nodo
   - Convierte coordenadas de pantalla a flow
   - Genera ID único (`node_001`, `node_002`, etc.)
   - Crea instancia en canvas

### Conexiones
1. Usuario arrastra desde handle de salida
2. React Flow muestra preview de conexión
3. `isValidConnection` valida tipo y disponibilidad
4. Si válido, `onConnect` crea edge con estilo automático
5. Edge se colorea según tipo (exec: blanco, data: azul)

### Selección Visual
- **Nodos:** Borde azul + glow cuando seleccionado
- **Edges:** Rosa cuando seleccionado
- **Hover:** Edges más gruesos

### Eliminación
- **Nodos:** Select + Delete key
- **Edges:** Click para seleccionar + Delete key

## Estado del Proyecto

### ✅ Implementado

**Layout y UI:**
- Ant Design 5.28.0 integration
- Responsive layout con sidebars collapsibles
- Header con controles
- Font Awesome 6.4.0 para iconos

**Node Library:**
- Tree component con jerarquía
- Búsqueda y filtrado
- Drag and drop support

**Canvas:**
- React Flow 11.11.4 integrado
- Custom nodes con dual handles
- Drag and drop desde library
- Conexiones type-safe
- Validación de inputs únicos
- Delete edges y nodes
- Visual feedback (selection, hover)
- Shortcuts helper modal

**Inspector:**
- Visualización de propiedades
- Empty state
- Close button

### 🚧 Pendiente

**Save/Load:**
- Exportar grafo a JSON
- Importar JSON
- Validar formato

**Code Editor:**
- Monaco Editor integration
- Editar código de nodos
- Syntax highlighting
- Save cambios

**Advanced Features:**
- Undo/redo
- Copy/paste nodes
- Multiple selection
- Zoom to fit selected
- Node search en canvas
- Connection validation avanzada (tipos de datos)

## Tecnologías

- **React 18** (CDN)
- **Ant Design 5.28.0** (unpkg CDN)
- **React Flow 11.11.4** (jsdelivr CDN)
- **Font Awesome 6.4.0**
- **Tailwind CSS** (para Canvas custom styles)
- **Babel Standalone** (JSX transformation)
- **No build process** - todo desde CDNs

## Conexiones con Backend

### GET /api/nodes
Obtiene lista de nodos disponibles:

```javascript
const response = await fetch('/api/nodes');
const data = await response.json();
// Returns: [{ name: "Add", type: "builtin", path: "rayflow/nodes/math/add.py" }, ...]
```

### POST /api/save (Futuro)
Guarda el flujo:

```javascript
const graphData = {
  name: "My Flow",
  nodes: [...],
  connections: [...]
};

await fetch('/api/save', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(graphData)
});
```

### POST /api/run (Futuro)
Ejecuta el flujo:

```javascript
const result = await fetch('/api/run', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    graph: graphData,
    inputs: {user_id: 123, action: "process"}
  })
});
```

## Extensibilidad

### Agregar Nuevo Tipo de Nodo Visual

Para agregar representación visual de un nuevo tipo:

1. **Definir color en theme:**
```javascript
const nodeColors = {
  'base': '#4CAF50',    // Verde para START
  'return': '#F44336',   // Rojo para RETURN
  'variables': '#FF9800', // Naranja para variables
  'math': '#2196F3',     // Azul para math
  // ... agregar nuevo tipo
};
```

2. **Customizar handles si necesario:**
```javascript
// Si el nodo no usa el esquema estándar
const SpecialNode = ({ data, selected }) => {
  return (
    <div>
      {/* Custom handles layout */}
    </div>
  );
};
```

3. **Actualizar validación:**
```javascript
// Si tiene reglas especiales de conexión
const isValidConnection = (connection) => {
  // Custom validation logic
};
```
