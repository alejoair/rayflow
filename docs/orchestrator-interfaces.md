# Orchestrator Module Interfaces

This document defines the **technical interfaces** for each module in the orchestrator system. These are the concrete method signatures, data structures, and contracts that modules use to communicate.

---

## Data Structures

### Core Data Types

```python
# Flow structure (from JSON)
FlowData = dict  # The raw flow JSON from frontend
{
    "nodes": [
        {
            "id": str,           # Unique node instance ID
            "type": str,         # Node class path (e.g., "rayflow.nodes.math.add.AddNode")
            "data": {
                "label": str,
                "constants": dict,  # Configured constant values
                "constantValues": dict,
                ...
            },
            "position": {"x": float, "y": float}
        },
        ...
    ],
    "edges": [
        {
            "id": str,
            "source": str,       # Source node ID
            "target": str,       # Target node ID
            "sourceHandle": str, # Output handle name
            "targetHandle": str, # Input handle name
            "type": str         # "exec" or data type
        },
        ...
    ]
}

# Execution inputs (from API call)
ExecutionInputs = dict  # User-provided input values
{
    "input_name": value,
    ...
}

# Node metadata (from node scanner)
NodeMetadata = dict
{
    "path": str,              # Full Python path to class
    "name": str,              # Display name
    "class_name": str,        # Python class name
    "inputs": dict,           # {name: type}
    "outputs": dict,          # {name: type}
    "exec_input": bool,
    "exec_output": bool,
    "constants": dict,        # {name: {type, value}}
    ...
}

# Execution graph (internal representation)
ExecutionGraph = dict
{
    "nodes": {
        node_id: {
            "id": str,
            "class_path": str,
            "metadata": NodeMetadata,
            "constants": dict,     # Configured values
            "dependencies": list,  # [node_id, ...]
            "dependents": list,    # [node_id, ...]
        },
        ...
    },
    "edges": {
        edge_id: {
            "source": str,
            "target": str,
            "source_handle": str,
            "target_handle": str,
            "edge_type": str,  # "exec" or "data"
        },
        ...
    },
    "start_node": str,         # ID of START node
    "return_nodes": [str],     # IDs of RETURN nodes
    "execution_order": [str],  # Topologically sorted node IDs
}

# Node execution result
NodeResult = dict
{
    "node_id": str,
    "status": str,             # "success", "error", "skipped"
    "outputs": dict,           # {output_name: value}
    "error": Optional[str],    # Error message if failed
    "exec_next": Optional[str], # Which exec output was taken
}

# Execution state
ExecutionState = dict
{
    "node_states": {
        node_id: {
            "status": str,     # "pending", "ready", "running", "completed", "failed"
            "result": Optional[NodeResult],
        },
        ...
    },
    "data_cache": {
        (node_id, output_name): value,  # Cached output values
        ...
    },
    "active_path": str,        # Currently executing path
}
```

---

## Module Interfaces

### 1. FlowValidator

**Purpose**: Validate flow structure and rules

```python
class FlowValidator:
    """Validates flow structure before execution"""

    def validate(self, flow_data: FlowData) -> tuple[bool, list[str]]:
        """
        Validate the flow structure

        Args:
            flow_data: Raw flow JSON from frontend

        Returns:
            (is_valid, errors)
            - is_valid: True if valid, False otherwise
            - errors: List of validation error messages
        """
        pass

    def _check_single_start(self, flow_data: FlowData) -> list[str]:
        """Ensure exactly one START node exists"""
        pass

    def _check_at_least_one_return(self, flow_data: FlowData) -> list[str]:
        """Ensure at least one RETURN node exists"""
        pass

    def _check_all_nodes_reachable(self, flow_data: FlowData) -> list[str]:
        """Ensure all nodes are reachable from START"""
        pass

    def _check_return_nodes_reachable(self, flow_data: FlowData) -> list[str]:
        """Ensure at least one RETURN is reachable"""
        pass

    def _check_no_cycles(self, flow_data: FlowData) -> list[str]:
        """Ensure no execution cycles exist"""
        pass

    def _check_type_compatibility(self, flow_data: FlowData) -> list[str]:
        """Ensure connected ports have compatible types"""
        pass
```

