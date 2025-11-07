# RayFlow Orchestrator - Development Plan

## Introduction

This document provides a complete implementation plan for the RayFlow orchestrator. It's designed for a **mid-level developer** who understands Python, Ray, and basic distributed systems concepts.

**Time Estimate**: 8-10 days of focused work
**Complexity**: Medium-High
**Prerequisites**: Python 3.8+, Ray 2.0+, understanding of async/distributed computing

---

## Required Reading (In Order)

Before starting implementation, read these documents to understand the system:

### 1. Overview (30 minutes)
**File**: `docs/overview.md`
- Understand RayFlow's core concepts
- Learn about dual-channel flow (exec + data)
- Understand node types and execution model

### 2. Architecture (1-2 hours)
**File**: `docs/orchestrator-architecture.md`
- Understand the 10 modular components
- Learn how modules interact
- Study the execution flow (3 phases)
- Review the example execution

### 3. Node Base Class (30 minutes)
**File**: `rayflow/core/node.py`
- Understand RayflowNode interface
- See how Ray actors work
- Learn about inputs/outputs/exec flow

### 4. Existing Nodes (1 hour)
**Files**:
- `rayflow/nodes/base/start.py` - Entry point
- `rayflow/nodes/base/return.py` - Exit point
- `rayflow/nodes/math/add.py` - Example data node
- `rayflow/nodes/variables/get.py` - Variable system

Understanding these will show you the patterns nodes follow.

### 5. Flow JSON Format (30 minutes)
**Files**:
- `editor/app.js` - See `performSave()` function for export format
- Export a flow from the UI and examine the JSON

### 6. Type System (15 minutes)
**File**: `editor/config/data-types.json`
- Understand type colors and mappings
- Type compatibility rules

**Total Reading Time**: ~4-5 hours (essential before coding)

---

## Implementation Order

We'll implement the 10 modules in **dependency order**, testing each before moving to the next.

```
Phase 1: Data Structures & Validation (2 days)
├─ 1. FlowValidator
├─ 2. GraphBuilder
└─ 3. Tests for Phase 1

Phase 2: Ray Infrastructure (2 days)
├─ 4. VariableStoreManager
├─ 5. NodeLoader
├─ 6. ActorManager
└─ 7. Tests for Phase 2

Phase 3: Execution Logic (2-3 days)
├─ 8. ExecutionPlanner
├─ 9. DataGatherer
├─ 10. NodeExecutor
├─ 11. StateTracker
├─ 12. ErrorHandler
└─ 13. Tests for Phase 3

Phase 4: Orchestrator & Integration (2 days)
├─ 14. Main Orchestrator
├─ 15. Integration Tests
└─ 16. API Endpoint

Phase 5: UI Integration (1 day)
└─ 17. Connect UI to backend
```

---

## Phase 1: Data Structures & Validation

### Day 1-2: Core Data Structures

#### Module 1: FlowValidator

**File**: `rayflow/core/validator.py`

**Purpose**: Validate workflow JSON before execution

**Classes to implement**:
```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str] = field(default_factory=list)

class FlowValidator:
    def validate(self, flow_json: dict) -> ValidationResult
    def _validate_structure(self) -> List[str]
    def _validate_start_node(self) -> List[str]
    def _validate_return_nodes(self) -> List[str]
    def _validate_node_ids(self) -> List[str]
    def _validate_connections(self) -> List[str]
    def _validate_types(self) -> List[str]
```

**Key validations**:
1. JSON has required fields: `metadata`, `flow`, `flow.nodes`, `flow.edges`
2. Exactly ONE START node exists
3. At least ONE RETURN node exists
4. All node IDs are unique
5. All connections reference existing nodes
6. Type compatibility in data connections

**Reference files**:
- `docs/orchestrator-architecture.md` - Validation section
- `editor/app.js` - See exported JSON structure

**Testing**:
```python
# Test with valid flow
# Test with missing START
# Test with duplicate IDs
# Test with invalid connections
# Test with type mismatches
```

---

#### Module 2: GraphBuilder

**File**: `rayflow/core/graph_builder.py`

**Purpose**: Transform JSON into optimized data structures

