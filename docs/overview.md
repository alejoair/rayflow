# RayFlow Overview

## What is RayFlow?

**RayFlow** is a visual workflow editor with distributed execution powered by Ray. It allows you to create complex computational workflows using a drag-and-drop interface, where each node is a Python function that executes as a distributed Ray actor.

Think of it as **Unreal Engine Blueprints meets Apache Airflow**, but with Python and Ray's distributed computing power.

---

## Core Concepts

### Visual Flow Editor

Create workflows visually by dragging nodes onto a canvas and connecting them. The editor runs in your browser - no installation required.

```
┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐
│  START  │─────→│   ADD   │─────→│MULTIPLY │─────→│ RETURN  │
└─────────┘      └─────────┘      └─────────┘      └─────────┘
```

### Nodes Are Python Functions

Each node is a Python class that inherits from `RayflowNode`:

```python
@ray.remote
class AddNode(RayflowNode):
    inputs = {"x": int, "y": int}
    outputs = {"result": int}

    def process(self, x, y):
        return {"result": x + y}
```

**Key Points**:
- Nodes are **Ray actors** - distributed by default
- Input/output types are **explicitly defined**
- Configuration is done via **class constants** (UPPERCASE variables)
- **Fully Pythonic** - standard Python code with type hints

---

## Node Types

### Built-in Nodes

Located in `rayflow/nodes/`, these are part of the package:
- **START**: Entry point (exactly ONE per workflow)
- **RETURN**: Exit point (one or more, terminates execution path)
- **Math**: Add, Multiply, Divide (basic arithmetic)
- More to come: Logic, String, I/O, Data structures

### Custom Nodes

Place your own nodes in `./nodes/` directory:
- Automatically discovered and displayed in the editor
- Marked with "CUSTOM" badge
- Edit source code directly in the UI
- Same capabilities as built-in nodes

**Example custom node**:
```python
# ./nodes/my_custom_node.py
@ray.remote
class MyCustomNode(RayflowNode):
    icon = "fa-star"
    category = "custom"
    description = "My awesome node"

    inputs = {"data": str}
    outputs = {"processed": str}

    def process(self, data):
        # Your logic here
        return {"processed": data.upper()}
```

---

## Execution Flow System

### Dual-Channel Architecture

RayFlow uses two separate systems for flow control:

**1. Execution Flow (Exec)** - Controls WHEN nodes execute
- White connections in the UI
- Determines execution order
- Independent of data

**2. Data Flow** - Controls WHAT DATA flows
- Colored connections (by type)
- Passes actual values between nodes
- Type-safe connections

```
         EXEC (white)
START ══════════════════> ADD
  │                        ↑
  │    DATA (colored)      │
  └────────────────────────┘
       (value flows)
```

**Why two channels?**

This gives you **maximum flexibility**:
- Execute nodes based on logic, not just data availability
- Branch execution paths conditionally
- Join multiple execution paths
- Parallel execution of independent branches

Inspired by **Unreal Engine Blueprints**, where exec pins control flow and data pins pass values.

---

## Flow Structure Rules

### One START, Multiple RETURNs

**START Node**:
- Exactly **ONE** per workflow (enforced by validator)
- Entry point for execution
- Receives external inputs
- No incoming connections (starts the flow)

**RETURN Nodes**:
- **One or more** per workflow
- Each represents an exit point
- First RETURN reached terminates the workflow
- Can have different outputs based on path taken

```
         ┌────→ RETURN (success)
START ───┤
         └────→ RETURN (error)
```

This allows **multiple exit paths** based on conditions or logic.

---

## Parallel Execution (Ray-Powered)

RayFlow executes nodes in **parallel automatically** when possible:

```
         ┌────→ NODE_A ────┐
START ───┤                  ├────→ RETURN
         └────→ NODE_B ────┘

NODE_A and NODE_B execute in PARALLEL
```

**Ray handles everything**:
- No manual threading code
- Automatic distribution across CPU cores
- Can scale to multiple machines
- Built-in fault tolerance

