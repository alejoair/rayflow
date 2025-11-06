// Inspector Component
function Inspector() {
    const { state, actions } = useFlow();
    const [typeConfig, setTypeConfig] = React.useState(null);

    // Get selectedNode from global state
    const selectedNode = state.selectedNode;

    // Get current constant values from selectedNode data (no local state)
    const constantValues = React.useMemo(() => {
        if (!selectedNode?.data?.constants) return {};

        const values = {};
        Object.keys(selectedNode.data.constants).forEach(key => {
            const constant = selectedNode.data.constants[key];
            // Use configured value if it exists, otherwise use default value
            const configuredValue = selectedNode.data.constantValues?.[key];
            values[key] = configuredValue !== undefined ? configuredValue : constant.value;
        });
        return values;
    }, [selectedNode]);

    // Load data type configuration
    React.useEffect(() => {
        fetch('/config/data-types.json')
            .then(response => response.json())
            .then(data => setTypeConfig(data))
            .catch(error => {
                console.error('Failed to load type configuration:', error);
                // Fallback configuration
                setTypeConfig({
                    dataTypes: {
                        int: { fieldType: 'number', inputProps: { step: 1 } },
                        float: { fieldType: 'number', inputProps: { step: 0.1 } },
                        str: { fieldType: 'text', inputProps: {} },
                        bool: { fieldType: 'switch', inputProps: {} }
                    }
                });
            });
    }, []);

    // Handle constant value change - update global state directly
    const handleConstantChange = (constName, value) => {
        if (selectedNode) {
            const newValues = {
                ...constantValues,
                [constName]: value
            };
            actions.updateNodeConstants(selectedNode.id, newValues);
        }
    };

    // Render form field based on data type
    const renderConstantField = (constName, constant) => {
        if (!typeConfig) return null;

        const typeInfo = typeConfig.dataTypes[constant.type];
        if (!typeInfo) return null;

        const currentValue = constantValues[constName] !== undefined ? constantValues[constName] : constant.value;

        switch (typeInfo.fieldType) {
            case 'number':
                return (
                    <antd.InputNumber
                        value={currentValue}
                        onChange={(value) => handleConstantChange(constName, value)}
                        style={{ width: '100%' }}
                        {...typeInfo.inputProps}
                    />
                );
            case 'text':
                return (
                    <antd.Input
                        value={currentValue}
                        onChange={(e) => handleConstantChange(constName, e.target.value)}
                        {...typeInfo.inputProps}
                    />
                );
            case 'switch':
                return (
                    <antd.Switch
                        checked={currentValue}
                        onChange={(checked) => handleConstantChange(constName, checked)}
                        {...typeInfo.inputProps}
                    />
                );
            case 'textarea':
                return (
                    <antd.Input.TextArea
                        value={typeof currentValue === 'object' ? JSON.stringify(currentValue, null, 2) : currentValue}
                        onChange={(e) => {
                            try {
                                const parsed = JSON.parse(e.target.value);
                                handleConstantChange(constName, parsed);
                            } catch {
                                handleConstantChange(constName, e.target.value);
                            }
                        }}
                        {...typeInfo.inputProps}
                    />
                );
            default:
                return (
                    <antd.Input
                        value={currentValue}
                        onChange={(e) => handleConstantChange(constName, e.target.value)}
                        disabled
                    />
                );
        }
    };
    return (
        <antd.Flex vertical style={{ height: '100%', background: '#fff' }}>
            <antd.Flex
                align="center"
                justify="space-between"
                style={{
                    padding: '16px',
                    borderBottom: '1px solid #f0f0f0'
                }}
            >
                <antd.Typography.Title level={4} style={{ margin: 0 }}>
                    Inspector
                </antd.Typography.Title>
                <antd.Space size="small">
                    {selectedNode && (
                        <antd.Button
                            type="text"
                            size="small"
                            icon={<i className="fas fa-times"></i>}
                            onClick={actions.deselectNode}
                            style={{ color: '#8c8c8c' }}
                            title="Deselect node"
                        />
                    )}
                    <antd.Button
                        type="text"
                        size="small"
                        icon={<i className="fas fa-chevron-right"></i>}
                        onClick={actions.toggleRightSidebar}
                        title="Collapse sidebar"
                    />
                </antd.Space>
            </antd.Flex>

            <antd.Flex flex={1} style={{ padding: '16px', overflow: 'auto' }}>
                {selectedNode ? (
                    <antd.Space direction="vertical" style={{ width: '100%' }} size="large">
                        <antd.Card
                            title="Node Properties"
                            size="small"
                            style={{ width: '100%' }}
                        >
                            <antd.Descriptions
                                column={1}
                                size="small"
                                items={[
                                    {
                                        key: 'name',
                                        label: 'Name',
                                        children: selectedNode.data.label
                                    },
                                    {
                                        key: 'type',
                                        label: 'Type',
                                        children: (
                                            <antd.Tag color={selectedNode.data.nodeType === 'builtin' ? 'blue' : 'green'}>
                                                {selectedNode.data.nodeType}
                                            </antd.Tag>
                                        )
                                    },
                                    {
                                        key: 'path',
                                        label: 'Path',
                                        children: (
                                            <antd.Typography.Text
                                                code
                                                copyable
                                                style={{ fontSize: '12px' }}
                                            >
                                                {selectedNode.data.path}
                                            </antd.Typography.Text>
                                        )
                                    }
                                ]}
                            />
                        </antd.Card>

                        {/* Constants Configuration Section - For both builtin and custom nodes */}
                        {selectedNode.data.constants && Object.keys(selectedNode.data.constants).length > 0 && (
                            <antd.Card
                                title={
                                    <antd.Space>
                                        <i className="fas fa-cog" style={{
                                            color: selectedNode.data.nodeType === 'user' ? '#FF6B35' : '#1890ff'
                                        }}></i>
                                        <span>Node Configuration</span>
                                        <antd.Tag
                                            color={selectedNode.data.nodeType === 'user' ? 'orange' : 'blue'}
                                            size="small"
                                        >
                                            {selectedNode.data.nodeType === 'user' ? 'CUSTOM' : 'BUILTIN'}
                                        </antd.Tag>
                                        <antd.Tag color="green" size="small">
                                            Auto-save
                                        </antd.Tag>
                                    </antd.Space>
                                }
                                size="small"
                                style={{ width: '100%' }}
                            >
                                <antd.Space direction="vertical" style={{ width: '100%' }} size="middle">
                                    <antd.Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                                        Configure node constants. These values will be used as default parameters for the node.
                                    </antd.Typography.Text>
                                    {Object.entries(selectedNode.data.constants).map(([constName, constant]) => (
                                        <antd.Form.Item
                                            key={constName}
                                            label={
                                                <antd.Space size="small">
                                                    <antd.Typography.Text strong style={{ fontSize: '13px' }}>
                                                        {constName}
                                                    </antd.Typography.Text>
                                                    <antd.Tag color="blue" size="small">
                                                        {constant.type}
                                                    </antd.Tag>
                                                </antd.Space>
                                            }
                                            style={{ marginBottom: '12px' }}
                                            labelCol={{ span: 24 }}
                                            wrapperCol={{ span: 24 }}
                                        >
                                            {renderConstantField(constName, constant)}
                                        </antd.Form.Item>
                                    ))}
                                </antd.Space>
                            </antd.Card>
                        )}

                        {/* Source Code - Only for custom nodes */}
                        {selectedNode.data.nodeType === 'user' && (
                            <antd.Card
                                title={
                                    <antd.Space>
                                        <i className="fas fa-code" style={{ color: '#FF6B35' }}></i>
                                        <span>Source Code</span>
                                        <antd.Tag color="orange" size="small">
                                            CUSTOM NODE
                                        </antd.Tag>
                                    </antd.Space>
                                }
                                size="small"
                                style={{ width: '100%' }}
                            >
                                <antd.Space direction="vertical" style={{ width: '100%' }} size="middle">
                                    <antd.Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                                        Edit the Python source code for this custom node. Opens in a tab on the canvas.
                                    </antd.Typography.Text>
                                    <antd.Button
                                        type="primary"
                                        icon={<i className="fas fa-code"></i>}
                                        onClick={() => actions.openEditorTab(selectedNode.data.path, selectedNode.data.label)}
                                        block
                                    >
                                        Edit Source Code
                                    </antd.Button>
                                    <antd.Typography.Text type="secondary" style={{ fontSize: '11px', fontStyle: 'italic' }}>
                                        File: {selectedNode.data.path}
                                    </antd.Typography.Text>
                                </antd.Space>
                            </antd.Card>
                        )}
                    </antd.Space>
                ) : (
                    <antd.Empty
                        image={antd.Empty.PRESENTED_IMAGE_SIMPLE}
                        description={
                            <antd.Space direction="vertical" size="small">
                                <antd.Typography.Title level={5} style={{ color: '#8c8c8c' }}>
                                    No Node Selected
                                </antd.Typography.Title>
                                <antd.Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                                    Select a node from the library or canvas to view its properties
                                </antd.Typography.Text>
                            </antd.Space>
                        }
                        style={{
                            padding: '60px 20px',
                            height: '100%',
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'center'
                        }}
                    />
                )}
            </antd.Flex>
        </antd.Flex>
    );
}