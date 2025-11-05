// Canvas Component with React Flow
function Canvas({ onCanvasClick }) {
    const { ReactFlow, Controls, Background, useNodesState, useEdgesState, addEdge, Handle, Position } = window.ReactFlow;

    // Custom Node Component with separate handles for exec and data
    const CustomNode = ({ data, selected }) => {
        return (
            <div style={{
                padding: '10px 20px',
                borderRadius: '5px',
                background: '#1a1a1a',
                border: selected ? '2px solid #1890ff' : '2px solid #333',
                boxShadow: selected ? '0 0 10px rgba(24, 144, 255, 0.5)' : 'none',
                color: 'white',
                minWidth: '150px',
                transition: 'all 0.2s ease'
            }}>
                {/* Handles de entrada (izquierda) */}
                <Handle
                    type="target"
                    position={Position.Left}
                    id="exec-in"
                    style={{ top: '30%', background: '#fff', width: '12px', height: '12px' }}
                />
                <Handle
                    type="target"
                    position={Position.Left}
                    id="data-in"
                    style={{ top: '70%', background: '#1890ff', width: '10px', height: '10px' }}
                />

                {/* Label del nodo con icono */}
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '14px',
                    fontWeight: '500'
                }}>
                    {data.icon && (
                        <i className={`fas ${data.icon}`} style={{
                            color: '#1890ff',
                            fontSize: '16px'
                        }}></i>
                    )}
                    <span>{data.label ? data.label.charAt(0).toUpperCase() + data.label.slice(1) : 'Unknown'}</span>
                </div>

                {/* Handles de salida (derecha) */}
                <Handle
                    type="source"
                    position={Position.Right}
                    id="exec-out"
                    style={{ top: '30%', background: '#fff', width: '12px', height: '12px' }}
                />
                <Handle
                    type="source"
                    position={Position.Right}
                    id="data-out"
                    style={{ top: '70%', background: '#1890ff', width: '10px', height: '10px' }}
                />
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
                category: 'base'
            },
            position: { x: 50, y: 100 },
        },
        {
            id: '2',
            type: 'custom',
            data: {
                label: 'add',
                icon: 'fa-plus',
                category: 'math'
            },
            position: { x: 300, y: 100 },
        },
        {
            id: '3',
            type: 'custom',
            data: {
                label: 'return',
                icon: 'fa-flag-checkered',
                category: 'base'
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
        },
        // Conexiones de datos - azules
        {
            id: 'data1-2',
            source: '1',
            target: '2',
            sourceHandle: 'data-out',
            targetHandle: 'data-in',
            type: 'smoothstep',
            animated: true,
            style: { stroke: '#1890ff', strokeWidth: 2 }
        },
        {
            id: 'data2-3',
            source: '2',
            target: '3',
            sourceHandle: 'data-out',
            targetHandle: 'data-in',
            type: 'smoothstep',
            animated: true,
            style: { stroke: '#1890ff', strokeWidth: 2 }
        },
    ];

    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
    const [nodeIdCounter, setNodeIdCounter] = React.useState(4); // Start from 4 since we have 3 initial nodes
    const [reactFlowInstance, setReactFlowInstance] = React.useState(null);
    const reactFlowWrapper = React.useRef(null);
    const [showShortcuts, setShowShortcuts] = React.useState(false);

    const isValidConnection = React.useCallback((connection) => {
        // Get the handle types from the connection
        const sourceHandle = connection.sourceHandle;
        const targetHandle = connection.targetHandle;

        // Type validation: Exec handles can only connect to exec handles
        if (sourceHandle && sourceHandle.includes('exec')) {
            if (!targetHandle || !targetHandle.includes('exec')) {
                return false;
            }
        }

        // Type validation: Data handles can only connect to data handles
        if (sourceHandle && sourceHandle.includes('data')) {
            if (!targetHandle || !targetHandle.includes('data')) {
                return false;
            }
        }

        // Check if target handle already has a connection
        const targetNode = connection.target;
        const targetHandleId = connection.targetHandle;

        const existingConnection = edges.find(
            edge => edge.target === targetNode && edge.targetHandle === targetHandleId
        );

        if (existingConnection) {
            return false; // Target handle already has a connection
        }

        return true;
    }, [edges]);

    const defaultEdgeOptions = {
        type: 'smoothstep',
    };

    const onConnect = React.useCallback(
        (params) => {
            // Apply visual styling based on connection type
            const sourceHandle = params.sourceHandle;
            let style = {};
            let animated = false;

            if (sourceHandle && sourceHandle.includes('exec')) {
                // Exec connection styling
                style = { stroke: '#fff', strokeWidth: 3 };
            } else if (sourceHandle && sourceHandle.includes('data')) {
                // Data connection styling
                style = { stroke: '#1890ff', strokeWidth: 2 };
                animated = true;
            }

            const newEdge = {
                ...params,
                type: 'smoothstep',
                style: style,
                animated: animated
            };

            setEdges((eds) => addEdge(newEdge, eds));
        },
        [setEdges]
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
                    category: nodeData.category
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