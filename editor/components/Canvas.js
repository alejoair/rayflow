// Canvas Component with React Flow
function Canvas({ onNodeSelect }) {
    const { ReactFlow, Controls, Background, addEdge, applyNodeChanges, applyEdgeChanges } = window.ReactFlow;
    const { state, actions } = useFlow();

    // Configuration state
    const [typeConfig, setTypeConfig] = React.useState(null);
    const [showShortcuts, setShowShortcuts] = React.useState(false);
    const [reactFlowInstance, setReactFlowInstance] = React.useState(null);
    const reactFlowWrapper = React.useRef(null);

    // Load type configuration
    React.useEffect(() => {
        fetch('/config/data-types.json')
            .then(response => response.json())
            .then(data => {
                setTypeConfig(data);
                window.typeConfig = data; // Make available globally for NodeComponent
            })
            .catch(error => {
                console.error('Failed to load type configuration:', error);
                const fallback = {
                    dataTypes: {
                        int: { color: '#4CAF50' }, float: { color: '#2196F3' },
                        str: { color: '#FF9800' }, bool: { color: '#E91E63' },
                        dict: { color: '#9C27B0' }, list: { color: '#00BCD4' },
                        any: { color: '#607D8B' }, exec: { color: '#FFFFFF' }
                    },
                    settings: {
                        handleSize: { exec: 12, data: 10 },
                        connectionWidth: { exec: 3, data: 2 },
                        customNodeIndicator: {
                            color: '#FF6B35', iconColor: '#FF6B35',
                            borderColor: '#FF6B35', badgeText: 'CUSTOM'
                        }
                    }
                };
                setTypeConfig(fallback);
                window.typeConfig = fallback;
            });
    }, []);

    // Custom handlers for React Flow events
    const onNodesChange = React.useCallback((changes) => {
        // Handle React Flow nodes changes and sync with global state
        const updatedNodes = applyNodeChanges(changes, state.nodes);
        actions.setNodes(updatedNodes);
    }, [state.nodes, actions]);

    const onEdgesChange = React.useCallback((changes) => {
        // Handle React Flow edges changes and sync with global state
        const updatedEdges = applyEdgeChanges(changes, state.edges);
        actions.setEdges(updatedEdges);
    }, [state.edges, actions]);


    // Helper functions
    const getTypeColor = (type) => {
        if (!typeConfig) return '#1890ff';
        return typeConfig.dataTypes[type]?.color || '#1890ff';
    };

    const areTypesCompatible = (sourceType, targetType) => {
        if (sourceType === targetType) return true;
        if (sourceType === 'any' || targetType === 'any') return true;
        return false;
    };

    // Node types
    const nodeTypes = {
        custom: NodeComponent
    };

    // Connection validation
    const isValidConnection = React.useCallback((connection) => {
        const sourceHandle = connection.sourceHandle;
        const targetHandle = connection.targetHandle;
        const sourceNodeId = connection.source;
        const targetNodeId = connection.target;

        const sourceNode = state.nodes.find(node => node.id === sourceNodeId);
        const targetNode = state.nodes.find(node => node.id === targetNodeId);

        if (!sourceNode || !targetNode) return false;

        // Exec handles only connect to exec handles
        if (sourceHandle && sourceHandle.includes('exec')) {
            if (!targetHandle || !targetHandle.includes('exec')) return false;
            return true;
        }

        // Data handles validation
        if (sourceHandle && sourceHandle.startsWith('output-')) {
            if (!targetHandle || !targetHandle.startsWith('input-')) return false;

            const sourceFieldName = sourceHandle.replace('output-', '');
            const targetFieldName = targetHandle.replace('input-', '');

            const sourceOutputs = sourceNode.data.outputs || {};
            const targetInputs = targetNode.data.inputs || {};

            const sourceType = sourceOutputs[sourceFieldName];
            const targetType = targetInputs[targetFieldName];

            if (!sourceType || !targetType) return false;
            if (!areTypesCompatible(sourceType, targetType)) return false;
        }

        // Check if target handle already has a connection
        const existingConnection = state.edges.find(
            edge => edge.target === targetNodeId && edge.targetHandle === targetHandle
        );

        return !existingConnection;
    }, [state.edges, state.nodes]);

    // Connection creation
    const onConnect = React.useCallback((params) => {
        const sourceHandle = params.sourceHandle;
        const sourceNodeId = params.source;
        let style = {};
        let animated = false;

        if (sourceHandle && sourceHandle.includes('exec')) {
            const execWidth = typeConfig?.settings?.connectionWidth?.exec || 3;
            style = { stroke: getTypeColor('exec'), strokeWidth: execWidth };
        } else if (sourceHandle && sourceHandle.startsWith('output-')) {
            const sourceNode = state.nodes.find(node => node.id === sourceNodeId);
            if (sourceNode) {
                const sourceFieldName = sourceHandle.replace('output-', '');
                const sourceOutputs = sourceNode.data.outputs || {};
                const sourceType = sourceOutputs[sourceFieldName];

                const dataWidth = typeConfig?.settings?.connectionWidth?.data || 2;
                style = { stroke: getTypeColor(sourceType), strokeWidth: dataWidth };
                animated = true;
            }
        }

        const newEdge = {
            ...params,
            id: `edge-${params.source}-${params.sourceHandle || 'default'}-${params.target}-${params.targetHandle || 'default'}`,
            type: 'smoothstep',
            style: style,
            animated: animated
        };

        actions.addEdge(newEdge);
    }, [actions, typeConfig, state.nodes, getTypeColor]);

    // Node selection handling
    const onNodeClick = React.useCallback((event, node) => {
        // Call the parent's onNodeSelect callback with the complete node (includes id and data)
        if (onNodeSelect) {
            onNodeSelect(node);
        }
    }, [onNodeSelect]);

    // Selection change handling
    const onSelectionChange = React.useCallback(({ nodes: selectedNodes }) => {
        if (selectedNodes.length === 1) {
            // Single node selected - pass complete node
            const selectedNode = selectedNodes[0];
            const currentSelectedId = state.selectedNode?.id;
            const newSelectedId = selectedNode?.id;

            // Only call if the selection actually changed
            if (onNodeSelect && currentSelectedId !== newSelectedId) {
                onNodeSelect(selectedNode);
            }
        } else {
            // No nodes or multiple nodes selected - only call if we currently have a selection
            if (onNodeSelect && state.selectedNode !== null) {
                onNodeSelect(null);
            }
        }
    }, [onNodeSelect, state.selectedNode]);

    // Drag and drop
    const onDragOver = React.useCallback((event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);

    const onDrop = React.useCallback((event) => {
        event.preventDefault();
        console.log('NODE DROP: Event triggered');

        const nodeData = JSON.parse(event.dataTransfer.getData('application/reactflow'));
        console.log('NODE DROP: nodeData parsed:', nodeData);

        if (!nodeData || !reactFlowInstance) {
            console.log('NODE DROP: Missing nodeData or reactFlowInstance');
            return;
        }

        // Use screenToFlowPosition instead of deprecated project()
        const position = reactFlowInstance.screenToFlowPosition({
            x: event.clientX,
            y: event.clientY,
        });

        const nodeDataForFlow = {
            label: nodeData.name,
            path: nodeData.type,
            nodeType: nodeData.nodeType,
            icon: nodeData.icon,
            category: nodeData.category,
            inputs: nodeData.inputs || {},
            outputs: nodeData.outputs || {},
            exec_input: nodeData.exec_input !== undefined ? nodeData.exec_input : true,
            exec_output: nodeData.exec_output !== undefined ? nodeData.exec_output : true,
            constants: nodeData.constants || {},
            type: nodeData.nodeType
        };

        console.log('NODE DROP: Calling actions.addNode with position:', position, 'data:', nodeDataForFlow);
        actions.addNode(position, nodeDataForFlow);
        console.log('NODE DROP: actions.addNode called successfully');
    }, [reactFlowInstance, actions]);

    return (
        <div ref={reactFlowWrapper} style={{ width: '100%', height: '100%', position: 'relative' }}>
            {/* Shortcuts Button */}
            <antd.Button
                type="default"
                size="small"
                icon={<i className="fas fa-keyboard"></i>}
                onClick={() => setShowShortcuts(true)}
                style={{
                    position: 'absolute',
                    top: '10px',
                    right: '10px',
                    zIndex: 10,
                    boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
                }}
            />

            {/* Shortcuts Modal */}
            <ShortcutsModal
                visible={showShortcuts}
                onClose={() => setShowShortcuts(false)}
            />

            <ReactFlow
                nodes={state.nodes}
                edges={state.edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                isValidConnection={isValidConnection}
                onInit={setReactFlowInstance}
                onDrop={onDrop}
                onDragOver={onDragOver}
                onNodeClick={onNodeClick}
                onSelectionChange={onSelectionChange}
                nodeTypes={nodeTypes}
                defaultEdgeOptions={{ type: 'smoothstep' }}
                deleteKeyCode="Delete"
                fitView
            >
                <Controls />
                <Background variant="dots" gap={12} size={1} />
            </ReactFlow>
        </div>
    );
}