**Input**: `FlowData` (raw JSON)
**Output**: `(bool, list[str])` - validity status and error messages
**Dependencies**: None
**Used By**: Orchestrator (first step)

---

### 2. GraphBuilder

**Purpose**: Convert flow JSON to execution graph

```python
class GraphBuilder:
    """Builds execution graph from validated flow"""

    def __init__(self, node_metadata_map: dict[str, NodeMetadata]):
        """
        Args:
            node_metadata_map: Map of class_path -> NodeMetadata
        """
        pass

    def build_graph(self, flow_data: FlowData) -> ExecutionGraph:
        """
        Build execution graph from flow

        Args:
            flow_data: Validated flow JSON

        Returns:
            ExecutionGraph with dependencies and execution order
        """
        pass

    def _build_dependency_graph(self, flow_data: FlowData) -> dict:
        """Build node dependency relationships"""
        pass

    def _topological_sort(self, dependencies: dict) -> list[str]:
        """
        Compute topological execution order

        Returns:
            List of node IDs in execution order
        """
        pass

    def _identify_special_nodes(self, flow_data: FlowData) -> dict:
        """Identify START and RETURN nodes"""
        pass
```

**Input**: `FlowData` (validated), node metadata map
**Output**: `ExecutionGraph` (internal representation)
**Dependencies**: Node metadata from NodeLoader
**Used By**: Orchestrator (after validation)

---

### 3. NodeLoader

**Purpose**: Load and instantiate node classes

```python
class NodeLoader:
    """Loads node classes and metadata"""

    def __init__(self):
        self._class_cache: dict[str, type] = {}

    def load_node_class(self, class_path: str) -> type:
        """
        Load a node class by its full Python path

        Args:
            class_path: e.g., "rayflow.nodes.math.add.AddNode"

        Returns:
            The node class (not instantiated)

        Raises:
            ImportError: If class cannot be imported
        """
        pass

    def get_node_metadata(self, class_path: str) -> NodeMetadata:
        """
        Get metadata for a node class

        Args:
            class_path: Full path to node class

        Returns:
            NodeMetadata extracted via AST or inspection
        """
        pass

    def load_all_metadata(self, flow_data: FlowData) -> dict[str, NodeMetadata]:
        """
        Load metadata for all nodes in flow

        Args:
            flow_data: Flow JSON

        Returns:
            Map of class_path -> NodeMetadata
        """
        pass
```

**Input**: Class paths (strings)
**Output**: Node classes and metadata
**Dependencies**: None
**Used By**: ActorManager, GraphBuilder

---

### 4. VariableStoreManager

**Purpose**: Manage global variable store

```python
class VariableStoreManager:
    """Manages the global variable store actor"""

    def __init__(self):
        self._store_actor = None

    def create_store(self, initial_variables: dict) -> ray.ObjectRef:
        """
        Create a new GlobalVariableStore actor

        Args:
            initial_variables: Initial variable values from flow

        Returns:
            Ray actor handle
        """
        pass

    def get_store_handle(self) -> ray.ObjectRef:
        """Get handle to the variable store"""
        pass

    def cleanup(self):
        """Cleanup the variable store actor"""
        pass
```

**Input**: Initial variables (dict)
**Output**: Ray actor handle
**Dependencies**: Ray
**Used By**: Orchestrator (initialization), ActorManager (passed to nodes)

---

### 5. ActorManager

**Purpose**: Create and manage node actors

