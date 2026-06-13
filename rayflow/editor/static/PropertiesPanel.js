import { html } from 'htm/react';

function LiteralField({ pin, value, onChange, catalog, flowList }) {
  const t = (pin.type || 'Any').toLowerCase();

  if (pin.name === 'node_type') {
    return html`
      <div class="prop-field">
        <label>${pin.name} <span style=${{ color:'var(--type-any)' }}>(${pin.type})</span></label>
        <select class="prop-input" value=${value ?? ''} onChange=${e => onChange(e.target.value)}>
          <option value="">— elegir —</option>
          ${Object.keys(catalog).map(t => html`<option key=${t} value=${t}>${t}</option>`)}
        </select>
      </div>
    `;
  }

  if (pin.name === 'flow' && flowList) {
    return html`
      <div class="prop-field">
        <label>${pin.name} <span style=${{ color:'var(--type-any)' }}>(flow)</span></label>
        <select class="prop-input" value=${value ?? ''} onChange=${e => onChange(e.target.value)}>
          <option value="">— elegir —</option>
          ${flowList.map(f => html`<option key=${f.name} value=${f.name}>${f.name}</option>`)}
        </select>
      </div>
    `;
  }

  if (t === 'bool') {
    return html`
      <div class="prop-field">
        <label class="prop-checkbox">
          <input type="checkbox" checked=${!!value} onChange=${e => onChange(e.target.checked)} />
          ${pin.name}
        </label>
      </div>
    `;
  }

  if (t === 'int' || t === 'float') {
    return html`
      <div class="prop-field">
        <label>${pin.name} <span style=${{ color:'var(--type-any)' }}>(${pin.type})</span></label>
        <input
          type="number"
          class="prop-input"
          step=${t === 'float' ? 'any' : '1'}
          value=${value ?? (pin.default ?? '')}
          onInput=${e => onChange(t === 'float' ? parseFloat(e.target.value) : parseInt(e.target.value, 10))}
        />
      </div>
    `;
  }

  if (t === 'list' || t === 'dict' || t.startsWith('list[') || t.startsWith('dict[')) {
    const display = typeof value === 'string' ? value : JSON.stringify(value ?? (t.startsWith('list') ? [] : {}), null, 2);
    return html`
      <div class="prop-field">
        <label>${pin.name} <span style=${{ color:'var(--type-any)' }}>(${pin.type})</span></label>
        <textarea
          class="prop-input textarea"
          value=${display}
          onInput=${e => { try { onChange(JSON.parse(e.target.value)); } catch { onChange(e.target.value); } }}
        />
      </div>
    `;
  }

  return html`
    <div class="prop-field">
      <label>${pin.name} <span style=${{ color:'var(--type-any)' }}>(${pin.type})</span></label>
      <input
        type="text"
        class="prop-input"
        value=${value ?? (pin.default ?? '')}
        onInput=${e => onChange(e.target.value)}
      />
    </div>
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
      <div class="sidebar-body">

        <div class="prop-section">
          <div class="prop-label">Nodo</div>
          <div class="prop-field">
            <label>Tipo</label>
            <div style=${{ fontSize: 13, fontWeight: 600, color: 'var(--accent)', padding: '4px 0' }}>${node.data.nodeType}</div>
          </div>
          <div class="prop-field">
            <label>ID</label>
            <input
              type="text"
              class="prop-input"
              defaultValue=${node.id}
              onBlur=${e => updateId(e.target.value.trim())}
              onKeyDown=${e => { if (e.key === 'Enter') updateId(e.target.value.trim()); }}
            />
          </div>
        </div>

        ${editablePins.length > 0 && html`
          <div class="prop-section">
            <div class="prop-label">Inputs literales</div>
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
            <div class="prop-label" style=${{ color: 'var(--error-color)' }}>Errores</div>
            <div class="error-list">
              ${nodeErrors.map((e, i) => html`<div key=${i} class="error-item">${e}</div>`)}
            </div>
          </div>
        `}

      </div>
    </div>
  `;
}
