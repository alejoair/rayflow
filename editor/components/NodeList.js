// Node Library Component
function NodeLibrary({ nodes, loading, error, onNodeSelect }) {
    const { state, actions } = useFlow();
    const [searchText, setSearchText] = React.useState('');
    const [activeCategories, setActiveCategories] = React.useState(['variables', 'base', 'math', 'logic', 'string', 'io', 'data']);
    const [modalVisible, setModalVisible] = React.useState(false);

    // Group nodes by category
    const nodesByCategory = nodes.reduce((acc, node) => {
        const category = node.category || 'other';
        if (!acc[category]) {
            acc[category] = [];
        }
        acc[category].push(node);
        return acc;
    }, {});

    // Filter nodes by search text
    const filteredNodesByCategory = Object.keys(nodesByCategory).reduce((acc, category) => {
        const filteredNodes = nodesByCategory[category].filter(node =>
            searchText === '' ||
            node.name.toLowerCase().includes(searchText.toLowerCase()) ||
            (node.description && node.description.toLowerCase().includes(searchText.toLowerCase()))
        );
        if (filteredNodes.length > 0) {
            acc[category] = filteredNodes;
        }
        return acc;
    }, {});

    // Category display names and icons
    const categoryConfig = {
        base: { label: 'Base', icon: 'fa-circle-play' },
        math: { label: 'Math', icon: 'fa-calculator' },
        variables: { label: 'Variables', icon: 'fa-box' },
        logic: { label: 'Logic', icon: 'fa-code-branch' },
        string: { label: 'String', icon: 'fa-font' },
        io: { label: 'I/O', icon: 'fa-arrow-right-arrow-left' },
        data: { label: 'Data', icon: 'fa-database' },
        other: { label: 'Other', icon: 'fa-question' }
    };

    const handleCollapseChange = (keys) => {
        setActiveCategories(keys);
    };

    // Handlers for variables
    const handleCreateVariable = () => {
        setModalVisible(true);
    };

    const handleVariableCreated = (newVariable) => {
        actions.addVariable(newVariable);
    };

    const handleDeleteVariable = (variableId) => {
        actions.deleteVariable(variableId);
    };

    // Get variable nodes (filtered from category "variables")
    const variableNodes = filteredNodesByCategory['variables'] || [];

    const renderNodeItem = (node) => (
        <antd.List.Item
            key={node.path}
            style={{
                padding: '8px 12px',
                margin: '2px 0',
                border: '1px solid #f0f0f0',
                borderRadius: '6px',
                cursor: 'grab',
                backgroundColor: '#fafafa',
                transition: 'all 0.2s ease'
            }}
            className="node-item"
            draggable
            onDragStart={(e) => {
                e.dataTransfer.setData('application/reactflow', JSON.stringify({
                    type: node.path,
                    name: node.name,
                    nodeType: node.type,
                    icon: node.icon,
                    category: node.category,
                    inputs: node.inputs || {},
                    outputs: node.outputs || {},
                    exec_input: node.exec_input !== undefined ? node.exec_input : true,
                    exec_output: node.exec_output !== undefined ? node.exec_output : true,
                    constants: node.constants || {}
                }));
                e.dataTransfer.effectAllowed = 'move';
            }}
            onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#f0f0f0';
                e.currentTarget.style.borderColor = '#d9d9d9';
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#fafafa';
                e.currentTarget.style.borderColor = '#f0f0f0';
            }}
        >
            <antd.Space style={{ width: '100%', justifyContent: 'space-between' }}>
                <antd.Space size="small">
                    <i className={`fas ${node.icon || 'fa-cube'}`} style={{
                        color: node.type === 'user' ? '#FF6B35' : '#1890ff',
                        fontSize: '14px',
                        minWidth: '16px'
                    }}></i>
                    <antd.Typography.Text strong style={{ fontSize: '13px' }}>
                        {node.name}
                    </antd.Typography.Text>
                    {node.type === 'user' && (
                        <antd.Badge
                            count="CUSTOM"
                            style={{
                                backgroundColor: '#FF6B35',
                                fontSize: '9px',
                                height: '16px',
                                lineHeight: '16px',
                                minWidth: '40px',
                                borderRadius: '8px'
                            }}
                        />
                    )}
                </antd.Space>
                {node.description && (
                    <antd.Popover
                        content={
                            <div style={{ maxWidth: '250px' }}>
                                <antd.Typography.Text>{node.description}</antd.Typography.Text>
                            </div>
                        }
                        title={node.name}
                        trigger="hover"
                        placement="right"
                    >
                        <i className="fas fa-info-circle" style={{
                            color: '#8c8c8c',
                            fontSize: '12px',
                            cursor: 'help'
                        }}></i>
                    </antd.Popover>
                )}
            </antd.Space>
        </antd.List.Item>
    );

    // Create collapse items (exclude 'variables' category - handled separately)
    const collapseItems = Object.keys(filteredNodesByCategory)
        .filter(category => category !== 'variables')
        .map((category, index, array) => {
            const config = categoryConfig[category] || categoryConfig.other;
            const isLast = index === array.length - 1;

        return {
            key: category,
            label: (
                <div style={{
                    width: '100%',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '4px 0'
                }}>
                    <antd.Space>
                        <i className={`fas ${config.icon}`} style={{ color: '#1890ff' }}></i>
                        <span style={{ fontWeight: '500' }}>{config.label}</span>
                    </antd.Space>
                    <antd.Badge count={filteredNodesByCategory[category].length} size="small" />
                </div>
            ),
            children: (
                <div>
                    <antd.List
                        size="small"
                        dataSource={filteredNodesByCategory[category]}
                        renderItem={renderNodeItem}
                        style={{ padding: '0', marginBottom: '8px' }}
                    />
                    {!isLast && (
                        <antd.Divider style={{
                            margin: '12px 0 8px 0',
                            borderColor: '#e8e8e8'
                        }} />
                    )}
                </div>
            )
        };
    });

    // Create Variables Section item
    const variablesItem = {
        key: 'variables',
        label: (
            <div style={{
                width: '100%',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '4px 0'
            }}>
                <antd.Space>
                    <i className="fas fa-box" style={{ color: '#1890ff' }}></i>
                    <span style={{ fontWeight: '500' }}>Variables</span>
                </antd.Space>
                <antd.Badge count={state.variables.length} size="small" />
            </div>
        ),
        children: (
            <VariablesSection
                variables={state.variables}
                variableNodes={variableNodes}
                renderNodeItem={renderNodeItem}
                onCreateVariable={handleCreateVariable}
                onDeleteVariable={handleDeleteVariable}
            />
        )
    };

    // Combine all collapse items (variables first, then others)
    const allCollapseItems = [variablesItem, ...collapseItems];

    return (
        <antd.Flex vertical style={{ height: '100%', background: '#fff' }}>
            <antd.Flex vertical style={{ padding: '16px', borderBottom: '1px solid #f0f0f0' }}>
                <antd.Flex justify="space-between" align="center" style={{ marginBottom: '12px' }}>
                    <antd.Typography.Title level={4} style={{ margin: 0 }}>
                        Node Library
                    </antd.Typography.Title>
                    <antd.Button
                        type="text"
                        size="small"
                        icon={<i className="fas fa-chevron-left"></i>}
                        onClick={actions.toggleLeftSidebar}
                        title="Collapse sidebar"
                    />
                </antd.Flex>

                <antd.Input.Search
                    placeholder="Search nodes..."
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                    allowClear
                    size="small"
                />
            </antd.Flex>

            <antd.Flex flex={1} style={{ padding: '4px 8px', overflow: 'auto' }}>
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
                    <antd.Space direction="vertical" style={{ width: '100%' }} size="small">
                        {Object.keys(filteredNodesByCategory).length === 0 ? (
                            <antd.Empty
                                description="No nodes found. Create .py files in the nodes/ directory."
                                style={{ padding: '40px 20px' }}
                            />
                        ) : (
                            <antd.Collapse
                                activeKey={activeCategories}
                                onChange={handleCollapseChange}
                                items={allCollapseItems}
                                style={{
                                    background: 'transparent',
                                    border: 'none',
                                    width: '100%'
                                }}
                                size="small"
                                ghost
                                expandIconPosition="end"
                            />
                        )}
                    </antd.Space>
                )}
            </antd.Flex>

            {/* Create Variable Modal */}
            <CreateVariableModal
                visible={modalVisible}
                onClose={() => setModalVisible(false)}
                onCreateVariable={handleVariableCreated}
                existingVariables={state.variables}
            />
        </antd.Flex>
    );
}
