import { html } from 'htm/react';
import { useState } from 'react';
import { createFlow, deleteFlow } from './api.js';

function NewFlowModal({ onClose, onCreate }) {
  const [name, setName] = useState('');
  const [inputsRaw, setInputsRaw] = useState('{}');
  const [outputsRaw, setOutputsRaw] = useState('{}');
  const [err, setErr] = useState('');

  async function handleCreate() {
    setErr('');
    if (!name.trim()) { setErr('El nombre es requerido'); return; }
    let inputs, outputs;
    try { inputs = JSON.parse(inputsRaw); outputs = JSON.parse(outputsRaw); }
    catch { setErr('inputs/outputs deben ser JSON válido, ej: {"x": "int"}'); return; }
    try {
      const flow = await createFlow({ name: name.trim(), version: '1', inputs, outputs, variables: [], events: [], nodes: [] });
      onCreate(flow);
      onClose();
    } catch (e) { setErr(e.message); }
  }

  return html`
    <div class="modal-overlay" onClick=${e => e.target === e.currentTarget && onClose()}>
      <div class="modal">
        <div class="modal-title">Nuevo flow</div>
        <div class="prop-field">
          <label style=${{ display:'block', marginBottom:3, fontSize:12 }}>Nombre</label>
          <input class="prop-input" value=${name} onInput=${e => setName(e.target.value)} placeholder="mi_flow" autoFocus />
        </div>
        <div class="prop-field">
          <label style=${{ display:'block', marginBottom:3, fontSize:12 }}>Inputs JSON <span style=${{ color:'var(--text-muted)' }}>ej: {"x":"int"}</span></label>
          <textarea class="prop-input textarea" style=${{ height:56 }} value=${inputsRaw} onInput=${e => setInputsRaw(e.target.value)} />
        </div>
        <div class="prop-field">
          <label style=${{ display:'block', marginBottom:3, fontSize:12 }}>Outputs JSON</label>
          <textarea class="prop-input textarea" style=${{ height:56 }} value=${outputsRaw} onInput=${e => setOutputsRaw(e.target.value)} />
        </div>
        ${err && html`<div style=${{ color:'var(--error-color)', fontSize:12, marginTop:6 }}>${err}</div>`}
        <div class="modal-footer">
          <button class="btn" onClick=${onClose}>Cancelar</button>
          <button class="btn btn-primary" onClick=${handleCreate}>Crear</button>
        </div>
      </div>
    </div>
  `;
}

export default function FlowManager({ flows, activeFlow, onSelectFlow, onFlowCreated, onFlowDeleted, onSave, onValidate, validationErrors, saving }) {
  const [showNew, setShowNew] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function handleDelete() {
    if (!activeFlow) return;
    try {
      await deleteFlow(activeFlow.name);
      onFlowDeleted(activeFlow.name);
      setConfirmDelete(false);
    } catch (e) { alert(e.message); }
  }

  const validStatus = !activeFlow ? 'unknown' : validationErrors.length === 0 ? 'valid' : 'invalid';

  return html`
    <header class="app-header">
      <span class="logo">Rayflow</span>
      <div class="header-sep"></div>

      <select class="flow-select" value=${activeFlow?.name ?? ''} onChange=${e => onSelectFlow(e.target.value)}>
        <option value="">— Abrir flow —</option>
        ${flows.map(f => html`<option key=${f.name} value=${f.name}>${f.name}</option>`)}
      </select>

      <button class="btn btn-sm" onClick=${() => setShowNew(true)}>+ Nuevo</button>
      <div class="header-sep"></div>

      ${activeFlow && html`
        <button class="btn btn-sm btn-primary" onClick=${onSave} disabled=${saving}>${saving ? 'Guardando…' : '💾 Guardar'}</button>
        <button class="btn btn-sm" onClick=${onValidate}>✓ Validar</button>
        <button class="btn btn-sm btn-danger" onClick=${() => setConfirmDelete(true)}>🗑</button>
        <div class="header-sep"></div>
      `}

      <div class="header-spacer"></div>

      ${activeFlow && html`
        <span class=${'status-badge status-' + validStatus}>
          ${validStatus === 'valid' ? '✓ Válido' : validStatus === 'invalid' ? `✗ ${validationErrors.length} error(es)` : '—'}
        </span>
      `}
      ${!activeFlow && html`<span style=${{ color:'var(--text-muted)', fontSize:12 }}>Ningún flow abierto</span>`}
    </header>

    ${showNew && html`<${NewFlowModal} onClose=${() => setShowNew(false)} onCreate=${onFlowCreated} />`}

    ${confirmDelete && html`
      <div class="modal-overlay" onClick=${e => e.target===e.currentTarget && setConfirmDelete(false)}>
        <div class="modal">
          <div class="modal-title">¿Borrar "${activeFlow?.name}"?</div>
          <p style=${{ fontSize:13, color:'var(--text-muted)', marginTop:8 }}>Esta acción no se puede deshacer.</p>
          <div class="modal-footer">
            <button class="btn" onClick=${() => setConfirmDelete(false)}>Cancelar</button>
            <button class="btn btn-danger" onClick=${handleDelete}>Borrar</button>
          </div>
        </div>
      </div>
    `}
  `;
}
