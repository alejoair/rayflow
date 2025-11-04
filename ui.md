# RayFlow Editor UI Documentation

## Overview

RayFlow Editor is a visual flow editor built with React 18 and Ant Design 5.0.7. It provides a blueprint-style interface for creating and editing distributed workflows using Ray. The application uses a CDN-based approach without a build process.

## Architecture

### Main Application Structure
```
├── index.html          # Main HTML file with CDN imports
├── app.js              # Main React application component
└── components/
    ├── Header.js        # Header component (not implemented)
    ├── NodeList.js      # Left sidebar - Node library
    ├── Canvas.js        # Center area - Visual flow editor
    └── Inspector.js     # Right sidebar - Node properties
```

## Technology Stack

### Core Libraries
- **React 18**: UI framework (loaded from CDN)
- **Ant Design 5.28.0**: Professional UI component library
- **React Flow 11.11.4**: Visual node-based editor with drag and drop
- **Font Awesome 6.4.0**: Icon library
- **Tailwind CSS**: Utility-first CSS framework
- **Babel Standalone**: JSX transformation in browser

### No Build Process
The application runs entirely from CDN-loaded libraries with no build step required. This allows for rapid development and easy deployment.

## Components

### 1. RayFlowEditor (Main Component)
**File**: `app.js`

**Purpose**: Root application component that manages the overall layout and state.

**State Management**:
- `nodes`: Array of available nodes loaded from backend
- `loading`: Boolean for loading state
- `error`: String for error messages
- `selectedNode`: Currently selected node object
- `leftSidebarCollapsed`: Boolean for left sidebar state
- `rightSidebarCollapsed`: Boolean for right sidebar state

**Key Functions**:
- `loadNodes()`: Fetches nodes from `/api/nodes` endpoint
- `handleSave()`: Placeholder for save functionality
- `handleRun()`: Placeholder for run functionality
- `handleNodeSelect()`: Sets selected node and logs selection
- `handleNodeDeselect()`: Clears selected node
- `handleCanvasClick()`: Deselects node when clicking canvas background
- `toggleLeftSidebar()`: Controls left sidebar collapse
- `toggleRightSidebar()`: Controls right sidebar collapse

**Layout Structure**:
```jsx
<Layout style={{ height: '100vh' }}>
  <Header>                    // Top navigation bar
  <Layout>
    <Sider>                   // Left sidebar - NodeLibrary
    <Content>                 // Center area - Canvas
    <Sider>                   // Right sidebar - Inspector
```

**Ant Design Components Used**:
- `Layout`, `Header`, `Sider`, `Content`
- `Button`, `Space`, `Typography.Title`, `Typography.Text`

### 2. NodeLibrary Component
**File**: `components/NodeList.js`

**Purpose**: Left sidebar component for browsing and selecting available nodes.

**State Management**:
- `selectedCategory`: Filter nodes by type ('all', 'builtin', 'user')
- `searchText`: Text filter for node names and paths

**Props**:
- `nodes`: Array of node objects from parent
- `loading`: Loading state from parent
- `error`: Error message from parent
- `onNodeSelect`: Callback when node is selected

**Key Functions**:
- `filteredNodes`: Computed array of nodes filtered by category and search
- `handleNodeClick()`: Handles tree node selection and calls parent callback

**Features**:
- Category filtering (All, Built-in, User nodes)
- Text search across node names and paths
- Tree view with icons and tags
- Loading and error states
- Empty state when no nodes found
- **Drag and Drop**: Each tree item is draggable to canvas

**Drag and Drop Implementation**:
- Each tree node title is wrapped in a draggable `div`
- `draggable` attribute enables HTML5 drag
- `onDragStart` sets node data in `dataTransfer` with type `'application/reactflow'`
- Data transferred includes:
  - `type`: Node path (e.g., "rayflow/nodes/math/add.py")
  - `name`: Display name (e.g., "Add")
  - `nodeType`: Category ("builtin" or "user")
- Cursor changes to `grab` to indicate draggability

**Ant Design Components Used**:
- `Typography.Title`, `Space`, `Select`, `Input.Search`
- `Spin`, `Alert`, `Empty`, `Tree`, `Tag`

### 3. Inspector Component
**File**: `components/Inspector.js`

**Purpose**: Right sidebar component for viewing and editing selected node properties.

**Props**:
- `selectedNode`: Current selected node object
- `onNodeDeselect`: Callback to clear selection

**Features**:
- Node properties display (name, type, path)
- Code editor placeholder
- Empty state when no node selected
- Close button to deselect node

**Ant Design Components Used**:
- `Typography.Title`, `Button`, `Space`, `Card`
- `Descriptions`, `Tag`, `Typography.Text`, `Empty`

