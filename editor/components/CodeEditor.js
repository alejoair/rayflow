/**
 * CodeEditor Component
 *
 * A code editor component using Ace Editor for editing Python node source code.
 * Features:
 * - Syntax highlighting for Python
 * - Line numbers and code folding
 * - Save functionality with validation
 * - Loading and error states
 * - Auto-backup on save
 */

const { useState, useEffect, useRef } = React;
const { Button, message, Spin, Alert } = antd;

function CodeEditor({ filePath, onSave, onChange }) {
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [sourceCode, setSourceCode] = useState('');
    const [hasChanges, setHasChanges] = useState(false);
    const [editorInitialized, setEditorInitialized] = useState(false);
    const editorRef = useRef(null);
    const aceEditorRef = useRef(null);

    // Load source code when component mounts or filePath changes
    useEffect(() => {
        if (filePath) {
            // Reset editor when file changes
            if (aceEditorRef.current) {
                aceEditorRef.current.destroy();
                aceEditorRef.current = null;
            }
            setEditorInitialized(false);
            loadSourceCode();
        }
    }, [filePath]);

    // Initialize Ace Editor after loading is complete
    useEffect(() => {
        if (editorRef.current && !editorInitialized && !loading && sourceCode) {
            console.log('🎨 Initializing Ace Editor with', sourceCode.length, 'characters');

            // Initialize Ace Editor
            const editor = window.ace.edit(editorRef.current);
            editor.setTheme('ace/theme/monokai');
            editor.session.setMode('ace/mode/python');
            editor.setOptions({
                fontSize: '14px',
                showPrintMargin: false,
                enableBasicAutocompletion: true,
                enableLiveAutocompletion: false,
                highlightActiveLine: true,
                showGutter: true
            });

            // Set initial content
            editor.setValue(sourceCode, -1); // -1 moves cursor to start

            // Force resize to ensure proper display
            setTimeout(() => {
                editor.resize();
            }, 100);

            // Track changes
            editor.on('change', () => {
                setHasChanges(true);
                if (onChange) {
                    onChange();
                }
            });

            aceEditorRef.current = editor;
            setEditorInitialized(true);
            console.log('✅ Ace Editor initialized successfully');
        }
    }, [loading, sourceCode, editorInitialized]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (aceEditorRef.current) {
                aceEditorRef.current.destroy();
                aceEditorRef.current = null;
            }
        };
    }, []);

    const loadSourceCode = async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`/api/nodes/source?file_path=${encodeURIComponent(filePath)}`);

            if (!response.ok) {
                throw new Error(`Failed to load source code: ${response.statusText}`);
            }

            const data = await response.json();
            setSourceCode(data.content);
            setHasChanges(false);
        } catch (err) {
            setError(err.message);
            message.error('Failed to load source code');
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        if (!aceEditorRef.current) return;

        const content = aceEditorRef.current.getValue();
        setSaving(true);
        setError(null);

        try {
            const response = await fetch('/api/nodes/source', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    file_path: filePath,
                    content: content
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to save source code');
            }

            if (data.success) {
                message.success('Source code saved successfully!');
                setHasChanges(false);
                if (data.backup_path) {
                    message.info(`Backup created: ${data.backup_path}`);
                }
                if (onSave) {
                    onSave();
                }
            } else {
                throw new Error(data.message || 'Save failed');
            }
        } catch (err) {
            setError(err.message);
            message.error(err.message);
        } finally {
            setSaving(false);
        }
    };

    const handleReload = () => {
        loadSourceCode();
    };

    if (loading) {
        return (
            React.createElement('div', { style: { textAlign: 'center', padding: '50px' } },
                React.createElement(Spin, { size: 'large', tip: 'Loading source code...' })
            )
        );
    }

    return (
        React.createElement('div', { style: { display: 'flex', flexDirection: 'column', height: '100%' } },
            // Header with buttons
            React.createElement('div', {
                style: {
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '10px',
                    padding: '10px',
                    background: '#f5f5f5',
                    borderRadius: '4px'
                }
            },
                React.createElement('div', { style: { display: 'flex', gap: '8px' } },
                    React.createElement(Button, {
                        type: 'primary',
                        onClick: handleSave,
                        loading: saving,
                        disabled: !hasChanges
                    }, hasChanges ? 'Save Changes' : 'Saved'),
                    React.createElement(Button, {
                        onClick: handleReload,
                        disabled: saving
                    }, 'Reload')
                ),
                hasChanges && React.createElement('span', {
                    style: { color: '#faad14', fontSize: '12px' }
                }, '● Unsaved changes')
            ),

            // Error display
            error && React.createElement(Alert, {
                message: 'Error',
                description: error,
                type: 'error',
                closable: true,
                onClose: () => setError(null),
                style: { marginBottom: '10px' }
            }),

            // Editor container
            React.createElement('div', {
                ref: editorRef,
                style: {
                    flex: 1,
                    border: '1px solid #d9d9d9',
                    borderRadius: '4px',
                    overflow: 'hidden'
                }
            })
        )
    );
}

// Export component
window.CodeEditor = CodeEditor;
