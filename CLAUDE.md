# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Start Development Server
```bash
# Install dependencies
pip install -e .

# Start the visual editor (serves both API and frontend)
rayflow create --port 8000

# Or with specific working directory
rayflow create --port 8000 --working-path /path/to/project
```

This command sets `RAYFLOW_CWD` environment variable and launches uvicorn with `rayflow.server.app:app`. The server serves the React-based visual editor at the root URL and provides API endpoints at `/api/*`.

### Testing
```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/
```

### Manual Server Control
If you need to manually start the server:
```bash
# From project root, with working directory set
RAYFLOW_CWD=/path/to/working/dir python -m uvicorn rayflow.server.app:app --host 0.0.0.0 --port 8000 --reload
```

## Architecture Overview

RayFlow is a **visual flow editor with Ray distributed execution** that follows this architecture:

```
Visual Editor (React/Ant Design) ←→ FastAPI Server ←→ Ray Actors (Nodes)
                ↓
         flow.json files                    nodes/*.py files
```

### Key Design Principles

1. **One Node = One Python File**: Each node is a separate `.py` file with a Ray remote class
2. **AST-Based Metadata Extraction**: Server uses Python AST parsing to extract node metadata (inputs, outputs, constants, UI info)
3. **Dynamic Discovery**: Nodes are discovered from both `rayflow/nodes/` (built-in) and `./nodes/` (user-defined)
4. **Type-Safe Connections**: Visual editor enforces type compatibility between node connections
5. **Configurable Node Constants**: Uppercase class variables become editable UI controls

## Visual Editor Architecture

### Frontend Stack
- **React 18** + **Ant Design 5.28.0**: UI framework and components
- **React Flow 11.11.4**: Visual node graph editor with custom node rendering
- **CDN-based loading**: All libraries loaded from CDN (no build process)

### Key Components
- **`editor/app.js`**: Main application with collapsible sidebars
- **`editor/components/Canvas.js`**: React Flow integration with drag-drop and type validation
- **`editor/components/NodeList.js`**: Categorized node library with search
- **`editor/components/Inspector.js`**: Property editor with dynamic form generation
- **`editor/components/NodeComponent.js`**: Custom React Flow node renderer

### Configuration System
- **`editor/config/data-types.json`**: Data type definitions with colors, UI field types, and visual settings
- Type configuration maps Python types to UI components (int→number input, str→text input, bool→switch)

## Node System

### Node Base Class Structure
```python
@ray.remote
class YourNode(RayflowNode):
    # UI Metadata (extracted by AST parser)
    icon = "fa-icon-name"           # Font Awesome icon
    category = "category_name"       # For organization in UI
    description = "What this node does"

    # Configurable Constants (uppercase = editable in UI)
    MAX_VALUE = 100                 # int → number input
    ENABLE_LOGGING = True           # bool → switch
    DEFAULT_MESSAGE = "Hello"       # str → text input

    # Type Definitions
    inputs = {"x": int, "y": str}   # Input port types
    outputs = {"result": float}     # Output port types

    # Execution Flow
    exec_input = True               # Needs execution signal
    exec_output = True              # Provides execution signal

    def process(self, **inputs):
        # Implementation here
        return {"result": some_value}
```

### Special Node Types

**START Node** (`rayflow/nodes/base/start.py`):
- Entry points for workflows
- `exec_input = False`, `exec_output = True`
- No input handles visible (starts the flow)

**RETURN Node** (`rayflow/nodes/base/return.py`):
- Exit points for workflows
- `exec_input = True`, `exec_output = False`
- Terminates workflow execution

### Node Discovery and Metadata
The server scans two directories:
1. **`rayflow/nodes/`**: Built-in nodes (part of package)
2. **`./nodes/`**: User-defined nodes (in working directory)

AST parser extracts from each `.py` file:
- Class metadata (icon, category, description)
- Input/output type definitions
- Configurable constants (uppercase class variables)
- Execution flow configuration

## Server Architecture

### FastAPI Application (`rayflow/server/app.py`)
- Serves visual editor at `/` from `editor/index.html`
- Serves components at `/components/{filename}`
- Serves config files at `/config/{filename}`
- API routes at `/api/*` (defined in `routes.py`)
- Uses `RAYFLOW_CWD` environment variable for working directory

### Key API Endpoints
- **`GET /api/nodes`**: Returns all discovered nodes with metadata
- **`GET /`**: Serves the visual editor
- **`GET /health`**: Health check

## Important File Patterns

### Adding New Built-in Nodes
1. Create `rayflow/nodes/{category}/{name}.py`
2. Follow the node base class pattern
3. Add configurable constants as uppercase class variables
4. Server will automatically discover via AST parsing

### Adding User Nodes
1. Create `./nodes/{name}.py` in working directory
2. Follow same pattern as built-in nodes
3. Will appear in node library with "CUSTOM" badge

### Visual Editor Customization
- **`editor/config/data-types.json`**: Modify type colors, UI field mappings, handle sizes
- **`editor/index.html`**: Add new CDN dependencies or custom CSS
- **Component files**: Modify React components (require server restart for changes)

## Type System

### Supported Python Types
- `int`, `float`, `str`, `bool`, `dict`, `list`, `any`
- Special type: `exec` (execution flow signal, white colored)

### UI Field Mappings (in data-types.json)
- `int`/`float` → `"fieldType": "number"` → Ant Design InputNumber
- `str` → `"fieldType": "text"` → Ant Design Input
- `bool` → `"fieldType": "switch"` → Ant Design Switch
- `dict`/`list` → `"fieldType": "textarea"` → JSON editor

### Connection Rules
- **Exec connections** (white): Only connect exec-to-exec
- **Data connections** (colored): Type must match exactly (no auto-conversion)
- **Each input**: Can only receive one connection
- **Outputs**: Can connect to multiple inputs

## Common Development Patterns

### Testing Node Changes
1. Modify node file in `rayflow/nodes/` or `./nodes/`
2. Restart server (uvicorn auto-reload should work)
3. Refresh editor to see changes in node library
4. Drag updated node to canvas to test

### Debugging Visual Editor
1. Open browser dev tools (F12)
2. Check console for JavaScript errors
3. Inspect network tab for API call failures
4. Use React DevTools if available

### Adding New Data Types
1. Update `editor/config/data-types.json` with new type definition
2. Add color, fieldType, and inputProps
3. Restart server and refresh editor
4. New type will be available for node inputs/outputs