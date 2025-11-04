// Node Library Component
function NodeLibrary({ nodes, loading, error, onNodeSelect }) {
    const [selectedCategory, setSelectedCategory] = useState('all');
    const [searchText, setSearchText] = useState('');

    const categories = [
        { value: 'all', label: 'All Nodes' },
        { value: 'builtin', label: 'Built-in Nodes' },
        { value: 'user', label: 'User Nodes' }
    ];

    const filteredNodes = nodes
        .filter(node => selectedCategory === 'all' || node.type === selectedCategory)
        .filter(node => searchText === '' ||
                node.name.toLowerCase().includes(searchText.toLowerCase()) ||
                node.path.toLowerCase().includes(searchText.toLowerCase()));

    // Convert nodes to tree data structure for Ant Design Tree
    const treeData = filteredNodes.map(node => ({
        title: (
            <div
                draggable
                onDragStart={(e) => {
                    e.dataTransfer.setData('application/reactflow', JSON.stringify({
                        type: node.path,
                        name: node.name,
                        nodeType: node.type
                    }));
                    e.dataTransfer.effectAllowed = 'move';
                }}
                style={{ cursor: 'grab' }}
            >
                <antd.Space style={{ width: '100%', justifyContent: 'space-between' }}>
                    <antd.Space direction="vertical" size={0}>
                        <antd.Typography.Text strong>{node.name}</antd.Typography.Text>
                        <antd.Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                            {node.path}
                        </antd.Typography.Text>
                    </antd.Space>
                    <antd.Tag color={node.type === 'builtin' ? 'blue' : 'green'} size="small">
                        {node.type}
                    </antd.Tag>
                </antd.Space>
            </div>
        ),
        key: node.path,
        icon: <i className={node.type === 'builtin' ? 'fas fa-cog' : 'fas fa-user'}></i>,
        nodeData: node
    }));

    const handleNodeClick = (selectedKeys, info) => {
        if (info.node.nodeData) {
            onNodeSelect(info.node.nodeData);
        }
    };

    return (
        <antd.Flex vertical style={{ height: '100%', background: '#fff' }}>
            <antd.Flex vertical style={{ padding: '16px', borderBottom: '1px solid #f0f0f0' }}>
                <antd.Typography.Title level={4} style={{ margin: '0 0 12px 0' }}>
                    Node Library
                </antd.Typography.Title>

                <antd.Space direction="vertical" style={{ width: '100%' }} size="middle">
                    <antd.Select
                        value={selectedCategory}
                        onChange={setSelectedCategory}
                        style={{ width: '100%' }}
                        options={categories}
                        size="small"
                    />

                    <antd.Input.Search
                        placeholder="Search nodes..."
                        value={searchText}
                        onChange={(e) => setSearchText(e.target.value)}
                        allowClear
                        size="small"
                    />
                </antd.Space>
            </antd.Flex>

            <antd.Flex flex={1} style={{ padding: '8px', overflow: 'hidden' }}>
                {loading && (
                    <antd.Flex
                        vertical
                        align="center"
                        justify="center"
                        style={{ height: '200px', width: '100%' }}
                    >
                        <antd.Spin size="large" />
                        <antd.Typography.Text type="secondary" style={{ marginTop: '16px' }}>
                            Loading nodes...
                        </antd.Typography.Text>
                    </antd.Flex>
                )}

                {error && (
                    <antd.Alert
                        message="Error loading nodes"
                        description={error}
                        type="error"
                        showIcon
                        style={{ margin: '16px 0' }}
                    />
                )}

                {!loading && !error && (
                    <>
                        {filteredNodes.length === 0 ? (
                            <antd.Empty
                                description="No nodes found. Create .py files in the nodes/ directory."
                                style={{ padding: '40px 20px' }}
                            />
                        ) : (
                            <antd.Tree
                                showIcon
                                treeData={treeData}
                                onSelect={handleNodeClick}
                                style={{
                                    background: 'transparent',
                                    height: '100%',
                                    overflow: 'auto'
                                }}
                                blockNode
                            />
                        )}
                    </>
                )}
            </antd.Flex>
        </antd.Flex>
    );
}
