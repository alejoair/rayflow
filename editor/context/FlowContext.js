// Global Flow State Management
const FlowContext = React.createContext();

// Helper function to generate Set/Get nodes for a variable
function generateVariableNodes(variable) {
    const setNode = {
        name: `Set: ${variable.name}`,
        path: `virtual://variables/set_${variable.id}`,
        type: "variable",
        category: "variables",
        icon: "fa-download",
        description: `Set value for variable '${variable.name}'${variable.isCustom ? ' ⚠️ Custom type' : ''}`,
        inputs: { value: variable.type },
        outputs: {},
        exec_input: false,
        exec_output: false,
        isVariable: true,
        variableId: variable.id,
        variableAction: "set",
        constants: {}
    };

    const getNode = {
        name: `Get: ${variable.name}`,
        path: `virtual://variables/get_${variable.id}`,
        type: "variable",
        category: "variables",
        icon: "fa-upload",
        description: `Get value of variable '${variable.name}'${variable.isCustom ? ' ⚠️ Custom type' : ''}`,
        inputs: {},
        outputs: { value: variable.type },
        exec_input: false,
        exec_output: false,
        isVariable: true,
        variableId: variable.id,
        variableAction: "get",
        constants: {}
    };

    // Add custom type metadata if applicable
    if (variable.isCustom) {
        setNode.customType = {
            import: variable.customImport,
            validated: false
        };
        getNode.customType = {
            import: variable.customImport,
            validated: false
        };
    }

    return [setNode, getNode];
}

// Initial state
const initialState = {
    // Flow data
    nodes: [],
    edges: [],
    selectedNode: null,

    // Variables system (future)
    variables: [],

    // UI state
    leftSidebarCollapsed: false,
    rightSidebarCollapsed: false,

    // Node library data
    availableNodes: [],
    loading: true,
    error: null,

    // Counters
    nodeIdCounter: 1
};

// Action types
const ActionTypes = {
    // Node management
    ADD_NODE: 'ADD_NODE',
    UPDATE_NODE: 'UPDATE_NODE',
    DELETE_NODE: 'DELETE_NODE',
    SELECT_NODE: 'SELECT_NODE',
    DESELECT_NODE: 'DESELECT_NODE',

    // Edge management
    ADD_EDGE: 'ADD_EDGE',
    UPDATE_EDGE: 'UPDATE_EDGE',
    DELETE_EDGE: 'DELETE_EDGE',

    // Bulk operations
    SET_NODES: 'SET_NODES',
    SET_EDGES: 'SET_EDGES',
    SET_FLOW_DATA: 'SET_FLOW_DATA',
    SET_NODE_COUNTER: 'SET_NODE_COUNTER',

    // Node constants
    UPDATE_NODE_CONSTANTS: 'UPDATE_NODE_CONSTANTS',

    // Variables
    ADD_VARIABLE: 'ADD_VARIABLE',
    UPDATE_VARIABLE: 'UPDATE_VARIABLE',
    DELETE_VARIABLE: 'DELETE_VARIABLE',
    SET_VARIABLES: 'SET_VARIABLES',

    // Node library
    SET_AVAILABLE_NODES: 'SET_AVAILABLE_NODES',
    SET_LOADING: 'SET_LOADING',
    SET_ERROR: 'SET_ERROR',

    // UI
    TOGGLE_LEFT_SIDEBAR: 'TOGGLE_LEFT_SIDEBAR',
    TOGGLE_RIGHT_SIDEBAR: 'TOGGLE_RIGHT_SIDEBAR'
};

