// Enhanced Node Component with improved layout and visual design
function NodeComponent({ data, selected }) {
    const { Handle, Position } = window.ReactFlow;

    // Get configuration from parent
    const getTypeColor = (type) => {
        if (!window.typeConfig) return '#1890ff';
        return window.typeConfig.dataTypes[type]?.color || '#1890ff';
    };

    const getHandleSize = (isExec) => {
        if (!window.typeConfig) return isExec ? 16 : 14; // Larger handles for better usability
        return window.typeConfig.settings.handleSize[isExec ? 'exec' : 'data'] + 4; // Add 4px
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

    // Calculate layout dimensions
    const inputCount = (execInput ? 1 : 0) + Object.keys(inputs).length;
    const outputCount = (execOutput ? 1 : 0) + Object.keys(outputs).length;
    const maxPortCount = Math.max(inputCount, outputCount);

    // More generous spacing for better readability
    const headerHeight = 50;
    const portSpacing = 40;
    const minContentHeight = maxPortCount > 0 ? (maxPortCount * portSpacing) + 20 : 60;
    const totalHeight = headerHeight + minContentHeight;

    // Generate all handles with synchronized positioning
    const renderAllHandles = () => {
        const inputHandles = [];
        const outputHandles = [];
        let currentPosition = headerHeight + 20; // Start after header with padding

        // Handle exec ports first (if any exist)
        if (execInput || execOutput) {
            // Exec input handle
            if (execInput) {
                const execSize = getHandleSize(true);
                inputHandles.push(
                    <Handle
                        key="exec-in"
                        type="target"
                        position={Position.Left}
                        id="exec-in"
                        style={{
                            top: `${currentPosition}px`,
                            background: getTypeColor('exec'),
                            width: `${execSize}px`,
                            height: `${execSize}px`,
                            border: '2px solid #000',
                            borderRadius: '50%',
                            boxShadow: '0 2px 4px rgba(0,0,0,0.3)'
                        }}
                    />
                );
            }

            // Exec output handle
            if (execOutput) {
                const execSize = getHandleSize(true);
                outputHandles.push(
                    <Handle
                        key="exec-out"
                        type="source"
                        position={Position.Right}
                        id="exec-out"
                        style={{
                            top: `${currentPosition}px`,
                            background: getTypeColor('exec'),
                            width: `${execSize}px`,
                            height: `${execSize}px`,
                            border: '2px solid #000',
                            borderRadius: '50%',
                            boxShadow: '0 2px 4px rgba(0,0,0,0.3)'
                        }}
                    />
                );
            }
            currentPosition += portSpacing;
        }

        // Handle data ports in pairs
        const inputKeys = Object.keys(inputs);
        const outputKeys = Object.keys(outputs);
        const maxDataPorts = Math.max(inputKeys.length, outputKeys.length);

        for (let i = 0; i < maxDataPorts; i++) {
            // Input handle
            if (i < inputKeys.length) {
                const inputName = inputKeys[i];
                const inputType = inputs[inputName];
                const dataSize = getHandleSize(false);
                inputHandles.push(
                    <Handle
                        key={`input-${inputName}`}
                        type="target"
                        position={Position.Left}
                        id={`input-${inputName}`}
                        style={{
                            top: `${currentPosition}px`,
                            background: getTypeColor(inputType),
                            width: `${dataSize}px`,
                            height: `${dataSize}px`,
                            border: '2px solid #000',
                            borderRadius: '3px',
                            boxShadow: '0 2px 4px rgba(0,0,0,0.3)'
                        }}
                    />
                );
            }

            // Output handle
            if (i < outputKeys.length) {
                const outputName = outputKeys[i];
                const outputType = outputs[outputName];
                const dataSize = getHandleSize(false);
                outputHandles.push(
                    <Handle
                        key={`output-${outputName}`}
                        type="source"
                        position={Position.Right}
                        id={`output-${outputName}`}
                        style={{
                            top: `${currentPosition}px`,
                            background: getTypeColor(outputType),
                            width: `${dataSize}px`,
                            height: `${dataSize}px`,
                            border: '2px solid #000',
                            borderRadius: '3px',
                            boxShadow: '0 2px 4px rgba(0,0,0,0.3)'
                        }}
                    />
                );
            }

            currentPosition += portSpacing;
        }

        return [...inputHandles, ...outputHandles];
    };

    // Render port rows for better organization
    const renderPortRows = () => {
        const rows = [];
        let currentPosition = headerHeight + 20;

        // Handle exec ports - only if either input OR output exec exists
        if (execInput || execOutput) {
            rows.push(
                <div key="exec-row" style={{
                    position: 'absolute',
                    top: `${currentPosition}px`,
                    left: '0',
                    right: '0',
                    height: '20px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0 24px',
                    pointerEvents: 'none'
                }}>
                    {execInput && (
                        <div style={{
                            fontSize: '12px',
                            color: getTypeColor('exec'),
                            fontWeight: '600',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px'
                        }}>
                            EXEC
                        </div>
                    )}
                    {execOutput && (
                        <div style={{
                            fontSize: '12px',
                            color: getTypeColor('exec'),
                            fontWeight: '600',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px'
                        }}>
                            EXEC
                        </div>
                    )}
                </div>
            );
            currentPosition += portSpacing;
        }

        // Handle data ports
        const inputKeys = Object.keys(inputs);
        const outputKeys = Object.keys(outputs);
        const maxDataPorts = Math.max(inputKeys.length, outputKeys.length);

        for (let i = 0; i < maxDataPorts; i++) {
            const inputName = inputKeys[i];
            const outputName = outputKeys[i];
            const inputType = inputName ? inputs[inputName] : null;
            const outputType = outputName ? outputs[outputName] : null;

            rows.push(
                <div key={`data-row-${i}`} style={{
                    position: 'absolute',
                    top: `${currentPosition}px`,
                    left: '0',
                    right: '0',
                    height: '20px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0 24px',
                    pointerEvents: 'none'
                }}>
                    {inputName && (
                        <div style={{
                            fontSize: '13px',
                            color: getTypeColor(inputType),
                            fontWeight: '600',
                            textShadow: '0 1px 2px rgba(0,0,0,0.8)',
                            filter: 'brightness(1.1)'
                        }}>
                            {inputName}
                        </div>
                    )}
                    {outputName && (
                        <div style={{
                            fontSize: '13px',
                            color: getTypeColor(outputType),
                            fontWeight: '600',
                            textAlign: 'right',
                            textShadow: '0 1px 2px rgba(0,0,0,0.8)',
                            filter: 'brightness(1.1)'
                        }}>
                            {outputName}
                        </div>
                    )}
                </div>
            );
            currentPosition += portSpacing;
        }

        return rows;
    };

    return (
        <div style={{
            position: 'relative',
            borderRadius: '12px',
            background: selected
                ? 'linear-gradient(145deg, #2a2a2a, #1e1e1e)'
                : 'linear-gradient(145deg, #252525, #1a1a1a)',
            border: selected
                ? '2px solid #1890ff'
                : (isCustomNode ? `2px solid ${customIndicator.borderColor}` : '2px solid #3a3a3a'),
            boxShadow: selected
                ? '0 8px 25px rgba(24, 144, 255, 0.3), 0 0 0 1px rgba(24, 144, 255, 0.2)'
                : '0 4px 15px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
            color: 'white',
            minWidth: '240px',
            height: `${totalHeight}px`,
            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            overflow: 'visible'
        }}>
            {/* Custom node indicator badge */}
            {isCustomNode && (
                <div style={{
                    position: 'absolute',
                    top: '-10px',
                    right: '-10px',
                    background: `linear-gradient(135deg, ${customIndicator.color}, #d94a1a)`,
                    color: 'white',
                    fontSize: '10px',
                    fontWeight: '700',
                    padding: '4px 8px',
                    borderRadius: '12px',
                    border: '2px solid #1a1a1a',
                    zIndex: 10,
                    textShadow: '0 1px 2px rgba(0,0,0,0.7)',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.3)'
                }}>
                    {customIndicator.badgeText}
                </div>
            )}

            {/* Node header */}
            <div style={{
                height: `${headerHeight}px`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '10px',
                padding: '0 20px',
                borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
                background: 'linear-gradient(135deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02))',
                borderRadius: '10px 10px 0 0'
            }}>
                {data.icon && (
                    <i className={`fas ${data.icon}`} style={{
                        color: isCustomNode ? customIndicator.iconColor : '#1890ff',
                        fontSize: '18px',
                        filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.5))'
                    }}></i>
                )}
                <span style={{
                    fontSize: '15px',
                    fontWeight: '600',
                    textShadow: '0 1px 2px rgba(0,0,0,0.5)',
                    letterSpacing: '0.3px'
                }}>
                    {data.label ? data.label.charAt(0).toUpperCase() + data.label.slice(1) : 'Unknown'}
                </span>
            </div>

            {/* Port rows */}
            {renderPortRows()}

            {/* Handles */}
            {renderAllHandles()}
        </div>
    );
}