### 4. Canvas Component
**File**: `components/Canvas.js`

**Purpose**: Visual flow editor powered by React Flow with Blueprints-inspired horizontal layout.

**Props**:
- `onCanvasClick`: Callback for canvas click events

**State Management**:
- `nodes`: Array of node instances in the canvas (managed by React Flow)
- `edges`: Array of connections between nodes (managed by React Flow)
- `nodeIdCounter`: Counter for generating unique node IDs (`node_001`, `node_002`, etc.)
- `reactFlowInstance`: Reference to React Flow instance for coordinate conversion
- `reactFlowWrapper`: Ref to wrapper div for drag and drop calculations

**Custom Node Component**:
- **Type**: `custom` (replaces default React Flow nodes)
- **Style**: Dark theme with rounded corners matching Blueprints aesthetic
- **Selection Visual**: When selected, border changes from gray to blue with glow effect
- **Transition**: Smooth 0.2s animation when selection state changes
- **Handles**: Each node has 4 connection points:
  - `exec-in` (top 30%, white, 12px): Incoming execution signal
  - `exec-out` (top 30%, white, 12px): Outgoing execution signal
  - `data-in` (top 70%, blue, 10px): Incoming data flow
  - `data-out` (top 70%, blue, 10px): Outgoing data flow

**Connection Types**:
1. **Exec Connections** (white, thick):
   - Control when nodes execute
   - Style: `stroke: '#fff', strokeWidth: 3`
   - Type: `smoothstep` for curved appearance

2. **Data Connections** (blue, animated):
   - Pass data between nodes
   - Style: `stroke: '#1890ff', strokeWidth: 2, animated: true`
   - Type: `smoothstep` for curved appearance

**Drag and Drop Implementation**:

The Canvas implements HTML5 Drag API integrated with React Flow for seamless node instantiation:

1. **onDragOver**: Prevents default behavior and sets drop effect to 'move'
2. **onDrop**:
   - Extracts node data from `dataTransfer`
   - Converts screen coordinates to flow coordinates using `reactFlowInstance.project()`
   - Creates new node with unique ID format: `node_XXX` (zero-padded 3 digits)
   - Adds node to canvas at drop position
   - Increments node ID counter

**Key Functions**:
- `isValidConnection()`: Validates connection types before allowing them
  - Exec handles can only connect to exec handles
  - Data handles can only connect to data handles
  - Prevents mismatched connections (exec to data, or vice versa)
  - Each input handle can only receive ONE connection (no multiple sources)
  - Output handles can connect to multiple targets
- `onConnect()`: Handles user creating connections between nodes
  - Applies appropriate styling based on connection type
  - Exec connections: white, thick, static
  - Data connections: blue, thin, animated
- `onDragOver()`: Allows dropping by preventing default behavior
- `onDrop()`: Creates new node instance from dragged template
- `onNodesChange()`: React Flow callback for node updates (move, delete, etc.)
- `onEdgesChange()`: React Flow callback for edge updates

**React Flow Features Enabled**:
- `Controls`: Zoom in/out, fit view, and lock controls
- `Background`: Dotted pattern background (`variant: "dots", gap: 12, size: 1`)
- `fitView`: Automatically fits all nodes in viewport on load
- Node dragging and repositioning
- Edge creation by connecting handles
- Node selection and deletion
- **Edge deletion**: Click edge to select (turns pink), press Delete/Backspace to remove
- Edge hover feedback: Edges become thicker on hover for better visibility
- **Shortcuts Button**: Info button in top-right corner shows keyboard shortcuts modal

**Shortcuts Modal**:
- Accessible via button in top-right corner of canvas
- Organized into three sections: Node Operations, Connection Operations, Canvas Navigation
- Includes connection rules reminder (exec/data types, single input rule)
- Uses Ant Design Modal with Cards and Descriptions for clean layout

**React Flow Components Used**:
- `ReactFlow`: Main canvas component
- `Controls`: Zoom and view controls
- `Background`: Dotted background pattern
- `Handle`: Connection points on nodes
- `Position`: Enum for handle positions (Left, Right)
- `useNodesState`: Hook for managing nodes
- `useEdgesState`: Hook for managing edges
- `addEdge`: Utility for creating edges

## Component Interactions

### Data Flow
1. **App → NodeLibrary**: Passes `nodes`, `loading`, `error`, `onNodeSelect`
2. **NodeLibrary → App**: Calls `onNodeSelect` when user clicks node
3. **App → Inspector**: Passes `selectedNode`, `onNodeDeselect`
4. **Inspector → App**: Calls `onNodeDeselect` when user clicks close
5. **App → Canvas**: Passes `onCanvasClick`
6. **Canvas → App**: Calls `onCanvasClick` for background clicks
7. **NodeLibrary → Canvas**: Drag and drop transfers node data via HTML5 DataTransfer API

