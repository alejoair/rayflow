// Shortcuts Modal Component
function ShortcutsModal({ visible, onClose }) {
    return (
        <antd.Modal
            title={
                <antd.Space>
                    <i className="fas fa-keyboard"></i>
                    <span>Keyboard Shortcuts</span>
                </antd.Space>
            }
            open={visible}
            onCancel={onClose}
            footer={[
                <antd.Button key="close" type="primary" onClick={onClose}>
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
    );
}