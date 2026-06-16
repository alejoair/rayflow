import htm from 'htm';
import { createElement } from 'react';
const html = htm.bind(createElement);

function LiteralField({ pin, value, onChange, catalog, flowList }) {
  const t = (pin.type || 'Any').toLowerCase();

  if (pin.name === 'node_type') {
    return html`
      <sl-select
        label=${`${pin.name} (${pin.type})`}
        value=${value ?? ''}
        onsl-change=${e => onChange(e.target.value)}
        size="small"
        clearable
      >
        ${Object.keys(catalog).map(k => html`<sl-option key=${k} value=${k}>${k}</sl-option>`)}
      </sl-select>
    `;
  }

  if (pin.name === 'flow' && flowList) {
    return html`
      <sl-select
        label="${pin.name} (flow)"
        value=${value ?? ''}
        onsl-change=${e => onChange(e.target.value)}
        size="small"
        clearable
      >
        ${flowList.map(f => html`<sl-option key=${f.name} value=${f.name}>${f.name}</sl-option>`)}
      </sl-select>
    `;
  }

  if (t === 'bool') {
    return html`
      <sl-checkbox
        ?checked=${!!value}
        onsl-change=${e => onChange(e.target.checked)}
        size="small"
      >${pin.name}</sl-checkbox>
    `;
  }

  if (t === 'int' || t === 'float') {
    return html`
      <sl-input
        label=${`${pin.name} (${pin.type})`}
        type="number"
        step=${t === 'float' ? 'any' : '1'}
        value=${value ?? (pin.default ?? '')}
        onsl-input=${e => onChange(t === 'float' ? parseFloat(e.target.value) : parseInt(e.target.value, 10))}
        size="small"
      ></sl-input>
    `;
  }

  if (t === 'list' || t === 'dict' || t.startsWith('list[') || t.startsWith('dict[')) {
    const display = typeof value === 'string' ? value : JSON.stringify(value ?? (t.startsWith('list') ? [] : {}), null, 2);
    return html`
      <sl-textarea
        label=${`${pin.name} (${pin.type})`}
        rows="3"
        value=${display}
        onsl-input=${e => { try { onChange(JSON.parse(e.target.value)); } catch { onChange(e.target.value); } }}
        size="small"
        style=${{ fontFamily: 'monospace', fontSize: 11 }}
      ></sl-textarea>
    `;
  }

  return html`
    <sl-input
      label=${`${pin.name} (${pin.type})`}
      type="text"
      value=${value ?? (pin.default ?? '')}
      onsl-input=${e => onChange(e.target.value)}
      size="small"
    ></sl-input>
  `;
}

export default function PropertiesPanel({ selectedNodeId, nodes, edges, catalog, flowList, onUpdateNode, validationErrors }) {
  const node = nodes.find(n => n.id === selectedNodeId);

  if (!node) {
    return html`
      <div class="sidebar-right">
        <div class="sidebar-header">Propiedades</div>
        <div class="no-selection">Selecciona un nodo en el canvas</div>
      </div>
    `;
  }

  const meta = catalog[node.data.nodeType];
  const literals = node.data.literals || {};

  const connectedInputs = new Set(
    edges
      .filter(e => e.target === node.id && e.type !== 'exec')
      .map(e => (e.targetHandle || '').replace('data-in-', ''))
  );

  function updateLiteral(pinName, val) {
    onUpdateNode(node.id, { literals: { ...literals, [pinName]: val } });
  }

  function updateId(newId) {
    if (newId && newId !== node.id) onUpdateNode(node.id, { newId });
  }

  const nodeErrors = validationErrors.filter(e => e.includes(node.id) || e.includes(node.data.nodeType));
  const editablePins = meta ? meta.inputs.filter(p => !connectedInputs.has(p.name)) : [];

  return html`
    <div class="sidebar-right">
      <div class="sidebar-header">Propiedades</div>
      <div class="sidebar-body" style=${{ display: 'flex', flexDirection: 'column', gap: 4 }}>

        <div class="prop-section">
          <div class="prop-label">Nodo</div>
          <div style=${{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <sl-input label="Tipo" value=${node.data.nodeType} readonly size="small"></sl-input>
            <sl-input
              label="ID"
              size="small"
              value=${node.id}
              onsl-change=${e => updateId(e.target.value.trim())}
            ></sl-input>
          </div>
        </div>

        ${editablePins.length > 0 && html`
          <div class="prop-section">
            <div class="prop-label">Inputs literales</div>
            <div style=${{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              ${editablePins.map(p => html`
                <${LiteralField}
                  key=${p.name}
                  pin=${p}
                  value=${literals[p.name]}
                  onChange=${val => updateLiteral(p.name, val)}
                  catalog=${catalog}
                  flowList=${flowList}
                />
              `)}
            </div>
          </div>
        `}

        ${connectedInputs.size > 0 && html`
          <div class="prop-section">
            <div class="prop-label">Conectados</div>
            ${[...connectedInputs].map(pin => html`
              <div key=${pin} style=${{ fontSize: 11, color: 'var(--text-muted)', padding: '2px 0' }}>${pin} ← arista</div>
            `)}
          </div>
        `}

        ${nodeErrors.length > 0 && html`
          <div class="prop-section">
            <sl-alert variant="danger" open>
              <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
              <div class="error-list">
                ${nodeErrors.map((e, i) => html`<div key=${i} class="error-item">${e}</div>`)}
              </div>
            </sl-alert>
          </div>
        `}

      </div>
    </div>
  `;
}