**Execution Rules**:
- Nodes with **no dependencies** execute in parallel
- Nodes with **dependencies** wait for predecessors
- Join nodes wait for **all** incoming connections

The orchestrator uses **topological ordering** to maximize parallelism while respecting dependencies.

---

## Global Variable System

Share state across the entire workflow using the **GlobalVariableStore**:

```python
SET Variable (counter = 0)
    ↓
GET Variable (counter) → returns 0
    ↓
ADD (counter + 1) → returns 1
    ↓
SET Variable (counter = 1)
```

**How it works**:
- **One GlobalVariableStore actor** per workflow execution
- All nodes receive a reference to the store
- **Thread-safe** by design (Ray actor model)
- Variables exist only for the workflow duration

**Variable nodes**:
- **GET Variable**: Reads a value from the store
- **SET Variable**: Writes a value to the store
- Types are dynamic (Any type)

This enables **stateful workflows** without passing data through every connection.

---

## Type System

### Supported Types

- `int` - Integer numbers (green)
- `float` - Floating point (blue)
- `str` - Text strings (orange)
- `bool` - Boolean values (pink)
- `dict` - Dictionaries (purple)
- `list` - Lists (cyan)
- `any` - Any type (gray)
- `exec` - Execution signal (white)

### Type Safety

Connections are **type-checked** at design time:
- Only compatible types can connect
- `any` can connect to/from anything
- `exec` only connects to `exec`

**Benefits**:
- Catch errors before execution
- Visual feedback (colors match types)
- Clear data flow understanding

---

## Configurable Constants

Nodes can expose configuration via **UPPERCASE class variables**:

```python
class AddNode(RayflowNode):
    # These become editable in the UI
    OFFSET_VALUE = 0          # int → number input
    ENABLE_VALIDATION = True  # bool → switch
    MIN_VALUE = -1000         # int → number input

    def process(self, x, y):
        result = x + y + self.OFFSET_VALUE
        if self.ENABLE_VALIDATION and result < self.MIN_VALUE:
            raise ValueError("Result too small")
        return {"result": result}
```

**In the UI**:
- Constants appear in the Inspector panel
- Type-appropriate controls (number input, switch, text, etc.)
- Values saved with the workflow
- Changes apply to that node instance only

This makes nodes **reusable and customizable** without code changes.

---

## Workflow Persistence

### Auto-Save (Browser)

- Saves to **localStorage** every 2 seconds
- Automatically restores on page reload
- Great for iterating on designs

### Export/Import (Files)

Export workflows as JSON files:
```json
{
  "metadata": {
    "name": "My Workflow",
    "version": "1.0.0"
  },
  "flow": {
    "nodes": [...],
    "edges": [...]
  }
}
```

**Benefits**:
- Version control (Git-friendly)
- Share workflows with others
- Templates and examples
- Reproducible executions

---

## Distributed Execution

### How Ray Powers RayFlow

When you execute a workflow:

1. **Orchestrator** parses the workflow JSON
2. **Creates Ray actors** for each node
3. **Executes nodes** following the dependency graph
4. **Collects results** from RETURN node

**Ray advantages**:
- **Automatic parallelism** - independent nodes run simultaneously
- **Distributed memory** - nodes can be on different machines
- **Fault tolerance** - failed actors can be restarted
- **Resource management** - Ray schedules based on available resources

**Scalability**:
- Single machine: Uses all CPU cores
- Cluster: Distributes across multiple machines
- Cloud: Can use cloud resources (AWS, GCP, Azure)

All of this happens **transparently** - you just define the workflow.

---

## Development Workflow

### 1. Design Visually

Use the web editor to:
- Drag nodes from the library
- Connect them with exec and data connections
- Configure node constants
- Test and iterate

### 2. Create Custom Nodes

Add your own logic:
```bash
# Create a new node file
touch nodes/my_node.py

# Define the node class
# Reload the editor - it appears automatically!
```

### 3. Execute Workflows

```bash
# Export your workflow to JSON
# Execute via CLI (coming soon)
rayflow run my_workflow.json --input '{"user_id": 123}'

# Or execute via API
POST /api/flows/execute
{
  "flow": {...},
  "inputs": {"user_id": 123}
}
```