```python
class ActorManager:
    """Creates and manages Ray actors for nodes"""

    def __init__(self, node_loader: NodeLoader, variable_store: ray.ObjectRef):
        """
        Args:
            node_loader: For loading node classes
            variable_store: Handle to GlobalVariableStore
        """
        pass

    def create_actor(
        self,
        node_id: str,
        class_path: str,
        constants: dict
    ) -> ray.ObjectRef:
        """
        Create a Ray actor for a node

        Args:
            node_id: Unique node instance ID
            class_path: Full path to node class
            constants: Configured constant values

        Returns:
            Ray actor handle
        """
        pass

    def get_actor(self, node_id: str) -> ray.ObjectRef:
        """Get actor handle for a node"""
        pass

    def cleanup_actors(self):
        """Cleanup all created actors"""
        pass

    def _configure_actor(self, actor: ray.ObjectRef, constants: dict):
        """Apply constant configuration to actor"""
        pass
```

**Input**: Node info, constants
**Output**: Ray actor handles
**Dependencies**: NodeLoader, VariableStoreManager
**Used By**: Orchestrator (initialization)

---

### 6. ExecutionPlanner

**Purpose**: Determine next nodes to execute

```python
class ExecutionPlanner:
    """Plans which nodes to execute next"""

    def __init__(self, execution_graph: ExecutionGraph):
        """
        Args:
            execution_graph: The execution graph
        """
        pass

    def get_next_nodes(
        self,
        current_state: ExecutionState,
        last_result: Optional[NodeResult]
    ) -> list[str]:
        """
        Determine which nodes can execute next

        Args:
            current_state: Current execution state
            last_result: Result from last executed node (for exec flow)

        Returns:
            List of node IDs ready to execute (may be multiple for parallel)
        """
        pass

    def _check_node_ready(
        self,
        node_id: str,
        execution_state: ExecutionState
    ) -> bool:
        """
        Check if a node is ready to execute
        (all dependencies satisfied)
        """
        pass

    def _get_exec_successors(
        self,
        node_id: str,
        exec_output: str
    ) -> list[str]:
        """Get nodes connected via exec from this node"""
        pass
```

**Input**: Execution graph, current state, last result
**Output**: List of nodes to execute next
**Dependencies**: ExecutionGraph
**Used By**: Orchestrator (execution loop)

---

### 7. DataGatherer

**Purpose**: Collect input data for node execution

```python
class DataGatherer:
    """Gathers input data for node execution"""

    def __init__(self, execution_graph: ExecutionGraph):
        """
        Args:
            execution_graph: The execution graph
        """
        pass

    def gather_inputs(
        self,
        node_id: str,
        execution_state: ExecutionState
    ) -> dict:
        """
        Gather all inputs for a node

        Args:
            node_id: Node to gather inputs for
            execution_state: Current execution state (has data cache)

        Returns:
            Dictionary of {input_name: value}

        Raises:
            DataNotAvailableError: If required input data is missing
        """
        pass

    def _get_connected_outputs(self, node_id: str) -> list[tuple]:
        """
        Get list of (source_node_id, source_output_name, target_input_name)
        for all data edges connected to this node
        """
        pass

    def _apply_default_values(self, node_id: str, inputs: dict) -> dict:
        """Apply default values for missing optional inputs"""
        pass
```

**Input**: Node ID, execution state
**Output**: Input data dictionary
**Dependencies**: ExecutionGraph, ExecutionState
**Used By**: NodeExecutor

---

### 8. NodeExecutor

**Purpose**: Execute individual nodes

```python
class NodeExecutor:
    """Executes individual nodes"""

    def __init__(
        self,
        actor_manager: ActorManager,
        data_gatherer: DataGatherer
    ):
        """
        Args:
            actor_manager: For getting actor handles
            data_gatherer: For gathering input data
        """
        pass

    async def execute_node(
        self,
        node_id: str,
        execution_state: ExecutionState
    ) -> NodeResult:
        """
        Execute a single node

        Args:
            node_id: Node to execute
            execution_state: Current execution state

        Returns:
            NodeResult with outputs or error
        """
        pass

    async def execute_nodes_parallel(
        self,
        node_ids: list[str],
        execution_state: ExecutionState
    ) -> list[NodeResult]:
        """
        Execute multiple nodes in parallel using Ray

        Args:
            node_ids: List of node IDs to execute
            execution_state: Current execution state

        Returns:
            List of NodeResults (one per node)
        """
        pass

    def _handle_execution_error(self, node_id: str, error: Exception) -> NodeResult:
        """Create error result from exception"""
        pass
```

