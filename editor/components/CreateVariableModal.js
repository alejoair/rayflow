// Create Variable Modal Component
function CreateVariableModal({ visible, onClose, onCreateVariable, existingVariables }) {
    const [variableName, setVariableName] = React.useState('');
    const [variableType, setVariableType] = React.useState('int');
    const [defaultValue, setDefaultValue] = React.useState(0);
    const [customImport, setCustomImport] = React.useState('');
    const [typeConfig, setTypeConfig] = React.useState(null);
    const [nameError, setNameError] = React.useState('');

    // Load data type configuration
    React.useEffect(() => {
        fetch('/config/data-types.json')
            .then(response => response.json())
            .then(data => setTypeConfig(data))
            .catch(error => {
                console.error('Failed to load type configuration:', error);
            });
    }, []);

    // Reset form when modal opens/closes
    React.useEffect(() => {
        if (visible) {
            setVariableName('');
            setVariableType('int');
            setDefaultValue(0);
            setCustomImport('');
            setNameError('');
        }
    }, [visible]);

    // Update default value when type changes
    React.useEffect(() => {
        if (!typeConfig) return;

        const typeInfo = typeConfig.dataTypes[variableType];
        if (!typeInfo) return;

        // Set appropriate default value for the type
        switch (variableType) {
            case 'int':
                setDefaultValue(0);
                break;
            case 'float':
                setDefaultValue(0.0);
                break;
            case 'str':
                setDefaultValue('');
                break;
            case 'bool':
                setDefaultValue(false);
                break;
            case 'dict':
                setDefaultValue({});
                break;
            case 'list':
                setDefaultValue([]);
                break;
            case 'custom':
                setDefaultValue('');
                break;
            default:
                setDefaultValue(null);
        }
    }, [variableType, typeConfig]);

    // Validate variable name
    const validateName = (name) => {
        if (!name) {
            setNameError('Variable name is required');
            return false;
        }

        if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name)) {
            setNameError('Variable name must be a valid Python identifier (letters, numbers, underscores, cannot start with number)');
            return false;
        }

        if (existingVariables.some(v => v.name === name)) {
            setNameError('Variable name already exists');
            return false;
        }

        setNameError('');
        return true;
    };

    // Render default value input based on type
    const renderDefaultValueInput = () => {
        if (!typeConfig || !typeConfig.dataTypes[variableType]) return null;

        const typeInfo = typeConfig.dataTypes[variableType];

        switch (typeInfo.fieldType) {
            case 'number':
                return (
                    <antd.InputNumber
                        value={defaultValue}
                        onChange={setDefaultValue}
                        style={{ width: '100%' }}
                        {...typeInfo.inputProps}
                    />
                );
            case 'text':
                return (
                    <antd.Input
                        value={defaultValue}
                        onChange={(e) => setDefaultValue(e.target.value)}
                        {...typeInfo.inputProps}
                    />
                );
            case 'switch':
                return (
                    <antd.Switch
                        checked={defaultValue}
                        onChange={setDefaultValue}
                        {...typeInfo.inputProps}
                    />
                );
            case 'textarea':
                return (
                    <antd.Input.TextArea
                        value={typeof defaultValue === 'object' ? JSON.stringify(defaultValue, null, 2) : defaultValue}
                        onChange={(e) => {
                            try {
                                const parsed = JSON.parse(e.target.value);
                                setDefaultValue(parsed);
                            } catch {
                                setDefaultValue(e.target.value);
                            }
                        }}
                        {...typeInfo.inputProps}
                    />
                );
            default:
                return (
                    <antd.Input
                        value={defaultValue}
                        onChange={(e) => setDefaultValue(e.target.value)}
                        placeholder="Enter default value"
                    />
                );
        }
    };

    const handleCreate = async () => {
        if (!validateName(variableName)) {
            return;
        }

        if (variableType === 'custom' && !customImport.trim()) {
            antd.message.error('Python import is required for custom types');
            return;
        }

        // Prepare API request data
        const requestData = {
            variable_name: variableName,
            value_type: variableType,
            default_value: variableType === 'custom' ? null : String(defaultValue),
            description: `Variable ${variableName}`,
            icon: 'fa-variable',
            category: 'user-created',
            is_custom: variableType === 'custom',
            custom_import: variableType === 'custom' ? customImport : null,
            custom_type_hint: null, // Could be extracted from import in future
            tags: ['user-created'],
            is_readonly: false
        };

        try {
            // Call API to create variable file
            const response = await fetch('/api/variables/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to create variable');
            }

            const responseData = await response.json();

            // Create variable object for UI state
            const newVariable = {
                id: `var_${Date.now()}`,
                name: variableName,
                type: variableType,
                defaultValue: defaultValue,
                isCustom: variableType === 'custom',
                customImport: variableType === 'custom' ? customImport : null,
                createdAt: new Date().toISOString(),
                filePath: responseData.file_path // Store the file path from API
            };

            onCreateVariable(newVariable);
            onClose();
            antd.message.success(`Variable '${variableName}' created successfully! File: ${responseData.file_path}`);

        } catch (error) {
            console.error('Error creating variable:', error);
            antd.message.error(`Failed to create variable: ${error.message}`);
        }
    };

    const typeOptions = [
        { value: 'int', label: 'Integer (int)' },
        { value: 'float', label: 'Float (float)' },
        { value: 'str', label: 'String (str)' },
        { value: 'bool', label: 'Boolean (bool)' },
        { value: 'dict', label: 'Dictionary (dict)' },
        { value: 'list', label: 'List (list)' },
        { value: 'custom', label: 'Custom Type ⚠️' }
    ];

    return (
        <antd.Modal
            title={
                <antd.Space>
                    <i className="fas fa-plus-circle" style={{ color: '#1890ff' }}></i>
                    <span>Create New Variable</span>
                </antd.Space>
            }
            open={visible}
            onOk={handleCreate}
            onCancel={onClose}
            width={600}
            okText="Create"
            cancelText="Cancel"
        >
            <antd.Space direction="vertical" style={{ width: '100%' }} size="large">
                {/* Information Alert */}
                <antd.Alert
                    message="About Variables"
                    description={
                        <div>
                            <p style={{ marginBottom: '8px' }}>Variables in RayFlow are <strong>global</strong> and can store any Python data type.</p>
                            <ul style={{ marginBottom: 0, paddingLeft: '20px' }}>
                                <li>Variables persist throughout workflow execution</li>
                                <li>Use Set nodes to store values</li>
                                <li>Use Get nodes to retrieve values</li>
                                <li>No execution flow (exec) connections needed</li>
                            </ul>
                        </div>
                    }
                    type="info"
                    showIcon
                    icon={<i className="fas fa-info-circle"></i>}
                />

                {/* Variable Name */}
                <antd.Form.Item
                    label="Variable Name"
                    required
                    validateStatus={nameError ? 'error' : ''}
                    help={nameError}
                    style={{ marginBottom: 0 }}
                >
                    <antd.Input
                        placeholder="my_variable"
                        value={variableName}
                        onChange={(e) => {
                            setVariableName(e.target.value);
                            validateName(e.target.value);
                        }}
                        prefix={<i className="fas fa-signature" style={{ color: '#8c8c8c' }}></i>}
                    />
                </antd.Form.Item>

                {/* Data Type */}
                <antd.Form.Item label="Data Type" required style={{ marginBottom: 0 }}>
                    <antd.Select
                        value={variableType}
                        onChange={setVariableType}
                        style={{ width: '100%' }}
                        options={typeOptions}
                    />
                </antd.Form.Item>

                {/* Custom Import (only for custom type) */}
                {variableType === 'custom' && (
                    <>
                        <antd.Form.Item label="Python Import" required style={{ marginBottom: 0 }}>
                            <antd.Input
                                placeholder="import numpy as np"
                                value={customImport}
                                onChange={(e) => setCustomImport(e.target.value)}
                                prefix={<i className="fas fa-code" style={{ color: '#8c8c8c' }}></i>}
                            />
                        </antd.Form.Item>
                        <antd.Alert
                            message="Custom Type Warning"
                            description="Custom types are not validated by the editor. Incorrect imports or type mismatches may cause runtime errors in your flow."
                            type="warning"
                            showIcon
                            icon={<i className="fas fa-exclamation-triangle"></i>}
                        />
                    </>
                )}

                {/* Default Value */}
                {variableType !== 'custom' && (
                    <antd.Form.Item label="Default Value" style={{ marginBottom: 0 }}>
                        {renderDefaultValueInput()}
                    </antd.Form.Item>
                )}
            </antd.Space>
        </antd.Modal>
    );
}