// Reducer
function flowReducer(state, action) {
    switch (action.type) {
        case ActionTypes.ADD_NODE:
            const newNode = {
                id: `node_${String(state.nodeIdCounter).padStart(3, '0')}`,
                type: 'custom',
                position: action.payload.position,
                data: {
                    ...action.payload.data,
                    constantValues: {} // Initialize empty constant values
                }
            };

            return {
                ...state,
                nodes: [...state.nodes, newNode],
                nodeIdCounter: state.nodeIdCounter + 1
            };

        case ActionTypes.UPDATE_NODE:
            return {
                ...state,
                nodes: state.nodes.map(node =>
                    node.id === action.payload.nodeId
                        ? { ...node, ...action.payload.updates }
                        : node
                ),
                // Also update selectedNode if it's the same node
                selectedNode: state.selectedNode && state.selectedNode.id === action.payload.nodeId
                    ? { ...state.selectedNode, ...action.payload.updates }
                    : state.selectedNode
            };

        case ActionTypes.UPDATE_NODE_CONSTANTS:
            return {
                ...state,
                nodes: state.nodes.map(node =>
                    node.id === action.payload.nodeId
                        ? {
                            ...node,
                            data: {
                                ...node.data,
                                constantValues: action.payload.constantValues
                            }
                        }
                        : node
                ),
                // Also update selectedNode if it's the same node
                selectedNode: state.selectedNode && state.selectedNode.id === action.payload.nodeId
                    ? {
                        ...state.selectedNode,
                        data: {
                            ...state.selectedNode.data,
                            constantValues: action.payload.constantValues
                        }
                    }
                    : state.selectedNode
            };

        case ActionTypes.DELETE_NODE:
            const filteredNodes = state.nodes.filter(node => node.id !== action.payload.nodeId);
            const filteredEdges = state.edges.filter(edge =>
                edge.source !== action.payload.nodeId && edge.target !== action.payload.nodeId
            );

            return {
                ...state,
                nodes: filteredNodes,
                edges: filteredEdges,
                selectedNode: state.selectedNode && state.selectedNode.id === action.payload.nodeId
                    ? null
                    : state.selectedNode
            };

        case ActionTypes.SELECT_NODE:
            return {
                ...state,
                selectedNode: action.payload.node
            };

        case ActionTypes.DESELECT_NODE:
            return {
                ...state,
                selectedNode: null
            };

        case ActionTypes.ADD_EDGE:
            return {
                ...state,
                edges: [...state.edges, action.payload.edge]
            };

        case ActionTypes.UPDATE_EDGE:
            return {
                ...state,
                edges: state.edges.map(edge =>
                    edge.id === action.payload.edgeId
                        ? { ...edge, ...action.payload.updates }
                        : edge
                )
            };

        case ActionTypes.DELETE_EDGE:
            return {
                ...state,
                edges: state.edges.filter(edge => edge.id !== action.payload.edgeId)
            };

        case ActionTypes.SET_NODES:
            return {
                ...state,
                nodes: action.payload.nodes
            };

        case ActionTypes.SET_EDGES:
            return {
                ...state,
                edges: action.payload.edges
            };

        case ActionTypes.SET_NODE_COUNTER:
            return {
                ...state,
                nodeIdCounter: action.payload.counter
            };

        case ActionTypes.SET_FLOW_DATA:
            return {
                ...state,
                nodes: action.payload.nodes,
                edges: action.payload.edges
            };

        case ActionTypes.ADD_VARIABLE:
            const newVariable = action.payload.variable;
            const [setNode, getNode] = generateVariableNodes(newVariable);

            return {
                ...state,
                variables: [...state.variables, newVariable],
                availableNodes: [...state.availableNodes, setNode, getNode]
            };

        case ActionTypes.UPDATE_VARIABLE:
            return {
                ...state,
                variables: state.variables.map(variable =>
                    variable.id === action.payload.variableId
                        ? { ...variable, ...action.payload.updates }
                        : variable
                )
            };

        case ActionTypes.DELETE_VARIABLE:
            const deletedVariableId = action.payload.variableId;

            return {
                ...state,
                variables: state.variables.filter(variable => variable.id !== deletedVariableId),
                // Remove Set/Get nodes for this variable
                availableNodes: state.availableNodes.filter(node =>
                    !(node.isVariable && node.variableId === deletedVariableId)
                )
            };

        case ActionTypes.SET_VARIABLES:
            return {
                ...state,
                variables: action.payload.variables
            };

        case ActionTypes.SET_AVAILABLE_NODES:
            return {
                ...state,
                availableNodes: action.payload.nodes,
                loading: false,
                error: null
            };

        case ActionTypes.SET_LOADING:
            return {
                ...state,
                loading: action.payload.loading
            };

        case ActionTypes.SET_ERROR:
            return {
                ...state,
                error: action.payload.error,
                loading: false
            };

        case ActionTypes.TOGGLE_LEFT_SIDEBAR:
            return {
                ...state,
                leftSidebarCollapsed: !state.leftSidebarCollapsed
            };

        case ActionTypes.TOGGLE_RIGHT_SIDEBAR:
            return {
                ...state,
                rightSidebarCollapsed: !state.rightSidebarCollapsed
            };

        default:
            return state;
    }
}

