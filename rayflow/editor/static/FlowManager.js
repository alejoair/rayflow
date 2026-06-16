import htm from 'htm';
import { createElement, useState, useRef, useEffect } from 'react';
const html = htm.bind(createElement);
import { createFlow, deleteFlow } from './api.js';

function NewFlowModal({ onClose, onCreate }) {
  const [name, setName] = useState('');
  const [inputsRaw, setInputsRaw] = useState('{}');
  const [outputsRaw, setOutputsRaw] = useState('{}');
  const [err, setErr] = useState('');
  const dialogRef = useRef(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (el) {
      el.show();
      el.addEventListener('sl-after-hide', onClose);
      return () => el.removeEventListener('sl-after-hide', onClose);
    }
  }, []);

  async function handleCreate() {
    setErr('');
    if (!name.trim()) { setErr('El nombre es requerido'); return; }
    let inputs, outputs;
    try { inputs = JSON.parse(inputsRaw); outputs = JSON.parse(outputsRaw); }
    catch { setErr('inputs/outputs deben ser JSON válido, ej: {"x": "int"}'); return; }
    try {
      const flow = await createFlow({ name: name.trim(), version: '1', inputs, outputs, variables: [], events: [], nodes: [] });
      onCreate(flow);
      dialogRef.current?.hide();
    } catch (e) { setErr(e.message); }
  }

  return html`
    <sl-dialog ref=${dialogRef} label="Nuevo flow" style=${{ '--width': '420px' }}>
      <div style=${{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <sl-input
          label="Nombre"
          placeholder="mi_flow"
          value=${name}
          onsl-input=${e => setName(e.target.value)}
          autofocus
        ></sl-input>
        <sl-textarea
          label='Inputs JSON  (ej: {"x":"int"})'
          rows="2"
          value=${inputsRaw}
          onsl-input=${e => setInputsRaw(e.target.value)}
        ></sl-textarea>
        <sl-textarea
          label="Outputs JSON"
          rows="2"
          value=${outputsRaw}
          onsl-input=${e => setOutputsRaw(e.target.value)}
        ></sl-textarea>
        ${err && html`<sl-alert variant="danger" open>${err}</sl-alert>`}
      </div>
      <div slot="footer" style=${{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <sl-button onclick=${() => dialogRef.current?.hide()}>Cancelar</sl-button>
        <sl-button variant="primary" onclick=${handleCreate}>Crear</sl-button>
      </div>
    </sl-dialog>
  `;
}

function DeleteModal({ name, onClose, onConfirm }) {
  const dialogRef = useRef(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (el) {
      el.show();
      el.addEventListener('sl-after-hide', onClose);
      return () => el.removeEventListener('sl-after-hide', onClose);
    }
  }, []);

  return html`
    <sl-dialog ref=${dialogRef} label='¿Borrar "${name}"?'>
      <p style=${{ fontSize: 13, color: 'var(--text-muted)' }}>Esta acción no se puede deshacer.</p>
      <div slot="footer" style=${{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <sl-button onclick=${() => dialogRef.current?.hide()}>Cancelar</sl-button>
        <sl-button variant="danger" onclick=${onConfirm}>Borrar</sl-button>
      </div>
    </sl-dialog>
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

      <sl-select
        value=${activeFlow?.name ?? ''}
        placeholder="— Abrir flow —"
        style=${{ minWidth: 200 }}
        onsl-change=${e => onSelectFlow(e.target.value)}
        size="small"
        clearable
      >
        ${flows.map(f => html`<sl-option key=${f.name} value=${f.name}>${f.name}</sl-option>`)}
      </sl-select>

      <sl-button size="small" onclick=${() => setShowNew(true)}>+ Nuevo</sl-button>
      <div class="header-sep"></div>

      ${activeFlow && html`
        <sl-button size="small" variant="primary" onclick=${onSave} ?disabled=${saving}>
          ${saving ? 'Guardando…' : '💾 Guardar'}
        </sl-button>
        <sl-button size="small" onclick=${onValidate}>✓ Validar</sl-button>
        <sl-button size="small" variant="danger" onclick=${() => setConfirmDelete(true)}>🗑</sl-button>
        <div class="header-sep"></div>
      `}

      <div class="header-spacer"></div>

      ${activeFlow && html`
        <sl-badge variant=${validStatus === 'valid' ? 'success' : validStatus === 'invalid' ? 'danger' : 'neutral'} pill>
          ${validStatus === 'valid' ? '✓ Válido' : validStatus === 'invalid' ? `✗ ${validationErrors.length} error(es)` : '—'}
        </sl-badge>
      `}
      ${!activeFlow && html`<span style=${{ color: 'var(--text-muted)', fontSize: 12 }}>Ningún flow abierto</span>`}
    </header>

    ${showNew && html`<${NewFlowModal} onClose=${() => setShowNew(false)} onCreate=${onFlowCreated} />`}
    ${confirmDelete && html`<${DeleteModal} name=${activeFlow?.name} onClose=${() => setConfirmDelete(false)} onConfirm=${handleDelete} />`}
  `;
}
