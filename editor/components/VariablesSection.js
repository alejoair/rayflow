// Variables Section Component for NodeList
function VariablesSection({
    variables,           // state.variables
    variableNodes,       // Nodos Set/Get generados
    renderNodeItem,      // Función compartida para drag
    onCreateVariable,    // Callback para abrir modal
    onDeleteVariable     // Callback para eliminar variable
}) {
    const [expandedVariable, setExpandedVariable] = React.useState(null);

    // Group variable nodes by variable ID
    const nodesByVariable = React.useMemo(() => {
        const grouped = {};
        variableNodes.forEach(node => {
            if (!grouped[node.variableId]) {
                grouped[node.variableId] = [];
            }
            grouped[node.variableId].push(node);
        });
        return grouped;
    }, [variableNodes]);

    const handleDeleteVariable = (variable) => {
        antd.Modal.confirm({
            title: 'Delete Variable',
            content: `Are you sure you want to delete variable '${variable.name}'? This will also remove all Set/Get nodes for this variable from the library.`,
            okText: 'Delete',
            okType: 'danger',
            cancelText: 'Cancel',
            onOk: () => {
                onDeleteVariable(variable.id);
                antd.message.success(`Variable '${variable.name}' deleted`);
            }
        });
    };

    return (
        <div style={{ padding: '8px 0' }}>
            {/* Create Variable Button */}
            <antd.Button
                type="primary"
                icon={<i className="fas fa-plus"></i>}
                onClick={onCreateVariable}
                block
                style={{ marginBottom: '12px' }}
            >
                Create New Variable
            </antd.Button>

            {/* Variables List */}
            {variables.length === 0 ? (
                <antd.Empty
                    description={
                        <antd.Space direction="vertical" size="small">
                            <antd.Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                                No variables created yet
                            </antd.Typography.Text>
                            <antd.Typography.Text type="secondary" style={{ fontSize: '11px' }}>
                                Create a variable to add Set/Get nodes
                            </antd.Typography.Text>
                        </antd.Space>
                    }
                    image={antd.Empty.PRESENTED_IMAGE_SIMPLE}
                    style={{ padding: '20px 0', margin: 0 }}
                />
            ) : (
                <antd.Space direction="vertical" style={{ width: '100%' }} size="small">
                    {variables.map(variable => {
                        const nodes = nodesByVariable[variable.id] || [];
                        const isExpanded = expandedVariable === variable.id;

                        return (
                            <antd.Card
                                key={variable.id}
                                size="small"
                                style={{
                                    width: '100%',
                                    border: '1px solid #e8e8e8',
                                    borderRadius: '6px',
                                    backgroundColor: variable.isCustom ? '#fff7e6' : '#fafafa'
                                }}
                                bodyStyle={{ padding: '8px' }}
                            >
                                {/* Variable Header */}
                                <antd.Space
                                    style={{ width: '100%', justifyContent: 'space-between', marginBottom: isExpanded ? '8px' : 0 }}
                                >
                                    <antd.Space size="small">
                                        <i
                                            className="fas fa-box"
                                            style={{
                                                color: variable.isCustom ? '#fa8c16' : '#1890ff',
                                                fontSize: '12px'
                                            }}
                                        ></i>
                                        <antd.Typography.Text
                                            strong
                                            style={{ fontSize: '13px' }}
                                        >
                                            {variable.name}
                                        </antd.Typography.Text>
                                        <antd.Tag
                                            color={variable.isCustom ? 'orange' : 'blue'}
                                            size="small"
                                            style={{ fontSize: '10px' }}
                                        >
                                            {variable.type}
                                        </antd.Tag>
                                        {variable.isCustom && (
                                            <antd.Tooltip title="Custom type - not validated">
                                                <i
                                                    className="fas fa-exclamation-triangle"
                                                    style={{ color: '#fa8c16', fontSize: '11px' }}
                                                ></i>
                                            </antd.Tooltip>
                                        )}
                                    </antd.Space>

                                    <antd.Space size={4}>
                                        <antd.Button
                                            type="text"
                                            size="small"
                                            icon={<i className={`fas fa-chevron-${isExpanded ? 'up' : 'down'}`}></i>}
                                            onClick={() => setExpandedVariable(isExpanded ? null : variable.id)}
                                            style={{ padding: '0 4px' }}
                                        />
                                        <antd.Button
                                            type="text"
                                            size="small"
                                            danger
                                            icon={<i className="fas fa-trash"></i>}
                                            onClick={() => handleDeleteVariable(variable)}
                                            style={{ padding: '0 4px' }}
                                        />
                                    </antd.Space>
                                </antd.Space>

                                {/* Variable Details (when expanded) */}
                                {isExpanded && (
                                    <div style={{
                                        paddingTop: '8px',
                                        borderTop: '1px solid #f0f0f0',
                                        marginTop: '8px'
                                    }}>
                                        {variable.isCustom && variable.customImport && (
                                            <antd.Typography.Text
                                                code
                                                style={{
                                                    fontSize: '10px',
                                                    display: 'block',
                                                    marginBottom: '8px',
                                                    backgroundColor: '#fff',
                                                    padding: '4px 6px',
                                                    borderRadius: '4px'
                                                }}
                                            >
                                                {variable.customImport}
                                            </antd.Typography.Text>
                                        )}

                                        {!variable.isCustom && variable.defaultValue !== undefined && (
                                            <antd.Typography.Text
                                                type="secondary"
                                                style={{ fontSize: '11px', display: 'block', marginBottom: '8px' }}
                                            >
                                                Default: {typeof variable.defaultValue === 'object'
                                                    ? JSON.stringify(variable.defaultValue)
                                                    : String(variable.defaultValue)}
                                            </antd.Typography.Text>
                                        )}

                                        {/* Set/Get Nodes */}
                                        <antd.Typography.Text
                                            strong
                                            style={{ fontSize: '11px', display: 'block', marginBottom: '4px' }}
                                        >
                                            Available Nodes:
                                        </antd.Typography.Text>
                                        <antd.List
                                            size="small"
                                            dataSource={nodes}
                                            renderItem={renderNodeItem}
                                            style={{ margin: 0 }}
                                        />
                                    </div>
                                )}
                            </antd.Card>
                        );
                    })}
                </antd.Space>
            )}
        </div>
    );
}