// Provider component
function FlowProvider({ children }) {
    const [state, dispatch] = React.useReducer(flowReducer, initialState);

    // Load available nodes on mount
    React.useEffect(() => {
        async function loadNodesAndVariables() {
            try {
                dispatch({ type: ActionTypes.SET_LOADING, payload: { loading: true } });

                // Load nodes (critical - must succeed)
                const nodesResponse = await fetch('/api/nodes');
                if (!nodesResponse.ok) throw new Error('Failed to fetch nodes');
                const nodesData = await nodesResponse.json();

                // Load variables (optional - can fail gracefully)
                let variables = [];
                let variableNodes = [];
                try {
                    const variablesResponse = await fetch('/api/variables');
                    if (variablesResponse.ok) {
                        const variablesData = await variablesResponse.json();

                        // Convert variables to UI format and generate Set/Get nodes
                        variables = variablesData.map(varFile => ({
                            id: `var_${varFile.variable_name}_${Date.now()}`,
                            name: varFile.variable_name,
                            type: varFile.value_type,
                            defaultValue: varFile.default_value,
                            isCustom: varFile.is_custom,
                            customImport: varFile.custom_import,
                            createdAt: new Date().toISOString(),
                            filePath: varFile.file_path,
                            description: varFile.description,
                            icon: varFile.icon,
                            category: varFile.category
                        }));

                        // Generate Set/Get nodes for each variable
                        variables.forEach(variable => {
                            const [setNode, getNode] = generateVariableNodes(variable);
                            variableNodes.push(setNode, getNode);
                        });

                        console.log('Variables loaded successfully:', variables.length);
                    } else {
                        console.log('No variables endpoint available or no variables found');
                    }
                } catch (varErr) {
                    console.log('Variables loading failed (continuing without variables):', varErr.message);
                }

                // Combine regular nodes with variable nodes
                const allNodes = [...nodesData, ...variableNodes];

                // Dispatch updates
                dispatch({ type: ActionTypes.SET_AVAILABLE_NODES, payload: { nodes: allNodes } });
                dispatch({ type: ActionTypes.SET_VARIABLES, payload: { variables } });

            } catch (err) {
                console.error('Critical error loading nodes:', err);
                dispatch({ type: ActionTypes.SET_ERROR, payload: { error: err.message } });
            }
        }
        loadNodesAndVariables();
    }, []);

    // Auto-save with debounced trigger to avoid loops
    const lastSaveRef = React.useRef({ nodeCount: 0, edgeCount: 0, counter: 0 });
    const saveTimeoutRef = React.useRef(null);

    // Trigger auto-save when state changes (using a separate effect with manual comparison)
    React.useEffect(() => {
        // Skip auto-save during initial loading
        if (state.loading) return;

        const currentCounts = {
            nodeCount: state.nodes.length,
            edgeCount: state.edges.length,
            counter: state.nodeIdCounter
        };

        // Only trigger save if something actually changed
        const hasChanged = (
            currentCounts.nodeCount !== lastSaveRef.current.nodeCount ||
            currentCounts.edgeCount !== lastSaveRef.current.edgeCount ||
            currentCounts.counter !== lastSaveRef.current.counter
        );

        if (hasChanged && (currentCounts.nodeCount > 0 || currentCounts.edgeCount > 0)) {
            console.log('AUTO-SAVE: State changed, triggering save', currentCounts);
            lastSaveRef.current = currentCounts;

            // Clear previous timeout
            if (saveTimeoutRef.current) {
                clearTimeout(saveTimeoutRef.current);
            }

            // Set new timeout for debounced save
            saveTimeoutRef.current = setTimeout(() => {
                const stateToSave = {
                    nodes: state.nodes,
                    edges: state.edges,
                    nodeIdCounter: state.nodeIdCounter
                };

                if (window.AutoSave?.save) {
                    window.AutoSave.save(stateToSave);
                    console.log('AUTO-SAVE: Save completed');
                }
            }, 2000); // 2 second debounce
        }
    });

    // Load auto-saved state on mount if available
    React.useEffect(() => {
        async function loadAutoSave() {
            try {
                console.log('AUTO-LOAD: Checking for auto-saved data...');

                // Check if AutoSave is available
                if (!window.AutoSave) {
                    console.log('AUTO-LOAD: AutoSave system not available');
                    return;
                }

                // Check if there's auto-saved data
                if (!window.AutoSave.hasAutoSave()) {
                    console.log('AUTO-LOAD: No auto-saved data found');
                    return;
                }

                const autoSaveInfo = window.AutoSave.getInfo();
                console.log('AUTO-LOAD: Found auto-save info:', autoSaveInfo);

                if (!autoSaveInfo) {
                    console.log('AUTO-LOAD: Could not get auto-save info');
                    return;
                }

                // Automatically restore if there's meaningful content
                if (autoSaveInfo.nodeCount > 0 || autoSaveInfo.edgeCount > 0) {
                    const ageText = autoSaveInfo.age ?
                        Math.round(autoSaveInfo.age / 1000 / 60) + ' minutes ago' : 'recently';

                    console.log('AUTO-LOAD: Automatically restoring', autoSaveInfo.nodeCount, 'nodes and', autoSaveInfo.edgeCount, 'edges from', ageText);

                    const savedState = window.AutoSave.load();
                    console.log('AUTO-LOAD: Loaded state:', savedState);

                    if (savedState) {
                        // Update lastSaveRef BEFORE dispatching to prevent auto-save trigger
                        lastSaveRef.current = {
                            nodeCount: savedState.nodes.length,
                            edgeCount: savedState.edges.length,
                            counter: savedState.nodeIdCounter
                        };

                        dispatch({ type: ActionTypes.SET_NODES, payload: { nodes: savedState.nodes } });
                        dispatch({ type: ActionTypes.SET_EDGES, payload: { edges: savedState.edges } });
                        dispatch({ type: ActionTypes.SET_NODE_COUNTER, payload: { counter: savedState.nodeIdCounter } });
                        console.log('AUTO-LOAD: State restored successfully');

                        // Show a discrete success message
                        setTimeout(() => {
                            if (window.antd?.message) {
                                window.antd.message.success(`Canvas restored with ${autoSaveInfo.nodeCount} nodes from ${ageText}`);
                            }
                        }, 1000);
                    } else {
                        console.log('AUTO-LOAD: Failed to load saved state');
                    }
                } else {
                    console.log('AUTO-LOAD: Auto-save found but no meaningful content');
                }
            } catch (error) {
                console.error('AUTO-LOAD: Error loading auto-save:', error);
            }
        }

        // Only attempt to load auto-save after nodes are loaded
        if (!state.loading && state.availableNodes.length > 0) {
            console.log('AUTO-LOAD: Conditions met, attempting to load auto-save');
            loadAutoSave();
        } else {
            console.log('AUTO-LOAD: Waiting for conditions - loading:', state.loading, 'availableNodes:', state.availableNodes.length);
        }
    }, [state.loading, state.availableNodes.length]);

    // Action creators (helper functions)
    const actions = {
        // Node actions
        addNode: (position, data) => {
            dispatch({
                type: ActionTypes.ADD_NODE,
                payload: { position, data }
            });
        },

        updateNode: (nodeId, updates) => {
            dispatch({
                type: ActionTypes.UPDATE_NODE,
                payload: { nodeId, updates }
            });
        },

        updateNodeConstants: (nodeId, constantValues) => {
            dispatch({
                type: ActionTypes.UPDATE_NODE_CONSTANTS,
                payload: { nodeId, constantValues }
            });
        },

        deleteNode: (nodeId) => {
            dispatch({
                type: ActionTypes.DELETE_NODE,
                payload: { nodeId }
            });
        },

        selectNode: (node) => {
            dispatch({
                type: ActionTypes.SELECT_NODE,
                payload: { node }
            });
        },

        deselectNode: () => {
            dispatch({ type: ActionTypes.DESELECT_NODE });
        },

        // Edge actions
        addEdge: (edge) => {
            dispatch({
                type: ActionTypes.ADD_EDGE,
                payload: { edge }
            });
        },

        updateEdge: (edgeId, updates) => {
            dispatch({
                type: ActionTypes.UPDATE_EDGE,
                payload: { edgeId, updates }
            });
        },

        deleteEdge: (edgeId) => {
            dispatch({
                type: ActionTypes.DELETE_EDGE,
                payload: { edgeId }
            });
        },

        // Bulk operations
        setNodes: (nodes) => {
            dispatch({
                type: ActionTypes.SET_NODES,
                payload: { nodes }
            });
        },

        setEdges: (edges) => {
            dispatch({
                type: ActionTypes.SET_EDGES,
                payload: { edges }
            });
        },

        setFlowData: (nodes, edges) => {
            dispatch({
                type: ActionTypes.SET_FLOW_DATA,
                payload: { nodes, edges }
            });
        },

        // Variable actions
        addVariable: (variable) => {
            dispatch({
                type: ActionTypes.ADD_VARIABLE,
                payload: { variable }
            });
        },

        updateVariable: (variableId, updates) => {
            dispatch({
                type: ActionTypes.UPDATE_VARIABLE,
                payload: { variableId, updates }
            });
        },

        deleteVariable: (variableId) => {
            dispatch({
                type: ActionTypes.DELETE_VARIABLE,
                payload: { variableId }
            });
        },

        // UI actions
        toggleLeftSidebar: () => {
            dispatch({ type: ActionTypes.TOGGLE_LEFT_SIDEBAR });
        },

        toggleRightSidebar: () => {
            dispatch({ type: ActionTypes.TOGGLE_RIGHT_SIDEBAR });
        }
    };

    return (
        <FlowContext.Provider value={{ state, actions }}>
            {children}
        </FlowContext.Provider>
    );
}

// Custom hook to use the flow context
function useFlow() {
    const context = React.useContext(FlowContext);
    if (!context) {
        throw new Error('useFlow must be used within a FlowProvider');
    }
    return context;
}

// Export everything
window.FlowProvider = FlowProvider;
window.useFlow = useFlow;
window.ActionTypes = ActionTypes;