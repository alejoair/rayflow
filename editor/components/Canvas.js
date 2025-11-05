// Canvas Component with React Flow
function Canvas({ onCanvasClick }) {
    const { ReactFlow, Controls, Background, useNodesState, useEdgesState, addEdge, Handle, Position } = window.ReactFlow;

    // Load data type configuration
    const [typeConfig, setTypeConfig] = React.useState(null);

    React.useEffect(() => {
        // Load type configuration
        fetch('/config/data-types.json')
            .then(response => response.json())
            .then(data => setTypeConfig(data))
            .catch(error => {
                console.error('Failed to load type configuration:', error);
                // Fallback configuration
                setTypeConfig({
                    dataTypes: {
                        int: { color: '#4CAF50' },
                        float: { color: '#2196F3' },
                        str: { color: '#FF9800' },
                        bool: { color: '#E91E63' },
                        dict: { color: '#9C27B0' },
                        list: { color: '#00BCD4' },
                        any: { color: '#607D8B' },
                        exec: { color: '#FFFFFF' }
                    },
                    settings: {
                        handleSize: { exec: 12, data: 10 },
                        connectionWidth: { exec: 3, data: 2 }
                    }
                });
            });
    }, []);

    // Helper function to get color for a data type
    const getTypeColor = (type) => {
        if (!typeConfig) return '#1890ff'; // Default blue
        return typeConfig.dataTypes[type]?.color || '#1890ff';
    };

    // Helper function to get handle size
    const getHandleSize = (isExec) => {
        if (!typeConfig) return isExec ? 12 : 10;
        return typeConfig.settings.handleSize[isExec ? 'exec' : 'data'];
    };

    // Custom Node Component with dynamic handles based on node configuration
    const CustomNode = ({ data, selected }) => {
        const inputs = data.inputs || {};
        const outputs = data.outputs || {};
        const hasDataInputs = Object.keys(inputs).length > 0;
        const hasDataOutputs = Object.keys(outputs).length > 0;
        const execInput = data.exec_input !== undefined ? data.exec_input : true;
        const execOutput = data.exec_output !== undefined ? data.exec_output : true;

        // Calculate handle positions dynamically
        const inputHandles = [];
        const outputHandles = [];
        let inputIndex = 0;
        let outputIndex = 0;

        // Add exec input handle if needed
        if (execInput) {
            const execSize = getHandleSize(true);
            inputHandles.push(
                <Handle
                    key="exec-in"
                    type="target"
                    position={Position.Left}
                    id="exec-in"
                    style={{
                        top: hasDataInputs ? '25%' : '50%',
                        background: getTypeColor('exec'),
                        width: `${execSize}px`,
                        height: `${execSize}px`
                    }}
                />
            );
        }

        // Add individual data input handles
        if (hasDataInputs) {
            const inputKeys = Object.keys(inputs);
            const startPosition = execInput ? 60 : 30; // Starting position in px
            const spacing = 25; // Spacing between handles

            inputKeys.forEach((inputName, index) => {
                const inputType = inputs[inputName];
                const dataSize = getHandleSize(false);
                inputHandles.push(
                    <Handle
                        key={`input-${inputName}`}
                        type="target"
                        position={Position.Left}
                        id={`input-${inputName}`}
                        style={{
                            top: `${startPosition + (index * spacing)}px`,
                            background: getTypeColor(inputType),
                            width: `${dataSize}px`,
                            height: `${dataSize}px`
                        }}
                    />
                );
            });
        }

        // Add exec output handle if needed
        if (execOutput) {
            const execSize = getHandleSize(true);
            outputHandles.push(
                <Handle
                    key="exec-out"
                    type="source"
                    position={Position.Right}
                    id="exec-out"
                    style={{
                        top: hasDataOutputs ? '25%' : '50%',
                        background: getTypeColor('exec'),
                        width: `${execSize}px`,
                        height: `${execSize}px`
                    }}
                />
            );
        }

        // Add individual data output handles
        if (hasDataOutputs) {
            const outputKeys = Object.keys(outputs);
            const startPosition = execOutput ? 60 : 30; // Starting position in px
            const spacing = 25; // Spacing between handles

            outputKeys.forEach((outputName, index) => {
                const outputType = outputs[outputName];
                const dataSize = getHandleSize(false);
                outputHandles.push(
                    <Handle
                        key={`output-${outputName}`}
                        type="source"
                        position={Position.Right}
                        id={`output-${outputName}`}
                        style={{
                            top: `${startPosition + (index * spacing)}px`,
                            background: getTypeColor(outputType),
                            width: `${dataSize}px`,
                            height: `${dataSize}px`
                        }}
                    />
                );
            });
        }

        // Calculate node height based on number of inputs/outputs
        const maxPorts = Math.max(
            (execInput ? 1 : 0) + Object.keys(inputs).length,
            (execOutput ? 1 : 0) + Object.keys(outputs).length
        );
        const nodeHeight = Math.max(80, 40 + (maxPorts * 25));

        return (
            <div style={{
                padding: '15px',
                borderRadius: '5px',
                background: '#1a1a1a',
                border: selected ? '2px solid #1890ff' : '2px solid #333',
                boxShadow: selected ? '0 0 10px rgba(24, 144, 255, 0.5)' : 'none',
                color: 'white',
                minWidth: '180px',
                minHeight: `${nodeHeight}px`,
                transition: 'all 0.2s ease',
                position: 'relative'
            }}>
                {/* Dynamic input handles */}
                {inputHandles}

                {/* Input labels */}
                {hasDataInputs && Object.keys(inputs).map((inputName, index) => {
                    const inputType = inputs[inputName];
                    return (
                        <div
                            key={`input-label-${inputName}`}
                            style={{
                                position: 'absolute',
                                left: '20px',
                                top: `${(execInput ? 60 : 30) + (index * 25) - 8}px`,
                                fontSize: '11px',
                                color: getTypeColor(inputType),
                                fontWeight: '500'
                            }}
                        >
                            {inputName}: {inputType}
                        </div>
                    );
                })}

                {/* Label del nodo con icono */}
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    fontSize: '14px',
                    fontWeight: '500',
                    marginBottom: hasDataInputs || hasDataOutputs ? '10px' : '0'
                }}>
                    {data.icon && (
                        <i className={`fas ${data.icon}`} style={{
                            color: '#1890ff',
                            fontSize: '16px'
                        }}></i>
                    )}
                    <span>{data.label ? data.label.charAt(0).toUpperCase() + data.label.slice(1) : 'Unknown'}</span>
                </div>

                {/* Output labels */}
                {hasDataOutputs && Object.keys(outputs).map((outputName, index) => {
                    const outputType = outputs[outputName];
                    return (
                        <div
                            key={`output-label-${outputName}`}
                            style={{
                                position: 'absolute',
                                right: '20px',
                                top: `${(execOutput ? 60 : 30) + (index * 25) - 8}px`,
                                fontSize: '11px',
                                color: getTypeColor(outputType),
                                fontWeight: '500',
                                textAlign: 'right'
                            }}
                        >
                            {outputName}: {outputType}
                        </div>
                    );
                })}

                {/* Dynamic output handles */}
                {outputHandles}
            </div>
        );
    };

    const nodeTypes = {
        custom: CustomNode
    };

    const initialNodes = [
        {
            id: '1',
            type: 'custom',
            data: {
                label: 'start',
                icon: 'fa-play',
                category: 'base',
                inputs: {},
                outputs: {},
                exec_input: false,
                exec_output: true
            },
            position: { x: 50, y: 100 },
        },
        {
            id: '2',
            type: 'custom',
            data: {
                label: 'add',
                icon: 'fa-plus',
                category: 'math',
                inputs: { x: 'int', y: 'int' },
                outputs: { result: 'int' },
                exec_input: true,
                exec_output: true
            },
            position: { x: 300, y: 100 },
        },
        {
            id: '3',
            type: 'custom',
            data: {
                label: 'return',
                icon: 'fa-flag-checkered',
                category: 'base',
                inputs: {},
                outputs: {},
                exec_input: true,
                exec_output: false
            },
            position: { x: 550, y: 100 },
        },
    ];

    const initialEdges = [
        // Conexiones exec (señales de activación) - blancas
        {
            id: 'exec1-2',
            source: '1',
            target: '2',
            sourceHandle: 'exec-out',
            targetHandle: 'exec-in',
            type: 'smoothstep',
            style: { stroke: '#fff', strokeWidth: 3 }
        },
        {
            id: 'exec2-3',
            source: '2',
            target: '3',
            sourceHandle: 'exec-out',
            targetHandle: 'exec-in',
            type: 'smoothstep',
            style: { stroke: '#fff', strokeWidth: 3 }
        }
        // Note: Removed data connections as they would need specific field connections
        // Users can now connect specific outputs to specific inputs with type validation
    ];

    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
    const [nodeIdCounter, setNodeIdCounter] = React.useState(4); // Start from 4 since we have 3 initial nodes
    const [reactFlowInstance, setReactFlowInstance] = React.useState(null);
    const reactFlowWrapper = React.useRef(null);
    const [showShortcuts, setShowShortcuts] = React.useState(false);

    const isValidConnection = React.useCallback((connection) => {
        // Get the handle IDs from the connection
        const sourceHandle = connection.sourceHandle;
        const targetHandle = connection.targetHandle;
        const sourceNodeId = connection.source;
        const targetNodeId = connection.target;

        // Get source and target nodes
        const sourceNode = nodes.find(node => node.id === sourceNodeId);
        const targetNode = nodes.find(node => node.id === targetNodeId);

        if (!sourceNode || !targetNode) {
            return false;
        }

        // Type validation: Exec handles can only connect to exec handles
        if (sourceHandle && sourceHandle.includes('exec')) {
            if (!targetHandle || !targetHandle.includes('exec')) {
                return false;
            }
            return true; // Exec connections are always compatible
        }

        // Type validation: Data handles can only connect to data handles
        if (sourceHandle && sourceHandle.startsWith('output-')) {
            if (!targetHandle || !targetHandle.startsWith('input-')) {
                return false;
            }

            // Extract the field names from handle IDs
            const sourceFieldName = sourceHandle.replace('output-', '');
            const targetFieldName = targetHandle.replace('input-', '');

            // Get the data types from node configurations
            const sourceOutputs = sourceNode.data.outputs || {};
            const targetInputs = targetNode.data.inputs || {};

            const sourceType = sourceOutputs[sourceFieldName];
            const targetType = targetInputs[targetFieldName];

            if (!sourceType || !targetType) {
                return false; // Field not found
            }

            // Check type compatibility
            if (!areTypesCompatible(sourceType, targetType)) {
                return false;
            }
        }

        // Check if target handle already has a connection
        const existingConnection = edges.find(
            edge => edge.target === targetNodeId && edge.targetHandle === targetHandle
        );

        if (existingConnection) {
            return false; // Target handle already has a connection
        }

        return true;
    }, [edges, nodes]);

    // Helper function to check type compatibility (strict - no automatic conversions)
    const areTypesCompatible = (sourceType, targetType) => {
        // Only allow exact type matches
        if (sourceType === targetType) {
            return true;
        }

        // Special case: 'any' type can connect to/from anything
        if (sourceType === 'any' || targetType === 'any') {
            return true;
        }

        // No other conversions allowed - use conversion nodes if needed
        return false;
    };

    const defaultEdgeOptions = {
        type: 'smoothstep',
    };

    const onConnect = React.useCallback(
        (params) => {
            // Apply visual styling based on connection type and data type
            const sourceHandle = params.sourceHandle;
            const sourceNodeId = params.source;
            let style = {};
            let animated = false;

            if (sourceHandle && sourceHandle.includes('exec')) {
                // Exec connection styling
                const execWidth = typeConfig?.settings?.connectionWidth?.exec || 3;
                style = { stroke: getTypeColor('exec'), strokeWidth: execWidth };
            } else if (sourceHandle && sourceHandle.startsWith('output-')) {
                // Data connection styling - use color based on data type
                const sourceNode = nodes.find(node => node.id === sourceNodeId);
                if (sourceNode) {
                    const sourceFieldName = sourceHandle.replace('output-', '');
                    const sourceOutputs = sourceNode.data.outputs || {};
                    const sourceType = sourceOutputs[sourceFieldName];

                    const dataWidth = typeConfig?.settings?.connectionWidth?.data || 2;
                    style = {
                        stroke: getTypeColor(sourceType),
                        strokeWidth: dataWidth
                    };
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
        },
        [setEdges, typeConfig, nodes, getTypeColor]
    );

    const onDragOver = React.useCallback((event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);

    const onDrop = React.useCallback(
        (event) => {
            event.preventDefault();

            const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
            const nodeData = JSON.parse(
                event.dataTransfer.getData('application/reactflow')
            );

            if (!nodeData || !reactFlowInstance) return;

            // Convert screen coordinates to flow coordinates
            const position = reactFlowInstance.project({
                x: event.clientX - reactFlowBounds.left,
                y: event.clientY - reactFlowBounds.top,
            });

            // Create new node with unique ID
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
                    exec_output: nodeData.exec_output !== undefined ? nodeData.exec_output : true
                },
            };

            setNodes((nds) => nds.concat(newNode));
            setNodeIdCounter((id) => id + 1);
        },
        [reactFlowInstance, nodeIdCounter, setNodes]
    );

    return (
        <div ref={reactFlowWrapper} style={{ width: '100%', height: '100%', position: 'relative' }}>
            {/* Shortcuts Info Button */}
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
            <antd.Modal
                title={
                    <antd.Space>
                        <i className="fas fa-keyboard"></i>
                        <span>Keyboard Shortcuts</span>
                    </antd.Space>
                }
                open={showShortcuts}
                onCancel={() => setShowShortcuts(false)}
                footer={[
                    <antd.Button key="close" type="primary" onClick={() => setShowShortcuts(false)}>
                        Close
                    </antd.Button>
                ]}
                width={600}
            >
                <antd.Space direction="vertical" size="large" style={{ width: '100%' }}>
                    <antd.Card title="Node Operations" size="small">
                        <antd.Descriptions column={1} size="small">
                            <antd.Descriptions.Item label={<antd.Typography.Text strong>Drag from Library</antd.Typography.Text>}>
                                Create new node instance
                            </antd.Descriptions.Item>
                            <antd.Descriptions.Item label={<antd.Typography.Text strong>Click & Drag Node</antd.Typography.Text>}>
                                Move node around canvas
                            </antd.Descriptions.Item>
                            <antd.Descriptions.Item label={<antd.Typography.Text strong><antd.Tag color="blue">Delete</antd.Tag></antd.Typography.Text>}>
                                Delete selected node
                            </antd.Descriptions.Item>
                        </antd.Descriptions>
                    </antd.Card>

                    <antd.Card title="Connection Operations" size="small">
                        <antd.Descriptions column={1} size="small">
                            <antd.Descriptions.Item label={<antd.Typography.Text strong>Drag from Handle</antd.Typography.Text>}>
                                Create connection between nodes
                            </antd.Descriptions.Item>
                            <antd.Descriptions.Item label={<antd.Typography.Text strong>Click Connection</antd.Typography.Text>}>
                                Select connection (turns pink)
                            </antd.Descriptions.Item>
                            <antd.Descriptions.Item label={<antd.Typography.Text strong><antd.Tag color="blue">Delete</antd.Tag> / <antd.Tag color="blue">Backspace</antd.Tag></antd.Typography.Text>}>
                                Remove selected connection
                            </antd.Descriptions.Item>
                        </antd.Descriptions>
                    </antd.Card>

                    <antd.Card title="Canvas Navigation" size="small">
                        <antd.Descriptions column={1} size="small">
                            <antd.Descriptions.Item label={<antd.Typography.Text strong>Mouse Wheel</antd.Typography.Text>}>
                                Zoom in/out
                            </antd.Descriptions.Item>
                            <antd.Descriptions.Item label={<antd.Typography.Text strong>Click & Drag Canvas</antd.Typography.Text>}>
                                Pan around
                            </antd.Descriptions.Item>
                            <antd.Descriptions.Item label={<antd.Typography.Text strong>Controls (bottom-left)</antd.Typography.Text>}>
                                Zoom, fit view, lock controls
                            </antd.Descriptions.Item>
                        </antd.Descriptions>
                    </antd.Card>

                    <antd.Alert
                        message="Connection Rules"
                        description={
                            <antd.Space direction="vertical" size="small">
                                <antd.Typography.Text>
                                    <i className="fas fa-circle" style={{ color: '#fff' }}></i> Exec connections (white) only connect to exec handles
                                </antd.Typography.Text>
                                <antd.Typography.Text>
                                    <i className="fas fa-circle" style={{ color: '#1890ff' }}></i> Data connections (blue) only connect to data handles
                                </antd.Typography.Text>
                                <antd.Typography.Text>
                                    Each input can only receive one connection
                                </antd.Typography.Text>
                            </antd.Space>
                        }
                        type="info"
                        showIcon
                    />
                </antd.Space>
            </antd.Modal>

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
                nodeTypes={nodeTypes}
                defaultEdgeOptions={defaultEdgeOptions}
                deleteKeyCode="Delete"
                fitView
            >
                <Controls />
                <Background variant="dots" gap={12} size={1} />
            </ReactFlow>
        </div>
    );
}