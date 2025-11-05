// Main App Component
function RayFlowEditor() {
    const [nodes, setNodes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedNode, setSelectedNode] = useState(null);
    const [leftSidebarCollapsed, setLeftSidebarCollapsed] = useState(false);
    const [rightSidebarCollapsed, setRightSidebarCollapsed] = useState(false);

    useEffect(() => {
        loadNodes();
    }, []);

    async function loadNodes() {
        try {
            setLoading(true);
            const response = await fetch('/api/nodes');
            if (!response.ok) throw new Error('Failed to fetch nodes');
            const data = await response.json();
            setNodes(data);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    const handleSave = () => {
        console.log('Save flow');
        // TODO: Implement save functionality
    };

    const handleRun = () => {
        console.log('Run flow');
        // TODO: Implement run functionality
    };

    const handleNodeSelect = (node) => {
        setSelectedNode(node);
        console.log('Selected node:', node);
    };

    const handleNodeDeselect = () => {
        setSelectedNode(null);
    };

    const handleCanvasClick = (e) => {
        if (e.target === e.currentTarget) {
            setSelectedNode(null);
        }
    };

    const toggleLeftSidebar = () => {
        setLeftSidebarCollapsed(!leftSidebarCollapsed);
    };

    const toggleRightSidebar = () => {
        setRightSidebarCollapsed(!rightSidebarCollapsed);
    };

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
                        icon={<i className={leftSidebarCollapsed ? 'fas fa-bars' : 'fas fa-chevron-left'}></i>}
                        onClick={toggleLeftSidebar}
                        style={{ color: 'white' }}
                        title={leftSidebarCollapsed ? "Show Node Library" : "Hide Node Library"}
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
                        icon={<i className={rightSidebarCollapsed ? 'fas fa-bars' : 'fas fa-chevron-right'}></i>}
                        onClick={toggleRightSidebar}
                        style={{ color: 'white' }}
                        title={rightSidebarCollapsed ? "Show Inspector" : "Hide Inspector"}
                    />
                </antd.Space>
            </antd.Layout.Header>

            <antd.Layout>
                {/* Left Sidebar - Node Library */}
                <antd.Layout.Sider
                    width={320}
                    collapsible
                    collapsed={leftSidebarCollapsed}
                    onCollapse={setLeftSidebarCollapsed}
                    trigger={null}
                    style={{ background: '#fff' }}
                >
                    <NodeLibrary
                        nodes={nodes}
                        loading={loading}
                        error={error}
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
                    collapsed={rightSidebarCollapsed}
                    onCollapse={setRightSidebarCollapsed}
                    trigger={null}
                    reverseArrow
                    style={{ background: '#fff' }}
                >
                    <Inspector
                        selectedNode={selectedNode}
                        onNodeDeselect={handleNodeDeselect}
                    />
                </antd.Layout.Sider>
            </antd.Layout>
        </antd.Layout>
    );
}

ReactDOM.createRoot(document.getElementById('root')).render(<RayFlowEditor />);