---

## Project Structure

```
rayflow/
├── editor/                 # Visual editor (React + React Flow)
│   ├── components/        # UI components
│   ├── context/          # State management
│   └── index.html        # Main entry point
│
├── rayflow/
│   ├── core/             # Core execution engine
│   │   └── node.py       # RayflowNode base class
│   │
│   ├── nodes/            # Built-in nodes
│   │   ├── base/        # START, RETURN
│   │   ├── math/        # Add, Multiply, Divide
│   │   └── ...          # More categories
│   │
│   └── server/           # FastAPI server
│       ├── app.py       # Main app
│       └── routes.py    # API endpoints
│
├── nodes/                # User-defined nodes (auto-discovered)
├── flows/                # Saved workflow files
└── docs/                 # Documentation
```

---

## Key Features Summary

| Feature | Description |
|---------|-------------|
| **Visual Editor** | Drag-and-drop workflow creation in browser |
| **Ray Distributed** | Automatic parallel execution across resources |
| **Dual-Channel Flow** | Separate exec and data connections for flexibility |
| **Pythonic** | Standard Python code with type hints |
| **Type-Safe** | Connections validated at design time |
| **Configurable** | Nodes expose constants as UI controls |
| **Extensible** | Easy to add custom nodes |
| **One START** | Single entry point per workflow |
| **Multiple RETURNs** | Different exit paths possible |
| **Global Variables** | Shared state across workflow |
| **Auto-Discovery** | Nodes automatically appear in editor |
| **Auto-Save** | Never lose your work |
| **Export/Import** | JSON workflow files |

---

## Example: Complete Workflow

**Goal**: Add two numbers, multiply by a factor, return result

**Visual Flow**:
```
START(x=5, y=3) → ADD(x, y) → MULTIPLY(result, factor=2) → RETURN(final)
```

**Python nodes**:
```python
# START node (built-in)
inputs: dynamic from config
outputs: passthrough

# ADD node (built-in)
inputs: {x: int, y: int}
outputs: {result: int}

# MULTIPLY node (built-in)
FACTOR = 2  # Configurable constant
inputs: {x: int}
outputs: {result: int}

# RETURN node (built-in)
inputs: dynamic from config
outputs: formatted response
```

**Execution**:
```
1. START receives {x: 5, y: 3}
2. ADD executes: 5 + 3 = 8
3. MULTIPLY executes: 8 * 2 = 16
4. RETURN executes: {final: 16}
5. Orchestrator returns: {success: true, result: {final: 16}}
```

All nodes run as distributed Ray actors, with automatic parallelism where possible.

---

## Why RayFlow?

### For Data Scientists
- **Visual debugging** of complex pipelines
- **Parallel execution** without infrastructure code
- **Iterative development** with instant visual feedback

### For Engineers
- **Distributed computing** made simple
- **Type safety** prevents runtime errors
- **Extensible** with custom Python code

### For Researchers
- **Reproducible workflows** via JSON exports
- **Easy experimentation** with drag-and-drop
- **Scalable** from laptop to cluster

---

## Next Steps

1. **Start the editor**: `rayflow create --port 8000`
2. **Read the docs**: `docs/orchestrator-architecture.md`
3. **Create custom nodes**: Add files to `./nodes/`
4. **Build workflows**: Drag, connect, configure
5. **Execute** (coming soon): Via CLI or API

---

## Technical Details

- **Frontend**: React 18, Ant Design 5, React Flow 11
- **Backend**: FastAPI, Python 3.8+
- **Execution**: Ray 2.0+
- **Storage**: JSON files, localStorage
- **Architecture**: Modular, event-driven, async

---

## Philosophy

RayFlow is designed around three principles:

1. **Visual First**: Complex logic should be easy to understand at a glance
2. **Pythonic**: Standard Python code, no DSL or special syntax
3. **Distributed by Default**: Parallelism shouldn't be an afterthought

The result is a tool that makes distributed computing **accessible** without sacrificing **power** or **flexibility**.
