// Canvas Component with React Flow
function Canvas({ onCanvasClick }) {
    const { ReactFlow, Controls, Background, useNodesState, useEdgesState, addEdge, Handle, Position } = window.ReactFlow;

    // Custom Node Component with separate handles for exec and data
    const CustomNode = ({ data }) => {
        return (
            <div style={{
                padding: '10px 20px',
                borderRadius: '5px',
                background: '#1a1a1a',
                border: '2px solid #333',
                color: 'white',
                minWidth: '150px'
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

                {/* Label del nodo */}
                <div>{data.label}</div>

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
            data: { label: 'Start Node' },
            position: { x: 50, y: 100 },
        },
        {
            id: '2',
            type: 'custom',
            data: { label: 'Process Node' },
            position: { x: 300, y: 100 },
        },
        {
            id: '3',
            type: 'custom',
            data: { label: 'End Node' },
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

    const onConnect = React.useCallback(
        (params) => setEdges((eds) => addEdge(params, eds)),
        [setEdges]
    );

    return (
        <div style={{ width: '100%', height: '100%' }}>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                nodeTypes={nodeTypes}
                fitView
            >
                <Controls />
                <Background variant="dots" gap={12} size={1} />
            </ReactFlow>
        </div>
    );
}