### State Changes
1. **Node Selection**: NodeLibrary (click) → App → Inspector
2. **Node Instantiation**: NodeLibrary (drag) → Canvas (drop) → Creates new node instance
3. **Node Deselection**: Inspector/Canvas → App → Inspector
4. **Sidebar Collapse**: Header buttons → App state → Sider props

### Drag and Drop Flow
1. **User drags** node from NodeLibrary Tree component
2. **onDragStart** in NodeLibrary sets node data in DataTransfer
3. **User drags over** Canvas area
4. **onDragOver** in Canvas prevents default to allow drop
5. **User drops** node in Canvas
6. **onDrop** in Canvas:
   - Reads node data from DataTransfer
   - Converts screen coordinates to flow coordinates
   - Generates unique ID (`node_001`, `node_002`, etc.)
   - Creates new node instance at drop position
   - Updates React Flow nodes state
7. **Node appears** on canvas and can be connected to other nodes

### Backend Integration
- **GET /api/nodes**: Fetches available nodes on app mount
- **Node Structure**: `{ name, type, path }` where type is 'builtin' or 'user'

## Styling Approach

### Ant Design Integration
- Primary UI framework for components and layout
- Consistent theming and design language
- Built-in responsive behavior and accessibility

### Custom Styling
- **Canvas**: Tailwind CSS for grid pattern and layout
- **Scrollbars**: Webkit custom scrollbar styles
- **Colors**: Ant Design default theme colors

### CSS Organization
- Ant Design CSS loaded from CDN
- Tailwind CSS for utility classes
- Custom styles in `<style>` block in index.html

## State Management Patterns

### Local State
Each component manages its own UI state (search text, filters, etc.)

### Lifted State
Shared state managed in main App component:
- Selected node (shared between NodeLibrary and Inspector)
- Sidebar collapse states (controlled by header buttons)
- Nodes data (fetched once, shared with NodeLibrary)

### Props Down, Events Up
- Data flows down through props
- User interactions bubble up through callbacks
- Clear separation of concerns between components

## Current Implementation Status

### ✅ Completed Features
- **React Flow Integration**: Full visual node editor with zoom, pan, and controls
- **Drag and Drop**: Seamless node instantiation from library to canvas
- **Dual Connection Types**: Separate exec (white) and data (blue) connections
- **Connection Validation**: Type-safe connections (exec-to-exec, data-to-data only)
- **Single Input Rule**: Each input handle can only receive one connection
- **Automatic Styling**: Connections automatically styled based on type
- **Edge Deletion**: Click edge to select (turns pink), press Delete to remove
- **Visual Feedback**: Edges highlight on hover and selection
- **Node Selection Visual**: Selected nodes show blue border with glow effect
- **Shortcuts Helper**: Info button with modal showing all keyboard shortcuts and rules
- **Custom Nodes**: Blueprints-inspired dark theme with 4 distinct handles
- **Node Library**: Searchable tree with category filtering
- **Responsive Layout**: Collapsible sidebars with Ant Design
- **Node Selection**: Click to select and view in inspector
- **Manual Connections**: Users can create connections by dragging between handles
- **Node Repositioning**: Drag nodes around the canvas
- **Unique IDs**: Automatic generation of unique node IDs (`node_001`, `node_002`, etc.)

### 🚧 In Progress / Planned Features
- Code editor integration for node editing (Monaco Editor)
- Save/load workflow functionality (export/import JSON)
- Real-time execution with Ray backend
- Node deletion UI
- Advanced connection validation (parameter type checking)
- Undo/redo functionality
- Multiple selection
- Copy/paste nodes
- Minimap (currently removed per user preference)
- Visual feedback when invalid connection is attempted

### Technical Improvements
- Add TypeScript for better type safety
- Implement proper state management (Redux/Zustand)
- Add unit and integration tests
- Optimize performance for large node libraries
- Add keyboard shortcuts and accessibility features
- Connection validation rules
- Node templates with configurable inputs/outputs

## Development Notes

### CDN Dependencies
- React 18 (development version for debugging)
- Ant Design 5.28.0 (unpkg CDN for better compatibility)
- React Flow 11.11.4 (jsdelivr CDN)
- Font Awesome 6.4.0 for icons
- Babel standalone for JSX transformation
- Tailwind CSS for utility classes
- dayjs 1.11.7 for Ant Design date handling

### Browser Compatibility
- Modern browsers with ES6 support
- No build process required
- Direct file serving from FastAPI backend

### Debugging
- Development versions of all libraries for better error messages
- Console logging for user interactions
- Error boundaries could be added for better error handling