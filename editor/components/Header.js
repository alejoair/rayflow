// Header Component - Ant Design version (currently not used in app.js)
function Header({
    onSave,
    onRun,
    onToggleLeftSidebar,
    onToggleRightSidebar,
    leftSidebarCollapsed,
    rightSidebarCollapsed
}) {
    return (
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
                    onClick={onToggleLeftSidebar}
                    style={{ color: 'white' }}
                    title={leftSidebarCollapsed ? "Show Node Library" : "Hide Node Library"}
                />
                <antd.Typography.Title level={3} style={{ color: 'white', margin: 0 }}>
                    RayFlow Editor
                </antd.Typography.Title>
                <antd.Typography.Text style={{ color: 'rgba(255,255,255,0.65)' }}>
                    Visual Flow Editor
                </antd.Typography.Text>
            </antd.Space>

            <antd.Space>
                <antd.Button type="primary" onClick={onSave}>
                    Save Flow
                </antd.Button>
                <antd.Button type="primary" style={{ background: '#52c41a' }} onClick={onRun}>
                    Run Flow
                </antd.Button>
                <antd.Button
                    type="text"
                    icon={<i className={rightSidebarCollapsed ? 'fas fa-bars' : 'fas fa-chevron-right'}></i>}
                    onClick={onToggleRightSidebar}
                    style={{ color: 'white' }}
                    title={rightSidebarCollapsed ? "Show Inspector" : "Hide Inspector"}
                />
            </antd.Space>
        </antd.Layout.Header>
    );
}