// Main App Component
function RayFlowEditor() {
    // Use global state instead of local state
    const { state, actions } = useFlow();

    const handleSave = () => {
        // Check if there are nodes to save
        if (state.nodes.length === 0) {
            antd.message.warning('No nodes to save. Create some nodes first!');
            return;
        }

        // Show save dialog
        antd.Modal.confirm({
            title: 'Save Flow',
            content: (
                <div>
                    <p>Save this flow as a JSON file?</p>
                    <p><strong>Nodes:</strong> {state.nodes.length}</p>
                    <p><strong>Connections:</strong> {state.edges.length}</p>
                </div>
            ),
            okText: 'Save',
            cancelText: 'Cancel',
            onOk: () => performSave()
        });
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
                    <antd.Button
                        type="text"
                        icon={<i className={state.leftSidebarCollapsed ? 'fas fa-bars' : 'fas fa-chevron-left'}></i>}
                        onClick={actions.toggleLeftSidebar}
                        style={{ color: 'white' }}
                        title={state.leftSidebarCollapsed ? "Show Node Library" : "Hide Node Library"}
                    />
                    <antd.Typography.Title level={3} style={{ color: 'white', margin: 0 }}>
                        RayFlow Editor
                    </antd.Typography.Title>
                    <antd.Typography.Text style={{ color: '#rgba(255,255,255,0.65)' }}>
                        Visual Flow Editor
                    </antd.Typography.Text>
                </antd.Space>

                <antd.Space>
                    <antd.Button type="primary" onClick={handleSave}>
                        Save Flow
                    </antd.Button>
                    <antd.Button type="primary" style={{ background: '#52c41a' }} onClick={handleRun}>
                        Run Flow
                    </antd.Button>
                    <antd.Button
                        type="text"
                        icon={<i className={state.rightSidebarCollapsed ? 'fas fa-bars' : 'fas fa-chevron-right'}></i>}
                        onClick={actions.toggleRightSidebar}
                        style={{ color: 'white' }}
                        title={state.rightSidebarCollapsed ? "Show Inspector" : "Hide Inspector"}
                    />
                </antd.Space>
            </antd.Layout.Header>

            <antd.Layout>
                {/* Left Sidebar - Node Library */}
                <antd.Layout.Sider
                    width={320}
                    collapsible
                    collapsed={state.leftSidebarCollapsed}
                    onCollapse={actions.toggleLeftSidebar}
                    trigger={null}
                    style={{ background: '#fff' }}
                >
                    <NodeLibrary
                        nodes={state.availableNodes}
                        loading={state.loading}
                        error={state.error}
                        onNodeSelect={handleNodeSelect}
                    />
                </antd.Layout.Sider>

                {/* Main Content - Canvas */}
                <antd.Layout.Content style={{ background: '#f5f5f5', height: 'calc(100vh - 64px)', display: 'flex' }}>
                    <Canvas onNodeSelect={handleNodeSelect} />
                </antd.Layout.Content>

                {/* Right Sidebar - Inspector */}
                <antd.Layout.Sider
                    width={320}
                    collapsible
                    collapsed={state.rightSidebarCollapsed}
                    onCollapse={actions.toggleRightSidebar}
                    trigger={null}
                    reverseArrow
                    style={{ background: '#fff' }}
                >
                    <Inspector />
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