**Input**: Node ID, execution state
**Output**: NodeResult
**Dependencies**: ActorManager, DataGatherer
**Used By**: Orchestrator (execution loop)

---

### 9. StateTracker

**Purpose**: Track execution state

```python
class StateTracker:
    """Tracks execution state throughout workflow"""

    def __init__(self, execution_graph: ExecutionGraph):
        """
        Args:
            execution_graph: The execution graph
        """
        self._state: ExecutionState = self._initialize_state()

    def get_state(self) -> ExecutionState:
        """Get current execution state"""
        pass

    def update_node_status(self, node_id: str, status: str):
        """Update a node's status"""
        pass

    def store_node_result(self, node_id: str, result: NodeResult):
        """
        Store node execution result and cache outputs

        Args:
            node_id: Node that was executed
            result: Execution result with outputs
        """
        pass

    def cache_output(self, node_id: str, output_name: str, value: any):
        """Cache an output value for later use"""
        pass

    def get_cached_output(self, node_id: str, output_name: str) -> any:
        """Retrieve a cached output value"""
        pass

    def is_complete(self) -> bool:
        """Check if execution is complete (RETURN node reached)"""
        pass

    def _initialize_state(self) -> ExecutionState:
        """Initialize execution state for all nodes"""
        pass
```

**Input**: Node results
**Output**: ExecutionState (updated)
**Dependencies**: ExecutionGraph
**Used By**: Orchestrator (throughout execution)

---

### 10. ErrorHandler

**Purpose**: Handle execution errors

```python
class ErrorHandler:
    """Handles errors during execution"""

    def __init__(self):
        self._errors: list[dict] = []

    def handle_node_error(
        self,
        node_id: str,
        error: Exception,
        execution_state: ExecutionState
    ) -> dict:
        """
        Handle an error from node execution

        Args:
            node_id: Node that failed
            error: The exception
            execution_state: Current state

        Returns:
            Error information dict with context
        """
        pass

    def should_continue(self, error_info: dict) -> bool:
        """
        Determine if execution should continue after error

        Args:
            error_info: Error details

        Returns:
            True if execution can continue, False to abort
        """
        pass

    def get_error_report(self) -> dict:
        """Get complete error report"""
        pass

    def format_error_message(self, error_info: dict) -> str:
        """Format error for user display"""
        pass
```

**Input**: Exceptions, node context
**Output**: Error handling decisions
**Dependencies**: None
**Used By**: Orchestrator (when errors occur)

---

## Main Orchestrator Interface

```python
class FlowOrchestrator:
    """Main orchestrator that coordinates all modules"""

    def __init__(self):
        """Initialize all sub-modules"""
        self.validator = FlowValidator()
        self.node_loader = NodeLoader()
        self.graph_builder = None  # Created after loading metadata
        self.variable_manager = VariableStoreManager()
        self.actor_manager = None  # Created after variable store
        self.execution_planner = None  # Created after graph
        self.data_gatherer = None  # Created after graph
        self.node_executor = None  # Created after actor manager
        self.state_tracker = None  # Created after graph
        self.error_handler = ErrorHandler()

    async def execute_flow(
        self,
        flow_data: FlowData,
        inputs: ExecutionInputs
    ) -> dict:
        """
        Execute a complete workflow

        Args:
            flow_data: Flow JSON from frontend
            inputs: User-provided input values

        Returns:
            {
                "success": bool,
                "result": dict,      # Output from RETURN node
                "error": Optional[str],
                "execution_time": float,
                "nodes_executed": int
            }
        """
        pass

    def _initialize(self, flow_data: FlowData) -> bool:
        """
        Initialization phase
        Returns True if successful, False otherwise
        """
        pass

    async def _execution_loop(self, start_inputs: dict) -> dict:
        """
        Main execution loop
        Returns result from RETURN node
        """
        pass

    def _finalize(self):
        """Cleanup phase"""
        pass
```