**Classes to implement**:
```python
@dataclass
class NodeInfo:
    id: str
    type: str
    position: dict
    config: dict
    inputs: Dict[str, str]  # {input_name: type}
    outputs: Dict[str, str]  # {output_name: type}
    exec_input: bool
    exec_output: bool
    constant_values: dict

@dataclass
class DataSource:
    from_node: str
    from_output: str

@dataclass
class FlowGraph:
    nodes: Dict[str, NodeInfo]
    dependencies: Dict[str, List[str]]  # node -> predecessors
    data_flow: Dict[str, Dict[str, DataSource]]  # node -> {input -> source}
    start_node_id: str
    return_node_ids: List[str]
    topological_order: List[str]

class GraphBuilder:
    def build(self, flow_json: dict) -> FlowGraph
    def _build_node_map(self) -> Dict[str, NodeInfo]
    def _build_dependencies(self) -> Dict[str, List[str]]
    def _build_data_flow(self) -> Dict[str, Dict[str, DataSource]]
    def _topological_sort(self) -> List[str]
    def _find_start_node(self) -> str
    def _find_return_nodes(self) -> List[str]
```

**Key logic**:

1. **Build node map**: Parse all nodes from JSON
2. **Build dependencies**: For each edge with exec connection, add to dependencies
3. **Build data flow**: For each edge with data connection, add to data_flow
4. **Topological sort**: Use Kahn's algorithm or DFS
5. **Find special nodes**: Identify START and RETURN nodes

**Edge format handling**:
```python
# React Flow format (from UI)
{
    "source": "node_001",
    "target": "node_002",
    "sourceHandle": "exec-out",  # OR "output-{name}"
    "targetHandle": "exec-in"    # OR "input-{name}"
}

# Parse handle to determine type
if "exec" in source_handle:
    # This is an exec connection
    dependencies[target].append(source)
else:
    # This is a data connection
    output_name = source_handle.replace("output-", "")
    input_name = target_handle.replace("input-", "")
    data_flow[target][input_name] = DataSource(source, output_name)
```

**Reference files**:
- `docs/orchestrator-architecture.md` - GraphBuilder section
- `editor/components/Canvas.js` - See connection creation (onConnect)

**Testing**:
```python
# Test simple linear flow (A → B → C)
# Test branching (A → B, A → C)
# Test join (B → D, C → D)
# Test complex graph
# Test topological sort correctness
```

---

#### Module 3: Tests for Phase 1

**File**: `tests/core/test_validator.py`, `tests/core/test_graph_builder.py`

**Test data**:
Create sample workflow JSONs in `tests/fixtures/`:
- `valid_flow.json` - Complete valid workflow
- `invalid_no_start.json` - Missing START node
- `invalid_duplicate_ids.json` - Duplicate node IDs
- `complex_flow.json` - Branching, joins, multiple returns

**Run tests**:
```bash
pytest tests/core/test_validator.py -v
pytest tests/core/test_graph_builder.py -v
```

---

## Phase 2: Ray Infrastructure

### Day 3-4: Ray Components

#### Module 4: VariableStoreManager

**File**: `rayflow/core/variable_store.py`

**Purpose**: Create and manage GlobalVariableStore Ray actor

**Classes to implement**:
```python
@ray.remote
class GlobalVariableStore:
    def __init__(self):
        self.variables: Dict[str, Any] = {}

    def get(self, variable_name: str) -> Any:
        return self.variables.get(variable_name)

    def set(self, variable_name: str, value: Any) -> bool:
        self.variables[variable_name] = value
        return True

    def exists(self, variable_name: str) -> bool:
        return variable_name in self.variables

    def delete(self, variable_name: str) -> bool:
        if variable_name in self.variables:
            del self.variables[variable_name]
            return True
        return False

    def get_all(self) -> Dict[str, Any]:
        return self.variables.copy()

class VariableStoreManager:
    def __init__(self):
        self.store = None

    def create_store(self, initial_variables: dict = None):
        """Create GlobalVariableStore actor"""
        self.store = GlobalVariableStore.remote()

        # Initialize variables if provided
        if initial_variables:
            for name, value in initial_variables.items():
                ray.get(self.store.set.remote(name, value))

        return self.store

    def get_store_ref(self):
        """Return store reference for nodes"""
        return self.store

    def shutdown(self):
        """Cleanup store"""
        if self.store:
            ray.kill(self.store)
            self.store = None
```

