/**
 * EditorTabs Component
 *
 * Renders editor tabs as an overlay on the canvas.
 * Features:
 * - Tab-based interface for multiple open files
 * - Unsaved changes indicator (*)
 * - Close tabs with X button
 * - Switch between tabs
 * - Integrates with CodeEditor component
 */

function EditorTabs() {
    const { state, actions } = useFlow();

    // Don't render anything if no tabs are open
    if (state.openEditorTabs.length === 0) {
        return null;
    }

    // If panel is hidden, show a floating button to restore it
    if (!state.editorPanelVisible) {
        return (
            <antd.Button
                type="primary"
                size="large"
                icon={<i className="fas fa-code"></i>}
                onClick={actions.toggleEditorPanel}
                style={{
                    position: 'absolute',
                    bottom: '20px',
                    right: '20px',
                    zIndex: 1000,
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
                    borderRadius: '50%',
                    width: '56px',
                    height: '56px'
                }}
                title={`Show Editor (${state.openEditorTabs.length} file${state.openEditorTabs.length !== 1 ? 's' : ''} open)`}
            >
                {state.openEditorTabs.filter(tab => tab.isDirty).length > 0 && (
                    <antd.Badge
                        count={state.openEditorTabs.filter(tab => tab.isDirty).length}
                        style={{
                            position: 'absolute',
                            top: '-5px',
                            right: '-5px'
                        }}
                    />
                )}
            </antd.Button>
        );
    }

    // Handle tab change (activation)
    const handleTabChange = (activeKey) => {
        actions.setActiveEditorTab(activeKey);
    };

    // Handle tab edit (close)
    const handleEdit = (targetKey, action) => {
        if (action === 'remove') {
            // Check if tab has unsaved changes
            const tabToClose = state.openEditorTabs.find(tab => tab.id === targetKey);
            if (tabToClose && tabToClose.isDirty) {
                antd.Modal.confirm({
                    title: 'Unsaved Changes',
                    content: `"${tabToClose.fileName}" has unsaved changes. Close anyway?`,
                    okText: 'Close',
                    okType: 'danger',
                    cancelText: 'Cancel',
                    onOk: () => {
                        actions.closeEditorTab(targetKey);
                    }
                });
            } else {
                actions.closeEditorTab(targetKey);
            }
        }
    };

    // Handle save in CodeEditor
    const handleEditorSave = (tabId) => {
        actions.updateEditorTabDirty(tabId, false);
        antd.message.success('File saved successfully');
    };

    // Handle change in CodeEditor
    const handleEditorChange = (tabId) => {
        actions.updateEditorTabDirty(tabId, true);
    };

    // Build tab items for Ant Design Tabs
    const tabItems = state.openEditorTabs.map(tab => ({
        key: tab.id,
        label: (
            <span>
                <i className="fas fa-file-code" style={{ marginRight: '6px', color: '#FF6B35' }}></i>
                {tab.fileName}
                {tab.isDirty && <span style={{ color: '#faad14', marginLeft: '4px' }}>●</span>}
            </span>
        ),
        children: (
            <div key={tab.id} style={{ height: '100%', overflow: 'hidden' }}>
                <CodeEditor
                    filePath={tab.filePath}
                    onSave={() => handleEditorSave(tab.id)}
                    onChange={() => handleEditorChange(tab.id)}
                />
            </div>
        )
    }));

    // Handle minimize panel (hide without closing tabs)
    const handleMinimize = () => {
        actions.toggleEditorPanel();
    };

    return (
        <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.3)',
            zIndex: 1000,
            display: 'flex',
            flexDirection: 'column',
            padding: '20px',
            pointerEvents: 'auto'
        }}>
            <div style={{
                background: 'white',
                borderRadius: '8px',
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                position: 'relative'
            }}>
                {/* Minimize Panel Button */}
                <antd.Button
                    type="text"
                    icon={<i className="fas fa-window-minimize"></i>}
                    onClick={handleMinimize}
                    style={{
                        position: 'absolute',
                        top: '8px',
                        right: '8px',
                        zIndex: 10
                    }}
                    title="Hide Editor Panel"
                />

                <antd.Tabs
                    type="editable-card"
                    activeKey={state.activeEditorTabId}
                    onChange={handleTabChange}
                    onEdit={handleEdit}
                    hideAdd
                    style={{ height: '100%' }}
                    items={tabItems}
                    tabBarStyle={{
                        margin: 0,
                        paddingLeft: '8px',
                        paddingRight: '48px',
                        background: '#fafafa',
                        borderBottom: '1px solid #f0f0f0'
                    }}
                    tabBarGutter={4}
                />
            </div>
        </div>
    );
}

// Export component
window.EditorTabs = EditorTabs;
