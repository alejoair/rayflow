// Main App Component
function RayFlowEditor() {
    // Use global state instead of local state
    const { state, actions } = useFlow();

    const handleManualSave = () => {
        // Check if there are nodes to save
        if (state.nodes.length === 0) {
            antd.message.warning('No nodes to save. Create some nodes first!');
            return;
        }

        const stateToSave = {
            nodes: state.nodes,
            edges: state.edges,
            nodeIdCounter: state.nodeIdCounter
        };

        if (window.AutoSave?.save) {
            const success = window.AutoSave.save(stateToSave);
            if (success) {
                antd.message.success('Canvas saved successfully!');
                console.log('MANUAL SAVE: Canvas saved with', state.nodes.length, 'nodes and', state.edges.length, 'edges');
            } else {
                antd.message.error('Failed to save canvas');
            }
        } else {
            antd.message.error('AutoSave system not available');
        }
    };

    const handleExportFlow = () => {
        // Check if there are nodes to export
        if (state.nodes.length === 0) {
            antd.message.warning('No nodes to export. Create some nodes first!');
            return;
        }

        // Show export dialog
        antd.Modal.confirm({
            title: 'Export Flow',
            content: (
                <div>
                    <p>Export this flow as a JSON file?</p>
                    <p><strong>Nodes:</strong> {state.nodes.length}</p>
                    <p><strong>Connections:</strong> {state.edges.length}</p>
                </div>
            ),
            okText: 'Export',
            cancelText: 'Cancel',
            onOk: () => performSave()
        });
    };

    const handleClearCanvas = () => {
        // Check if there are nodes to clear
        if (state.nodes.length === 0) {
            antd.message.info('Canvas is already empty');
            return;
        }

        // Show confirmation dialog
        antd.Modal.confirm({
            title: 'Clear Canvas',
            content: (
                <div>
                    <p>Are you sure you want to clear the entire canvas?</p>
                    <p><strong>This will remove:</strong></p>
                    <p>• {state.nodes.length} nodes</p>
                    <p>• {state.edges.length} connections</p>
                    <p style={{ color: '#ff4d4f', fontWeight: 'bold' }}>This action cannot be undone!</p>
                </div>
            ),
            okText: 'Clear Canvas',
            okType: 'danger',
            cancelText: 'Cancel',
            onOk: () => performClear()
        });
    };

    const performClear = () => {
        // Clear all canvas state
        actions.setNodes([]);
        actions.setEdges([]);
        actions.deselectNode();

        // Also clear the auto-save so it doesn't restore an empty canvas
        if (window.AutoSave?.clear) {
            window.AutoSave.clear();
        }

        // Show success message
        antd.message.success('Canvas cleared successfully');
        console.log('CLEAR CANVAS: Canvas cleared by user');
    };

    const performSave = () => {
        // Create flow JSON with metadata and enhanced node data
        const flowJson = {
            metadata: {
                name: "Untitled Flow",
                version: "1.0.0",
                created: new Date().toISOString(),
                lastModified: new Date().toISOString(),
                description: "RayFlow workflow",
                nodeCount: state.nodes.length,
                edgeCount: state.edges.length,
                rayflowVersion: "0.1.0"
            },
            variables: state.variables,
            flow: {
                nodes: state.nodes.map(node => ({
                    id: node.id,
                    type: node.type,
                    position: node.position,
                    data: {
                        ...node.data,
                        // Include configured constant values if they exist
                        ...(node.data.constantValues && { configuredConstants: node.data.constantValues })
                    }
                })),
                edges: state.edges.map(edge => ({
                    id: edge.id,
                    source: edge.source,
                    target: edge.target,
                    sourceHandle: edge.sourceHandle,
                    targetHandle: edge.targetHandle,
                    type: edge.type,
                    style: edge.style,
                    animated: edge.animated
                }))
            }
        };

        // Create downloadable JSON file
        const dataStr = JSON.stringify(flowJson, null, 2);
        const dataBlob = new Blob([dataStr], {type: "application/json"});

        // Create download link
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `flow_${new Date().toISOString().slice(0,10)}.json`;

        // Trigger download
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        // Show success message
        antd.message.success('Flow saved successfully!');
    };

    const handleRun = () => {
        console.log('Run flow');
        // TODO: Implement run functionality
    };

    const handleNodeSelect = React.useCallback((node) => {
        // Only update if the selection actually changed (compare by ID, not object reference)
        const currentSelectedId = state.selectedNode?.id;
        const newSelectedId = node?.id;

        if (currentSelectedId !== newSelectedId) {
            actions.selectNode(node);
        }
    }, [actions, state.selectedNode]);


    return (
        <antd.Layout style={{ height: '100vh' }}>
            {/* Header with Ant Design */}
            <antd.Layout.Header style={{
                padding: '0 24px',
                background: '#001529',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
            }}>
                <antd.Space align="center" size="large">
                    <antd.Typography.Title level={3} style={{ color: 'white', margin: 0 }}>
                        RayFlow Editor
                    </antd.Typography.Title>
                    <antd.Typography.Text style={{ color: '#rgba(255,255,255,0.65)' }}>
                        Visual Flow Editor
                    </antd.Typography.Text>
                </antd.Space>

                <antd.Space>
                    <antd.Button type="default" onClick={handleManualSave}>
                        Save Canvas
                    </antd.Button>
                    <antd.Button type="primary" onClick={handleExportFlow}>
                        Export Flow
                    </antd.Button>
                    <antd.Button
                        type="default"
                        danger
                        icon={<i className="fas fa-trash"></i>}
                        onClick={handleClearCanvas}
                    >
                        Clear Canvas
                    </antd.Button>
                    <antd.Button type="primary" style={{ background: '#52c41a' }} onClick={handleRun}>
                        Run Flow
                    </antd.Button>
                </antd.Space>
            </antd.Layout.Header>

            <antd.Layout style={{ height: 'calc(100vh - 64px)' }}>
                {/* Left Sidebar - Node Library */}
                <antd.Layout.Sider
                    width={320}
                    collapsedWidth={50}
                    collapsible
                    collapsed={state.leftSidebarCollapsed}
                    onCollapse={actions.toggleLeftSidebar}
                    trigger={null}
                    style={{ background: '#fff', borderRight: '1px solid #f0f0f0' }}
                >
                    {state.leftSidebarCollapsed ? (
                        <div style={{
                            height: '100%',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            paddingTop: '16px',
                            gap: '16px'
                        }}>
                            <antd.Button
                                type="text"
                                icon={<i className="fas fa-chevron-right"></i>}
                                onClick={actions.toggleLeftSidebar}
                                title="Show Node Library"
                                style={{ fontSize: '16px' }}
                            />
                            <div style={{
                                writingMode: 'vertical-rl',
                                transform: 'rotate(180deg)',
                                fontSize: '12px',
                                color: '#8c8c8c',
                                marginTop: '8px'
                            }}>
                                NODES
                            </div>
                        </div>
                    ) : (
                        <NodeLibrary
                            nodes={state.availableNodes}
                            loading={state.loading}
                            error={state.error}
                            onNodeSelect={handleNodeSelect}
                        />
                    )}
                </antd.Layout.Sider>

                {/* Main Content - Canvas */}
                <antd.Layout.Content style={{ background: '#f5f5f5', display: 'flex' }}>
                    <Canvas onNodeSelect={handleNodeSelect} />
                </antd.Layout.Content>

                {/* Right Sidebar - Inspector */}
                <antd.Layout.Sider
                    width={320}
                    collapsedWidth={50}
                    collapsible
                    collapsed={state.rightSidebarCollapsed}
                    onCollapse={actions.toggleRightSidebar}
                    trigger={null}
                    reverseArrow
                    style={{ background: '#fff', borderLeft: '1px solid #f0f0f0' }}
                >
                    {state.rightSidebarCollapsed ? (
                        <div style={{
                            height: '100%',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            paddingTop: '16px',
                            gap: '16px'
                        }}>
                            <antd.Button
                                type="text"
                                icon={<i className="fas fa-chevron-left"></i>}
                                onClick={actions.toggleRightSidebar}
                                title="Show Inspector"
                                style={{ fontSize: '16px' }}
                            />
                            <div style={{
                                writingMode: 'vertical-rl',
                                transform: 'rotate(180deg)',
                                fontSize: '12px',
                                color: '#8c8c8c',
                                marginTop: '8px'
                            }}>
                                INSPECTOR
                            </div>
                        </div>
                    ) : (
                        <Inspector />
                    )}
                </antd.Layout.Sider>
            </antd.Layout>
        </antd.Layout>
    );
}

ReactDOM.createRoot(document.getElementById('root')).render(
    <FlowProvider>
        <RayFlowEditor />
    </FlowProvider>
);
