// Custom Node Component with dynamic handles
function NodeComponent({ data, selected }) {
    const { Handle, Position } = window.ReactFlow;

    // Get configuration from parent
    const getTypeColor = (type) => {
        if (!window.typeConfig) return '#1890ff';
        return window.typeConfig.dataTypes[type]?.color || '#1890ff';
    };

    const getHandleSize = (isExec) => {
        if (!window.typeConfig) return isExec ? 12 : 10;
        return window.typeConfig.settings.handleSize[isExec ? 'exec' : 'data'];
    };

    const getCustomIndicator = () => {
        if (!window.typeConfig) return {
            color: '#FF6B35',
            iconColor: '#FF6B35',
            borderColor: '#FF6B35',
            badgeText: 'CUSTOM'
        };
        return window.typeConfig.settings.customNodeIndicator;
    };

    const inputs = data.inputs || {};
    const outputs = data.outputs || {};
    const hasDataInputs = Object.keys(inputs).length > 0;
    const hasDataOutputs = Object.keys(outputs).length > 0;
    const execInput = data.exec_input !== undefined ? data.exec_input : true;
    const execOutput = data.exec_output !== undefined ? data.exec_output : true;
    const isCustomNode = data.nodeType === 'user';
    const customIndicator = getCustomIndicator();

    // Generate handles
    const inputHandles = [];
    const outputHandles = [];

    // Add exec input handle if needed
    if (execInput) {
        const execSize = getHandleSize(true);
        inputHandles.push(
            <Handle
                key="exec-in"
                type="target"
                position={Position.Left}
                id="exec-in"
                style={{
                    top: hasDataInputs ? '25%' : '50%',
                    background: getTypeColor('exec'),
                    width: `${execSize}px`,
                    height: `${execSize}px`
                }}
            />
        );
    }

    // Add individual data input handles
    if (hasDataInputs) {
        const inputKeys = Object.keys(inputs);
        const startPosition = execInput ? 60 : 30;
        const spacing = 25;

        inputKeys.forEach((inputName, index) => {
            const inputType = inputs[inputName];
            const dataSize = getHandleSize(false);
            inputHandles.push(
                <Handle
                    key={`input-${inputName}`}
                    type="target"
                    position={Position.Left}
                    id={`input-${inputName}`}
                    style={{
                        top: `${startPosition + (index * spacing)}px`,
                        background: getTypeColor(inputType),
                        width: `${dataSize}px`,
                        height: `${dataSize}px`
                    }}
                />
            );
        });
    }

    // Add exec output handle if needed
    if (execOutput) {
        const execSize = getHandleSize(true);
        outputHandles.push(
            <Handle
                key="exec-out"
                type="source"
                position={Position.Right}
                id="exec-out"
                style={{
                    top: hasDataOutputs ? '25%' : '50%',
                    background: getTypeColor('exec'),
                    width: `${execSize}px`,
                    height: `${execSize}px`
                }}
            />
        );
    }

    // Add individual data output handles
    if (hasDataOutputs) {
        const outputKeys = Object.keys(outputs);
        const startPosition = execOutput ? 60 : 30;
        const spacing = 25;

        outputKeys.forEach((outputName, index) => {
            const outputType = outputs[outputName];
            const dataSize = getHandleSize(false);
            outputHandles.push(
                <Handle
                    key={`output-${outputName}`}
                    type="source"
                    position={Position.Right}
                    id={`output-${outputName}`}
                    style={{
                        top: `${startPosition + (index * spacing)}px`,
                        background: getTypeColor(outputType),
                        width: `${dataSize}px`,
                        height: `${dataSize}px`
                    }}
                />
            );
        });
    }

    // Calculate node height based on number of inputs/outputs
    const maxPorts = Math.max(
        (execInput ? 1 : 0) + Object.keys(inputs).length,
        (execOutput ? 1 : 0) + Object.keys(outputs).length
    );
    const nodeHeight = Math.max(80, 40 + (maxPorts * 25));

    return (
        <div style={{
            padding: '15px',
            borderRadius: '5px',
            background: '#1a1a1a',
            border: selected ? '2px solid #1890ff' : (isCustomNode ? `2px solid ${customIndicator.borderColor}` : '2px solid #333'),
            boxShadow: selected ? '0 0 10px rgba(24, 144, 255, 0.5)' : 'none',
            color: 'white',
            minWidth: '180px',
            minHeight: `${nodeHeight}px`,
            transition: 'all 0.2s ease',
            position: 'relative'
        }}>
            {/* Custom node indicator badge */}
            {isCustomNode && (
                <div style={{
                    position: 'absolute',
                    top: '-8px',
                    right: '-8px',
                    backgroundColor: customIndicator.color,
                    color: 'white',
                    fontSize: '10px',
                    fontWeight: 'bold',
                    padding: '2px 6px',
                    borderRadius: '10px',
                    border: '2px solid #1a1a1a',
                    zIndex: 10,
                    textShadow: '0 1px 2px rgba(0,0,0,0.5)'
                }}>
                    {customIndicator.badgeText}
                </div>
            )}

            {/* Dynamic input handles */}
            {inputHandles}

            {/* Input labels */}
            {hasDataInputs && Object.keys(inputs).map((inputName, index) => {
                const inputType = inputs[inputName];
                return (
                    <div
                        key={`input-label-${inputName}`}
                        style={{
                            position: 'absolute',
                            left: '20px',
                            top: `${(execInput ? 60 : 30) + (index * 25) - 8}px`,
                            fontSize: '11px',
                            color: getTypeColor(inputType),
                            fontWeight: '500'
                        }}
                    >
                        {inputName}: {inputType}
                    </div>
                );
            })}

            {/* Label del nodo con icono */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                fontSize: '14px',
                fontWeight: '500',
                marginBottom: hasDataInputs || hasDataOutputs ? '10px' : '0'
            }}>
                {data.icon && (
                    <i className={`fas ${data.icon}`} style={{
                        color: isCustomNode ? customIndicator.iconColor : '#1890ff',
                        fontSize: '16px'
                    }}></i>
                )}
                <span>{data.label ? data.label.charAt(0).toUpperCase() + data.label.slice(1) : 'Unknown'}</span>
            </div>

            {/* Output labels */}
            {hasDataOutputs && Object.keys(outputs).map((outputName, index) => {
                const outputType = outputs[outputName];
                return (
                    <div
                        key={`output-label-${outputName}`}
                        style={{
                            position: 'absolute',
                            right: '20px',
                            top: `${(execOutput ? 60 : 30) + (index * 25) - 8}px`,
                            fontSize: '11px',
                            color: getTypeColor(outputType),
                            fontWeight: '500',
                            textAlign: 'right'
                        }}
                    >
                        {outputName}: {outputType}
                    </div>
                );
            })}

            {/* Dynamic output handles */}
            {outputHandles}
        </div>
    );
}