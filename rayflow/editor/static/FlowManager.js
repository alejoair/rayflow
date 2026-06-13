import { html } from 'htm/react';
import { useState } from 'react';
import { createFlow } from './api.js';

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
          <label style=${{ display:'block', marginBottom:3, fontSize:12 }}>Inputs JSON</label>
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

export default function FlowManager({ flows, onOpenFlow, onFlowCreated }) {
  const [showNew, setShowNew] = useState(false);

  return html`
    <header class="app-header">
      <span class="logo">Rayflow</span>
      <div class="header-sep"></div>

      <select
        class="flow-select"
        value=""
        onChange=${e => { if (e.target.value) { onOpenFlow(e.target.value); e.target.value = ''; } }}
      >
        <option value="">Abrir flow…</option>
        ${flows.map(f => html`<option key=${f.name} value=${f.name}>${f.name}</option>`)}
      </select>

      <button class="btn btn-sm" onClick=${() => setShowNew(true)}>+ Nuevo</button>
    </header>

    ${showNew && html`
      <${NewFlowModal}
        onClose=${() => setShowNew(false)}
        onCreate=${flow => { onFlowCreated(flow); setShowNew(false); }}
      />
    `}
  `;
}
