// Canvas Component with React Flow
function Canvas({ onNodeSelect }) {
    const { ReactFlow, Controls, Background, useNodesState, useEdgesState, addEdge } = window.ReactFlow;

    // Configuration state
    const [typeConfig, setTypeConfig] = React.useState(null);
    const [showShortcuts, setShowShortcuts] = React.useState(false);

    // Flow state
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [nodeIdCounter, setNodeIdCounter] = React.useState(1);
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

        const sourceNode = nodes.find(node => node.id === sourceNodeId);
        const targetNode = nodes.find(node => node.id === targetNodeId);

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
        const existingConnection = edges.find(
            edge => edge.target === targetNodeId && edge.targetHandle === targetHandle
        );

        return !existingConnection;
    }, [edges, nodes]);

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
            const sourceNode = nodes.find(node => node.id === sourceNodeId);
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
            type: 'smoothstep',
            style: style,
            animated: animated
        };

        setEdges((eds) => addEdge(newEdge, eds));
    }, [setEdges, typeConfig, nodes, getTypeColor]);

    // Node selection handling
    const onNodeClick = React.useCallback((event, node) => {
        // Call the parent's onNodeSelect callback with the node data
        if (onNodeSelect) {
            onNodeSelect(node.data);
        }
    }, [onNodeSelect]);

    // Selection change handling
    const onSelectionChange = React.useCallback(({ nodes: selectedNodes }) => {
        if (selectedNodes.length === 1) {
            // Single node selected
            if (onNodeSelect) {
                onNodeSelect(selectedNodes[0].data);
            }
        } else {
            // No nodes or multiple nodes selected
            if (onNodeSelect) {
                onNodeSelect(null);
            }
        }
    }, [onNodeSelect]);

    // Drag and drop
    const onDragOver = React.useCallback((event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);

    const onDrop = React.useCallback((event) => {
        event.preventDefault();

        const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
        const nodeData = JSON.parse(event.dataTransfer.getData('application/reactflow'));

        if (!nodeData || !reactFlowInstance) return;

        const position = reactFlowInstance.project({
            x: event.clientX - reactFlowBounds.left,
            y: event.clientY - reactFlowBounds.top,
        });

        const newNode = {
            id: `node_${String(nodeIdCounter).padStart(3, '0')}`,
            type: 'custom',
            position,
            data: {
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
            },
        };

        setNodes((nds) => nds.concat(newNode));
        setNodeIdCounter((id) => id + 1);
    }, [reactFlowInstance, nodeIdCounter, setNodes]);

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
                nodes={nodes}
                edges={edges}
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