---

## Module Communication Flow

```
FlowOrchestrator.execute_flow(flow_data, inputs)
    ↓
1. INITIALIZATION PHASE
    FlowValidator.validate(flow_data) → (valid, errors)
    NodeLoader.load_all_metadata(flow_data) → metadata_map
    GraphBuilder.build_graph(flow_data) → execution_graph
    VariableStoreManager.create_store(initial_vars) → store_handle
    ActorManager.create_actors(graph, store_handle) → actor_handles
    StateTracker.__init__(execution_graph) → state
    ExecutionPlanner.__init__(execution_graph)
    DataGatherer.__init__(execution_graph)
    NodeExecutor.__init__(actor_manager, data_gatherer)

2. EXECUTION LOOP PHASE
    while not state_tracker.is_complete():
        ↓
        next_nodes = ExecutionPlanner.get_next_nodes(state, last_result)
        ↓
        results = NodeExecutor.execute_nodes_parallel(next_nodes, state)
        ↓
        for result in results:
            if result.status == "error":
                error_info = ErrorHandler.handle_node_error(...)
                if not ErrorHandler.should_continue(error_info):
                    break
            StateTracker.store_node_result(node_id, result)
        ↓
        if RETURN node reached:
            break

3. FINALIZATION PHASE
    ActorManager.cleanup_actors()
    VariableStoreManager.cleanup()
    ↓
    return result
```

---

## Error Handling Protocol

**All modules should raise specific exceptions**:

```python
# Validation errors
class ValidationError(Exception):
    """Flow structure validation failed"""
    pass

# Graph building errors
class GraphBuildError(Exception):
    """Failed to build execution graph"""
    pass

# Node loading errors
class NodeLoadError(Exception):
    """Failed to load node class"""
    pass

# Data gathering errors
class DataNotAvailableError(Exception):
    """Required input data not available"""
    pass

# Execution errors
class NodeExecutionError(Exception):
    """Node execution failed"""
    def __init__(self, node_id: str, original_error: Exception):
        self.node_id = node_id
        self.original_error = original_error
        super().__init__(f"Node {node_id} failed: {original_error}")
```

**Error handling pattern**:
1. Module raises specific exception
2. Orchestrator catches and passes to ErrorHandler
3. ErrorHandler decides: continue or abort
4. If abort: cleanup and return error response
5. If continue: log error and proceed

---

## Thread Safety and Async

**Ray Actors (Thread-Safe by Design)**:
- `GlobalVariableStore` - Ray actor (automatically serialized access)
- Node actors - Ray actors (each has own event loop)

**Async Execution**:
- `NodeExecutor.execute_node()` - async (waits for Ray remote calls)
- `NodeExecutor.execute_nodes_parallel()` - async (concurrent Ray calls)
- `FlowOrchestrator.execute_flow()` - async (main entry point)

**Synchronous**:
- All other modules - synchronous (no I/O, just data processing)

---

## Testing Interfaces

Each module should provide test fixtures:

```python
# Example for GraphBuilder
def test_build_simple_linear_graph():
    flow_data = {
        "nodes": [...],
        "edges": [...]
    }
    metadata_map = {...}

    builder = GraphBuilder(metadata_map)
    graph = builder.build_graph(flow_data)

    assert graph["start_node"] == "start_1"
    assert len(graph["execution_order"]) == 3
    assert graph["nodes"]["node_2"]["dependencies"] == ["node_1"]
```

**Test data should be in**: `tests/fixtures/`

---

## Summary

This document defines:
- ✅ All data structures used between modules
- ✅ Complete method signatures for each module
- ✅ Input/output contracts
- ✅ Dependency relationships
- ✅ Error handling protocol
- ✅ Async/thread safety requirements
- ✅ Communication flow diagram

**Next Step**: Begin implementing modules in order (FlowValidator → GraphBuilder → ...)