**Reference files**:
- `rayflow/nodes/variables/get.py` - See how nodes use the store
- `rayflow/nodes/variables/set.py` - See how nodes write to store

**Testing**:
```python
# Test store creation
# Test get/set operations
# Test variable persistence across calls
# Test concurrent access (multiple actors)
```

---

#### Module 5: NodeLoader

**File**: `rayflow/core/node_loader.py`

**Purpose**: Dynamically load node classes from Python files

**Classes to implement**:
```python
class NodeLoader:
    def __init__(self):
        self.cache: Dict[str, Type[RayflowNode]] = {}
        self.node_paths = [
            Path("rayflow/nodes"),  # Built-in
            Path("./nodes")          # User-defined
        ]

    def load_node_class(self, node_type: str) -> Type[RayflowNode]:
        """Load node class by type string"""
        # Check cache first
        if node_type in self.cache:
            return self.cache[node_type]

        # Convert type to file path
        file_path = self._type_to_path(node_type)

        # Import module
        module = self._import_module(file_path)

        # Find RayflowNode subclass
        node_class = self._find_node_class(module)

        # Cache and return
        self.cache[node_type] = node_class
        return node_class

    def _type_to_path(self, node_type: str) -> Path:
        """Convert 'math_add' to 'rayflow/nodes/math/add.py'"""
        parts = node_type.split("_")

        if len(parts) == 1:
            # Base node (e.g., "start" → "rayflow/nodes/base/start.py")
            return Path(f"rayflow/nodes/base/{parts[0]}.py")
        else:
            # Categorized node
            category = parts[0]
            name = "_".join(parts[1:])

            # Try user nodes first
            user_path = Path(f"./nodes/{category}/{name}.py")
            if user_path.exists():
                return user_path

            # Fall back to built-in
            return Path(f"rayflow/nodes/{category}/{name}.py")

    def _import_module(self, file_path: Path) -> ModuleType:
        """Import Python module from file path"""
        import importlib.util

        spec = importlib.util.spec_from_file_location("node_module", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module

    def _find_node_class(self, module: ModuleType) -> Type[RayflowNode]:
        """Find class that inherits from RayflowNode"""
        from rayflow.core.node import RayflowNode
        import inspect

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj != RayflowNode and issubclass(obj, RayflowNode):
                return obj

        raise ValueError(f"No RayflowNode subclass found in module")
```

**Reference files**:
- Existing nodes in `rayflow/nodes/` for testing
- `rayflow/core/node.py` - Base class definition

**Testing**:
```python
# Test loading built-in node (math_add)
# Test loading base node (start)
# Test cache functionality
# Test error on missing node
# Test error on invalid node class
```

---

#### Module 6: ActorManager

**File**: `rayflow/core/actor_manager.py`

**Purpose**: Create and manage Ray actors for all nodes

**Classes to implement**:
```python
class ActorManager:
    def __init__(self, variable_store_ref):
        self.actors: Dict[str, ray.ObjectRef] = {}
        self.variable_store = variable_store_ref

    def create_actor(self, node_id: str, node_class: Type, config: dict):
        """Create a single Ray actor"""
        actor = node_class.remote(
            store_ref=self.variable_store,
            config=config
        )
        self.actors[node_id] = actor
        return actor

    def create_all_actors(self, graph: FlowGraph, node_loader: NodeLoader):
        """Create actors for all nodes in graph"""
        for node_id, node_info in graph.nodes.items():
            # Load node class
            node_class = node_loader.load_node_class(node_info.type)

            # Prepare config
            config = {
                **node_info.config,
                "constant_values": node_info.constant_values
            }

            # Create actor
            self.create_actor(node_id, node_class, config)

        return self.actors

    def get_actor(self, node_id: str):
        """Get actor reference by node ID"""
        return self.actors.get(node_id)

    def shutdown_all(self):
        """Kill all actors"""
        for actor in self.actors.values():
            ray.kill(actor)
        self.actors.clear()
```

