// Canvas Component with React Flow
function Canvas({ onNodeSelect }) {
    const { ReactFlow, Controls, Background, addEdge, applyNodeChanges, applyEdgeChanges } = window.ReactFlow;
    const { state, actions } = useFlow();

    // Configuration state
    const [typeConfig, setTypeConfig] = React.useState(null);
    const [showShortcuts, setShowShortcuts] = React.useState(false);
    const [reactFlowInstance, setReactFlowInstance] = React.useState(null);
    const reactFlowWrapper = React.useRef(null);
    const onNodeSelectRef = React.useRef(onNodeSelect);

    // Update ref when prop changes
    React.useEffect(() => {
        onNodeSelectRef.current = onNodeSelect;
    }, [onNodeSelect]);

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
        // Filter only significant changes that need to update global state
        // Ignore 'dimensions' changes which are internal to React Flow rendering
        const significantChanges = changes.filter(change => change.type !== 'dimensions');

        if (significantChanges.length === 0) {
            // Don't log or do anything for dimensions-only changes
            return;
        }

        console.log('📊 NODES CHANGE (significant):', significantChanges.map(c => ({ type: c.type, id: c.id })));

        // Apply changes using the current state from context
        // We access state.nodes directly here but don't include it in dependencies
        const updatedNodes = applyNodeChanges(significantChanges, state.nodes);
        actions.setNodes(updatedNodes);
    }, [actions]);

    const onEdgesChange = React.useCallback((changes) => {
        // Apply edge changes
        const updatedEdges = applyEdgeChanges(changes, state.edges);
        actions.setEdges(updatedEdges);
    }, [actions]);


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
    }, [state.nodes, state.edges]);

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
    }, [actions, typeConfig, getTypeColor, state.nodes]);

    // Add additional React Flow event debugging
    const onNodeMouseEnter = React.useCallback((event, node) => {
        console.log('🖱️ MOUSE ENTER NODE:', { nodeId: node.id, label: node.data?.label });
    }, []);

    const onNodeMouseLeave = React.useCallback((event, node) => {
        console.log('🖱️ MOUSE LEAVE NODE:', { nodeId: node.id, label: node.data?.label });
    }, []);

    // Track drag timing to detect clicks (short drags)
    const dragStartTimeRef = React.useRef(null);
    const dragStartPosRef = React.useRef(null);

    const onNodeDragStart = React.useCallback((event, node) => {
        dragStartTimeRef.current = Date.now();
        dragStartPosRef.current = { x: event.clientX, y: event.clientY };
        console.log('🔄 NODE DRAG START:', { nodeId: node.id, label: node.data?.label });
    }, []);

    const onNodeDragStop = React.useCallback((event, node) => {
        const dragDuration = Date.now() - (dragStartTimeRef.current || 0);
        const dragDistance = dragStartPosRef.current ? Math.sqrt(
            Math.pow(event.clientX - dragStartPosRef.current.x, 2) +
            Math.pow(event.clientY - dragStartPosRef.current.y, 2)
        ) : 0;

        console.log('🔄 NODE DRAG STOP:', {
            nodeId: node.id,
            label: node.data?.label,
            duration: dragDuration,
            distance: Math.round(dragDistance)
        });

        // Treat as click if drag was very short and minimal movement
        if (dragDuration < 200 && dragDistance < 5) {
            console.log('🎯 CLICK DETECTED (via short drag):', { nodeId: node.id, label: node.data?.label });
            // The selection already happened via onSelectionChange, no need to call onNodeSelect again
        }

        dragStartTimeRef.current = null;
        dragStartPosRef.current = null;
    }, []);

    const onPaneClick = React.useCallback((event) => {
        // Deselect when clicking on empty canvas
        if (onNodeSelectRef.current) {
            onNodeSelectRef.current(null);
        }
    }, []);

    // Node selection handling
    const onNodeClick = React.useCallback((event, node) => {
        console.log('🎯 NODE CLICK:', { nodeId: node.id, label: node.data?.label });
        if (onNodeSelectRef.current) {
            onNodeSelectRef.current(node);  // Pasar nodo completo para Inspector
        }
    }, []);

    // Selection change handling - con protección contra bucles
    const lastSelectionRef = React.useRef(null);
    const onSelectionChange = React.useCallback(({ nodes: selectedNodes }) => {
        const newSelectionId = selectedNodes.length === 1 ? selectedNodes[0].id : null;

        // Solo llamar si la selección realmente cambió
        if (lastSelectionRef.current !== newSelectionId) {
            lastSelectionRef.current = newSelectionId;
            console.log('🔄 SELECTION CHANGE:', { count: selectedNodes.length, id: newSelectionId });

            if (selectedNodes.length === 1) {
                if (onNodeSelectRef.current) {
                    onNodeSelectRef.current(selectedNodes[0]);
                }
            } else {
                if (onNodeSelectRef.current) {
                    onNodeSelectRef.current(null);
                }
            }
        }
    }, []);

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