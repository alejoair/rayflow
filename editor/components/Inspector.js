// Inspector Component
function Inspector({ selectedNode, onNodeDeselect }) {
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
                {selectedNode && (
                    <antd.Button
                        type="text"
                        size="small"
                        icon={<i className="fas fa-times"></i>}
                        onClick={onNodeDeselect}
                        style={{ color: '#8c8c8c' }}
                    />
                )}
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
                                        children: selectedNode.name
                                    },
                                    {
                                        key: 'type',
                                        label: 'Type',
                                        children: (
                                            <antd.Tag color={selectedNode.type === 'builtin' ? 'blue' : 'green'}>
                                                {selectedNode.type}
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
                                                {selectedNode.path}
                                            </antd.Typography.Text>
                                        )
                                    }
                                ]}
                            />
                        </antd.Card>

                        <antd.Card
                            title="Code Editor"
                            size="small"
                            style={{ width: '100%' }}
                            extra={
                                <antd.Button
                                    type="primary"
                                    size="small"
                                    icon={<i className="fas fa-edit"></i>}
                                >
                                    Edit Code
                                </antd.Button>
                            }
                        >
                            <antd.Typography.Paragraph
                                code
                                style={{
                                    background: '#1f1f1f',
                                    color: '#52c41a',
                                    padding: '12px',
                                    borderRadius: '4px',
                                    fontFamily: 'monospace',
                                    fontSize: '12px',
                                    lineHeight: '1.4',
                                    margin: 0,
                                    whiteSpace: 'pre-line'
                                }}
                            >
                                <antd.Typography.Text style={{ color: '#8c8c8c', display: 'block', marginBottom: '8px' }}>
                                    # Code editor placeholder
                                </antd.Typography.Text>
                                # Double-click node to edit code{'\n'}
                                # File: {selectedNode.path}
                            </antd.Typography.Paragraph>
                        </antd.Card>
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