**Important notes**:
- Pass `variable_store_ref` to ALL nodes (even if they don't use it)
- Pass `config` dict with node-specific configuration
- Store actor references by node ID for easy lookup

**Reference files**:
- `rayflow/core/node.py` - See __init__ signature

**Testing**:
```python
# Test creating single actor
# Test creating all actors from graph
# Test actor receives correct config
# Test actor can be called (process.remote())
# Test shutdown cleans up actors
```

---

## Phase 3: Execution Logic

### Day 5-7: Execution Components

#### Module 7: ExecutionPlanner

**File**: `rayflow/core/execution_planner.py`

**Purpose**: Determine which nodes are ready to execute

**Classes to implement**:
```python
class NodeState(Enum):
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class ExecutionPlanner:
    def __init__(self, graph: FlowGraph):
        self.graph = graph
        self.node_states: Dict[str, NodeState] = {}

        # Initialize all as pending
        for node_id in graph.nodes:
            self.node_states[node_id] = NodeState.PENDING

    def get_ready_nodes(self) -> List[str]:
        """Return IDs of nodes ready to execute"""
        ready = []

        for node_id in self.graph.nodes:
            if self._is_node_ready(node_id):
                ready.append(node_id)

        return ready

    def _is_node_ready(self, node_id: str) -> bool:
        """Check if node is ready to execute"""
        # Must be pending
        if self.node_states[node_id] != NodeState.PENDING:
            return False

        # All dependencies must be completed
        deps = self.graph.dependencies.get(node_id, [])
        for dep_id in deps:
            if self.node_states[dep_id] != NodeState.COMPLETED:
                return False

        return True

    def mark_in_progress(self, node_id: str):
        """Mark node as currently executing"""
        self.node_states[node_id] = NodeState.IN_PROGRESS

    def mark_completed(self, node_id: str):
        """Mark node as completed"""
        self.node_states[node_id] = NodeState.COMPLETED

    def mark_failed(self, node_id: str):
        """Mark node as failed"""
        self.node_states[node_id] = NodeState.FAILED

    def get_initial_nodes(self) -> List[str]:
        """Return START node"""
        return [self.graph.start_node_id]

    def is_workflow_complete(self) -> bool:
        """Check if any RETURN node completed"""
        for return_id in self.graph.return_node_ids:
            if self.node_states[return_id] == NodeState.COMPLETED:
                return True
        return False
```

**Reference files**:
- `docs/orchestrator-architecture.md` - ExecutionPlanner section

**Testing**:
```python
# Test simple linear flow readiness
# Test parallel branches (both ready after START)
# Test join (not ready until both deps complete)
# Test workflow completion detection
```

---

#### Module 8: DataGatherer

**File**: `rayflow/core/data_gatherer.py`

**Purpose**: Collect inputs for each node from predecessors

**Classes to implement**:
```python
class DataGatherer:
    def __init__(self, graph: FlowGraph):
        self.graph = graph
        self.node_results: Dict[str, dict] = {}

    def gather_inputs(self, node_id: str) -> Dict[str, Any]:
        """Gather all inputs for a node"""
        inputs = {}

        # Get data sources for this node
        data_sources = self.graph.data_flow.get(node_id, {})

        # For each input, get the value from source node
        for input_name, source in data_sources.items():
            # Get result from source node
            source_result = self.node_results.get(source.from_node, {})

            # Extract specific output
            value = source_result.get(source.from_output)

            if value is None:
                raise ValueError(
                    f"Missing output '{source.from_output}' from node '{source.from_node}'"
                )

            inputs[input_name] = value

        return inputs

    def store_result(self, node_id: str, result: dict):
        """Store result from a node"""
        self.node_results[node_id] = result

    def set_external_inputs(self, node_id: str, inputs: dict):
        """Set external inputs (for START node)"""
        self.node_results[node_id] = inputs

    def get_final_result(self, return_node_id: str) -> dict:
        """Get result from RETURN node"""
        return self.node_results.get(return_node_id, {})
```

**Reference files**:
- `docs/orchestrator-architecture.md` - DataGatherer section

**Testing**:
```python
# Test gathering inputs from single source
# Test gathering inputs from multiple sources
# Test external inputs (START node)
# Test error on missing source data
```

---

#### Module 9: NodeExecutor

**File**: `rayflow/core/node_executor.py`

**Purpose**: Execute nodes and return results

**Classes to implement**:
```python
@dataclass
class ExecutionResult:
    success: bool
    node_id: str
    result: Optional[dict] = None
    error: Optional[str] = None
    execution_time: float = 0.0

class NodeExecutor:
    def __init__(self, actor_manager: ActorManager):
        self.actor_manager = actor_manager

    def execute_node(self, node_id: str, inputs: Dict[str, Any]) -> ExecutionResult:
        """Execute a single node synchronously"""
        import time

        start_time = time.time()

        try:
            # Get actor
            actor = self.actor_manager.get_actor(node_id)

            # Execute
            future = actor.process.remote(**inputs)
            result = ray.get(future)

            execution_time = time.time() - start_time

            return ExecutionResult(
                success=True,
                node_id=node_id,
                result=result,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time

            return ExecutionResult(
                success=False,
                node_id=node_id,
                error=str(e),
                execution_time=execution_time
            )

    def execute_batch(self, executions: List[Tuple[str, dict]]) -> List[ExecutionResult]:
        """Execute multiple nodes in parallel"""
        # Create futures
        futures = []
        for node_id, inputs in executions:
            actor = self.actor_manager.get_actor(node_id)
            future = actor.process.remote(**inputs)
            futures.append((node_id, future))

        # Wait for all to complete
        results = []
        for node_id, future in futures:
            try:
                result = ray.get(future)
                results.append(ExecutionResult(
                    success=True,
                    node_id=node_id,
                    result=result
                ))
            except Exception as e:
                results.append(ExecutionResult(
                    success=False,
                    node_id=node_id,
                    error=str(e)
                ))

        return results
```

**Testing**:
```python
# Test executing single node
# Test executing multiple nodes in parallel
# Test error handling
# Test execution timing
```

---

#### Module 10: StateTracker

**File**: `rayflow/core/state_tracker.py`

**Purpose**: Track execution state and metrics

**Classes to implement**:
```python
@dataclass
class ExecutionStats:
    total_time: float
    nodes_executed: int
    nodes_failed: int
    node_times: Dict[str, float]
    errors: List[dict]

class StateTracker:
    def __init__(self, graph: FlowGraph):
        self.graph = graph
        self.node_states = {}
        self.execution_times = {}
        self.errors = []
        self.start_time = None
        self.end_time = None

    def start_workflow(self):
        """Mark workflow start"""
        import time
        self.start_time = time.time()

    def end_workflow(self):
        """Mark workflow end"""
        import time
        self.end_time = time.time()

    def record_execution(self, result: ExecutionResult):
        """Record node execution result"""
        self.execution_times[result.node_id] = result.execution_time

        if not result.success:
            self.errors.append({
                "node_id": result.node_id,
                "error": result.error
            })

    def get_statistics(self) -> ExecutionStats:
        """Get execution statistics"""
        return ExecutionStats(
            total_time=self.end_time - self.start_time if self.end_time else 0,
            nodes_executed=len(self.execution_times),
            nodes_failed=len(self.errors),
            node_times=self.execution_times.copy(),
            errors=self.errors.copy()
        )
```

---

#### Module 11: ErrorHandler

**File**: `rayflow/core/error_handler.py`

**Purpose**: Handle execution errors

**Classes to implement**:
```python
class ErrorStrategy(Enum):
    ABORT = "abort"
    CONTINUE = "continue"
    RETRY = "retry"

class ErrorAction(Enum):
    ABORT_WORKFLOW = "abort"
    RETRY_NODE = "retry"
    CONTINUE = "continue"

class ErrorHandler:
    def __init__(self, strategy: ErrorStrategy = ErrorStrategy.ABORT):
        self.strategy = strategy
        self.retry_counts = {}
        self.max_retries = 3

    def handle_error(self, node_id: str, error: Exception) -> ErrorAction:
        """Decide what to do with an error"""
        if self.strategy == ErrorStrategy.ABORT:
            return ErrorAction.ABORT_WORKFLOW

        elif self.strategy == ErrorStrategy.RETRY:
            retries = self.retry_counts.get(node_id, 0)
            if retries < self.max_retries:
                self.retry_counts[node_id] = retries + 1
                return ErrorAction.RETRY_NODE
            else:
                return ErrorAction.ABORT_WORKFLOW

        elif self.strategy == ErrorStrategy.CONTINUE:
            return ErrorAction.CONTINUE

        return ErrorAction.ABORT_WORKFLOW
```

---

## Phase 4: Main Orchestrator

### Day 8-9: Integration

#### Module 12: Orchestrator

**File**: `rayflow/core/orchestrator.py`

**Purpose**: Coordinate all modules to execute workflows

**Main class**:
```python
class RayFlowOrchestrator:
    def __init__(self, flow_json: dict, error_strategy: ErrorStrategy = ErrorStrategy.ABORT):
        self.flow_json = flow_json
        self.error_strategy = error_strategy

        # Modules (initialized in initialize())
        self.validator = None
        self.graph = None
        self.variable_manager = None
        self.node_loader = None
        self.actor_manager = None
        self.execution_planner = None
        self.data_gatherer = None
        self.node_executor = None
        self.state_tracker = None
        self.error_handler = None

    def initialize(self):
        """PHASE 1: Initialize all modules"""
        # 1. Validate
        self.validator = FlowValidator()
        validation = self.validator.validate(self.flow_json)

        if not validation.is_valid:
            raise ValueError(f"Invalid flow: {validation.errors}")

        # 2. Build graph
        builder = GraphBuilder()
        self.graph = builder.build(self.flow_json)

        # 3. Create variable store
        self.variable_manager = VariableStoreManager()
        initial_vars = self.flow_json.get("variables", {})
        variable_store_ref = self.variable_manager.create_store(initial_vars)

        # 4. Create node loader
        self.node_loader = NodeLoader()

        # 5. Create actors
        self.actor_manager = ActorManager(variable_store_ref)
        self.actor_manager.create_all_actors(self.graph, self.node_loader)

        # 6. Initialize execution modules
        self.execution_planner = ExecutionPlanner(self.graph)
        self.data_gatherer = DataGatherer(self.graph)
        self.node_executor = NodeExecutor(self.actor_manager)
        self.state_tracker = StateTracker(self.graph)
        self.error_handler = ErrorHandler(self.error_strategy)

    def execute(self, external_inputs: dict = None) -> dict:
        """PHASE 2: Execute the workflow"""
        self.state_tracker.start_workflow()

        # Set external inputs for START node
        if external_inputs:
            self.data_gatherer.set_external_inputs(
                self.graph.start_node_id,
                external_inputs
            )

        # Execution loop
        while True:
            # 1. Get ready nodes
            ready_nodes = self.execution_planner.get_ready_nodes()

            # If no nodes ready, check if we're done
            if not ready_nodes:
                if self.execution_planner.is_workflow_complete():
                    break  # RETURN node executed
                else:
                    raise RuntimeError("No nodes ready but workflow not complete - possible deadlock")

            # 2. Gather inputs for each ready node
            executions = []
            for node_id in ready_nodes:
                inputs = self.data_gatherer.gather_inputs(node_id)
                executions.append((node_id, inputs))
                self.execution_planner.mark_in_progress(node_id)

            # 3. Execute nodes in parallel
            results = self.node_executor.execute_batch(executions)

            # 4. Process results
            for result in results:
                self.state_tracker.record_execution(result)

                if result.success:
                    # Store result
                    self.data_gatherer.store_result(result.node_id, result.result)
                    self.execution_planner.mark_completed(result.node_id)
                else:
                    # Handle error
                    action = self.error_handler.handle_error(
                        result.node_id,
                        Exception(result.error)
                    )

                    if action == ErrorAction.ABORT_WORKFLOW:
                        raise RuntimeError(f"Node {result.node_id} failed: {result.error}")
                    elif action == ErrorAction.RETRY_NODE:
                        # Reset to pending for retry
                        self.execution_planner.node_states[result.node_id] = NodeState.PENDING
                    # CONTINUE action does nothing, moves to next nodes

        # PHASE 3: Finalization
        self.state_tracker.end_workflow()

        # Find which RETURN node executed
        executed_return = None
        for return_id in self.graph.return_node_ids:
            if self.execution_planner.node_states[return_id] == NodeState.COMPLETED:
                executed_return = return_id
                break

        # Get final result
        final_result = self.data_gatherer.get_final_result(executed_return)
        stats = self.state_tracker.get_statistics()

        return {
            "success": True,
            "result": final_result,
            "statistics": {
                "total_time": stats.total_time,
                "nodes_executed": stats.nodes_executed,
                "node_times": stats.node_times
            }
        }

    def cleanup(self):
        """PHASE 3: Cleanup resources"""
        if self.actor_manager:
            self.actor_manager.shutdown_all()
        if self.variable_manager:
            self.variable_manager.shutdown()
```

**Usage**:
```python
import ray
ray.init()

# Load flow JSON
with open("my_flow.json") as f:
    flow_json = json.load(f)

# Create orchestrator
orchestrator = RayFlowOrchestrator(flow_json)

# Initialize
orchestrator.initialize()

# Execute
result = orchestrator.execute(external_inputs={"x": 5, "y": 3})

# Cleanup
orchestrator.cleanup()

print(result)
```

**Testing**:
```python
# Test simple linear flow end-to-end
# Test flow with branching
# Test flow with joins
# Test flow with variables
# Test error handling
# Test statistics collection
```

---

## Phase 5: API & UI Integration

### Day 10: API Endpoint

#### API Route

**File**: `rayflow/server/routes.py`

Add execution endpoint:
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rayflow.core.orchestrator import RayFlowOrchestrator
import ray

router = APIRouter()

class ExecuteFlowRequest(BaseModel):
    flow: dict
    inputs: dict = {}

@router.post("/api/flows/execute")
async def execute_flow(request: ExecuteFlowRequest):
    """Execute a workflow"""
    try:
        # Initialize Ray if not already
        if not ray.is_initialized():
            ray.init()

        # Create orchestrator
        orchestrator = RayFlowOrchestrator(request.flow)

        # Initialize
        orchestrator.initialize()

        # Execute
        result = orchestrator.execute(external_inputs=request.inputs)

        # Cleanup
        orchestrator.cleanup()

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Update**: `rayflow/server/app.py`

Add the route:
```python
from rayflow.server.routes import router
app.include_router(router)
```

---

#### UI Integration

**File**: `editor/app.js`

Update the `handleRun` function:
```javascript
const handleRun = async () => {
    // Check if there are nodes
    if (state.nodes.length === 0) {
        antd.message.warning('No nodes to run. Create a flow first!');
        return;
    }

    // Show loading
    const loadingMessage = antd.message.loading('Executing workflow...', 0);

    try {
        // Prepare flow JSON (same format as export)
        const flowJson = {
            metadata: {
                name: "Flow Execution",
                version: "1.0.0",
                created: new Date().toISOString()
            },
            variables: state.variables,
            flow: {
                nodes: state.nodes.map(node => ({
                    id: node.id,
                    type: node.data.path.replace('.py', '').replace(/\//g, '_'),
                    position: node.position,
                    data: node.data
                })),
                edges: state.edges
            }
        };

        // Execute via API
        const response = await fetch('/api/flows/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                flow: flowJson,
                inputs: {} // TODO: Prompt user for inputs
            })
        });

        if (!response.ok) {
            throw new Error(`Execution failed: ${response.statusText}`);
        }

        const result = await response.json();

        // Hide loading
        loadingMessage();

        // Show result
        antd.Modal.success({
            title: 'Workflow Executed Successfully',
            content: (
                <div>
                    <p><strong>Result:</strong></p>
                    <pre>{JSON.stringify(result.result, null, 2)}</pre>
                    <p><strong>Statistics:</strong></p>
                    <ul>
                        <li>Total time: {result.statistics.total_time.toFixed(2)}s</li>
                        <li>Nodes executed: {result.statistics.nodes_executed}</li>
                    </ul>
                </div>
            ),
            width: 600
        });

    } catch (error) {
        // Hide loading
        loadingMessage();

        // Show error
        antd.Modal.error({
            title: 'Execution Failed',
            content: error.message
        });
        console.error('Execution error:', error);
    }
};
```

---

## Testing Strategy

### Unit Tests

Test each module independently:
```bash
pytest tests/core/test_validator.py
pytest tests/core/test_graph_builder.py
pytest tests/core/test_node_loader.py
pytest tests/core/test_variable_store.py
pytest tests/core/test_actor_manager.py
pytest tests/core/test_execution_planner.py
pytest tests/core/test_data_gatherer.py
pytest tests/core/test_node_executor.py
```

### Integration Tests

Test the full orchestrator:
```python
# tests/integration/test_orchestrator.py

def test_simple_linear_flow():
    """Test START → ADD → RETURN"""
    flow_json = load_fixture("simple_linear.json")

    orchestrator = RayFlowOrchestrator(flow_json)
    orchestrator.initialize()
    result = orchestrator.execute({"x": 5, "y": 3})
    orchestrator.cleanup()

    assert result["success"]
    assert result["result"]["sum"] == 8

def test_parallel_branches():
    """Test branching execution"""
    # START → [MATH_A, MATH_B] (parallel) → RETURN

def test_join_nodes():
    """Test join execution"""
    # [MATH_A, MATH_B] → JOIN → RETURN

def test_variables():
    """Test variable system"""
    # START → SET(x=5) → GET(x) → RETURN(x)

def test_error_handling():
    """Test error in execution"""
    # START → DIVIDE_BY_ZERO → should error
```

### Manual Testing

1. **Start the server**: `rayflow create --port 8000`
2. **Create a simple flow** in the UI
3. **Click "Run Flow"**
4. **Verify result appears**

---

## Common Issues & Solutions

### Issue: Ray not initialized
**Solution**: Call `ray.init()` before creating orchestrator

### Issue: Module import errors
**Solution**: Ensure `rayflow` package is installed: `pip install -e .`

### Issue: Actor creation fails
**Solution**: Check node class has `@ray.remote` decorator

### Issue: Execution hangs
**Solution**: Check for circular dependencies in graph

### Issue: Type errors in connections
**Solution**: Verify data types match in `inputs` and `outputs`

---

## Debugging Tips

### Enable Ray Logging
```python
import ray
ray.init(logging_level="DEBUG")
```

### Print Graph Structure
```python
graph = builder.build(flow_json)
print("Dependencies:", graph.dependencies)
print("Data Flow:", graph.data_flow)
print("Topological Order:", graph.topological_order)
```

### Add Logging to Modules
```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Executing node: {node_id}")
logger.debug(f"Inputs: {inputs}")
logger.debug(f"Result: {result}")
```

### Test Individual Nodes
```python
# Test a node in isolation
import ray
ray.init()

from rayflow.nodes.math.add import AddNode

actor = AddNode.remote(store_ref=None, config={})
result = ray.get(actor.process.remote(x=5, y=3))
print(result)  # {"result": 8}
```

---

## Completion Checklist

- [ ] Phase 1: Validator and GraphBuilder implemented and tested
- [ ] Phase 2: Variable store, loader, actor manager working
- [ ] Phase 3: Execution modules (planner, gatherer, executor) working
- [ ] Phase 4: Main orchestrator executes simple flows end-to-end
- [ ] Phase 5: API endpoint added
- [ ] Phase 6: UI "Run Flow" button works
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Manual testing successful
- [ ] Documentation updated

---

## Next Steps After Completion

1. **Add more built-in nodes**: Logic, String, I/O
2. **Flow validation UI**: Show validation errors in editor
3. **Execution visualization**: Highlight executing nodes in real-time
4. **Flow import**: Add "Import Flow" button in UI
5. **CLI command**: `rayflow run flow.json`
6. **Performance optimization**: Caching, batching
7. **Error recovery**: Retry logic, checkpointing

---

## Resources

- **Ray Documentation**: https://docs.ray.io
- **FastAPI Documentation**: https://fastapi.tiangolo.com
- **React Flow Documentation**: https://reactflow.dev
- **Project Docs**: `docs/` directory

---

## Getting Help

If stuck:
1. Review `docs/orchestrator-architecture.md`
2. Check existing nodes for patterns
3. Add logging to see what's happening
4. Test modules independently before integration
5. Ray dashboard: http://localhost:8265 (when Ray is running)
