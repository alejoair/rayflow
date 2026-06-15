import { html } from 'htm/react';
import { useState, useEffect, useCallback, useRef } from 'react';
import { useNodesState, useEdgesState, addEdge } from '@xyflow/react';
import { updateFlow, validateFlow, deleteFlow } from './api.js';
import { flowDefToRF, rfToFlowDef } from './translator.js';
import FlowCanvas from './FlowCanvas.js';
import PropertiesPanel from './PropertiesPanel.js';
import RunPanel from './RunPanel.js';

let _counter = 1;
function freshId(type) { return `${type.toLowerCase()}_${_counter++}`; }

// ── Interface editor modal ─────────────────────────────────────────────────
function InterfaceModal({ flowDef, onSave, onClose }) {
  const [name, setName] = useState(flowDef.name);
  const [inputsRaw, setInputsRaw] = useState(JSON.stringify(flowDef.inputs || {}, null, 2));
  const [outputsRaw, setOutputsRaw] = useState(JSON.stringify(flowDef.outputs || {}, null, 2));
  const [err, setErr] = useState('');

  function handleSave() {
    setErr('');
    if (!name.trim()) { setErr('El nombre es requerido'); return; }
    let inputs, outputs;
    try { inputs = JSON.parse(inputsRaw); outputs = JSON.parse(outputsRaw); }
    catch { setErr('JSON inválido — ej: {"x": "int"}'); return; }
    onSave({ name: name.trim(), inputs, outputs });
    onClose();
  }

  return html`
    <div class="modal-overlay" onClick=${e => e.target === e.currentTarget && onClose()}>
      <div class="modal">
        <div class="modal-title">Interfaz del flow</div>
        <div class="prop-field">
          <label style=${{ display:'block', marginBottom:3, fontSize:12 }}>Nombre</label>
          <input class="prop-input" value=${name} onInput=${e => setName(e.target.value)} />
        </div>
        <div class="prop-field">
          <label style=${{ display:'block', marginBottom:3, fontSize:12 }}>Inputs <span style=${{ color:'var(--text-muted)' }}>{"nombre":"tipo"}</span></label>
          <textarea class="prop-input textarea" style=${{ height:80 }} value=${inputsRaw} onInput=${e => setInputsRaw(e.target.value)} />
        </div>
        <div class="prop-field">
          <label style=${{ display:'block', marginBottom:3, fontSize:12 }}>Outputs <span style=${{ color:'var(--text-muted)' }}>{"nombre":"tipo"}</span></label>
          <textarea class="prop-input textarea" style=${{ height:80 }} value=${outputsRaw} onInput=${e => setOutputsRaw(e.target.value)} />
        </div>
        ${err && html`<div style=${{ color:'var(--error-color)', fontSize:12, marginTop:4 }}>${err}</div>`}
        <div class="modal-footer">
          <button class="btn" onClick=${onClose}>Cancelar</button>
          <button class="btn btn-primary" onClick=${handleSave}>Guardar</button>
        </div>
      </div>
    </div>
  `;
}

// ── Variables editor modal ─────────────────────────────────────────────────
const TYPE_OPTIONS = ['int','float','str','bool','list','dict','Any'];

function VariablesModal({ variables, onSave, onClose }) {
  const [vars, setVars] = useState(variables.map(v => ({ ...v })));

  function addVar() {
    setVars(prev => [...prev, { name: '', type: 'str', default: null }]);
  }
  function updateVar(idx, field, val) {
    setVars(prev => prev.map((v, i) => i === idx ? { ...v, [field]: val } : v));
  }
  function removeVar(idx) {
    setVars(prev => prev.filter((_, i) => i !== idx));
  }

  return html`
    <div class="modal-overlay" onClick=${e => e.target === e.currentTarget && onClose()}>
      <div class="modal" style=${{ minWidth: 480 }}>
        <div class="modal-title">Variables del flow</div>

        <div style=${{ marginBottom: 8 }}>
          <div class="var-row var-row-header">
            <span>Nombre</span><span>Tipo</span><span>Default</span><span></span>
          </div>
          ${vars.map((v, i) => html`
            <div key=${i} class="var-row">
              <input class="prop-input" style=${{ width: '100%' }} value=${v.name}
                onInput=${e => updateVar(i, 'name', e.target.value)} placeholder="nombre" />
              <select class="prop-input" value=${v.type} onChange=${e => updateVar(i, 'type', e.target.value)}>
                ${TYPE_OPTIONS.map(t => html`<option key=${t} value=${t}>${t}</option>`)}
              </select>
              <input class="prop-input" style=${{ width: '100%' }}
                value=${v.default == null ? '' : String(v.default)}
                onInput=${e => {
                  const raw = e.target.value;
                  let val;
                  try { val = JSON.parse(raw); } catch { val = raw || null; }
                  updateVar(i, 'default', val);
                }} placeholder="default" />
              <button class="btn btn-sm btn-danger" onClick=${() => removeVar(i)}>×</button>
            </div>
          `)}
        </div>

        <button class="btn btn-sm" onClick=${addVar}>+ Añadir variable</button>
        <div class="modal-footer">
          <button class="btn" onClick=${onClose}>Cancelar</button>
          <button class="btn btn-primary" onClick=${() => { onSave(vars.filter(v => v.name)); onClose(); }}>
            Guardar
          </button>
        </div>
      </div>
    </div>
  `;
}

// ── Main FlowTab ───────────────────────────────────────────────────────────
export default function FlowTab({ flowData, catalog, flows, isActive, onDirtyChange, onFlowDeleted, onToast }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [flowDef, setFlowDef] = useState(flowData);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [validationErrors, setValidationErrors] = useState([]);
  const [saving, setSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [showInterface, setShowInterface] = useState(false);
  const [showVariables, setShowVariables] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const initialized = useRef(false);
  const initializedForDirty = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    const { nodes: rfN, edges: rfE } = flowDefToRF(flowData, catalog);
    setNodes(rfN);
    setEdges(rfE);
    initialized.current = true;
  }, [catalog]);

  useEffect(() => {
    if (!initialized.current) return;
    if (!initializedForDirty.current) { initializedForDirty.current = true; return; }
    markDirty();
  }, [nodes, edges]);

  function markDirty() { setIsDirty(true); onDirtyChange(true); }
  function markClean() { setIsDirty(false); onDirtyChange(false); }

  function buildFlowDef() {
    return rfToFlowDef(nodes, edges, {
      name: flowDef.name,
      version: flowDef.version || '1',
      inputs: flowDef.inputs || {},
      outputs: flowDef.outputs || {},
      variables: flowDef.variables || [],
      events: flowDef.events || [],
    });
  }

  async function handleSave() {
    setSaving(true);
    try {
      const fd = buildFlowDef();
      await updateFlow(flowDef.name, fd);
      setFlowDef(prev => ({ ...prev, ...fd }));
      markClean();
      onToast('Flow guardado', 'success');
      return true;
    } catch (e) {
      onToast(`Error guardando: ${e.message}`, 'error');
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function handleValidate() {
    try {
      const result = await validateFlow(buildFlowDef());
      const errors = result.errors || [];
      setValidationErrors(errors);

      // Highlight nodes with errors
      const errSet = new Set();
      nodes.forEach(n => {
        if (errors.some(e => e.includes(n.id) || e.includes(`'${n.id}'`))) errSet.add(n.id);
      });
      setNodes(prev => prev.map(n => ({
        ...n,
        data: { ...n.data, hasError: errSet.has(n.id) },
      })));

      if (result.valid) onToast('Flow válido ✓', 'success');
      else onToast(`${errors.length} error(es)`, 'error');
    } catch (e) {
      onToast(`Error validando: ${e.message}`, 'error');
    }
  }

  async function handleDelete() {
    try {
      await deleteFlow(flowDef.name);
      onFlowDeleted(flowDef.name);
    } catch (e) {
      onToast(`Error borrando: ${e.message}`, 'error');
    }
  }

  function handleInterfaceSave({ name, inputs, outputs }) {
    setFlowDef(prev => ({ ...prev, name, inputs, outputs }));
    // Update dynamic pins on FlowInput/FlowOutput nodes
    setNodes(prev => prev.map(n => {
      if (n.data.nodeType === 'FlowInput' || n.data.nodeType === 'OnStart') {
        return { ...n, data: { ...n.data, dynamicOutputs: Object.entries(inputs) } };
      }
      if (n.data.nodeType === 'FlowOutput') {
        return { ...n, data: { ...n.data, dynamicInputs: Object.entries(outputs) } };
      }
      return n;
    }));
    markDirty();
  }

  function handleVariablesSave(vars) {
    setFlowDef(prev => ({ ...prev, variables: vars }));
    markDirty();
  }

  const handleAddNode = useCallback((nodeType, position) => {
    const id = freshId(nodeType);
    const extra = {};
    if (nodeType === 'FlowInput' || nodeType === 'OnStart') extra.dynamicOutputs = Object.entries(flowDef.inputs || {});
    if (nodeType === 'FlowOutput') extra.dynamicInputs = Object.entries(flowDef.outputs || {});
    setNodes(prev => [...prev, {
      id, type: 'rayflowNode', position,
      data: { nodeType, meta: catalog[nodeType] || null, literals: {}, ...extra },
    }]);
  }, [catalog, flowDef]);

  const handleConnect = useCallback(params => {
    setEdges(prev => addEdge(params, prev));
  }, []);

  function handleUpdateNode(nodeId, update) {
    if (update.newId) {
      const newId = update.newId;
      setNodes(prev => prev.map(n => n.id === nodeId ? { ...n, id: newId } : n));
      setEdges(prev => prev.map(e => ({
        ...e,
        source: e.source === nodeId ? newId : e.source,
        target: e.target === nodeId ? newId : e.target,
        id: e.id.replace(new RegExp(`\\b${nodeId}\\b`), newId),
      })));
      setSelectedNodeId(newId);
      return;
    }
    setNodes(prev => prev.map(n => n.id === nodeId ? { ...n, data: { ...n.data, ...update } } : n));
  }

  return html`
    <div class="flow-tab" style=${{ display: isActive ? 'flex' : 'none' }}>

      <div class="tab-toolbar">
        <span class="tab-toolbar-name">${flowDef.name}</span>
        <div class="tab-toolbar-inputs">
          ${Object.entries(flowDef.inputs || {}).map(([k,v]) => html`
            <span key=${k} style=${{ marginRight: 8, fontSize: 11, color: 'var(--text-muted)' }}>
              ${k}<span style=${{ color: 'var(--type-any)' }}>:${v}</span>
            </span>
          `)}
        </div>
        <div style=${{ flex: 1 }} />
        ${validationErrors.length > 0 && html`
          <span class="status-badge status-invalid" style=${{ marginRight: 4 }}>✗ ${validationErrors.length} error(es)</span>
        `}
        <button class="btn btn-sm" onClick=${() => setShowInterface(true)} title="Editar nombre, inputs y outputs">✏ Interfaz</button>
        <button class="btn btn-sm" onClick=${() => setShowVariables(true)} title="Editar variables del flow">
          📋 Vars ${flowDef.variables?.length > 0 ? html`<span style=${{ color:'var(--accent)', marginLeft:2 }}>(${flowDef.variables.length})</span>` : ''}
        </button>
        <button class="btn btn-sm" onClick=${handleValidate}>✓ Validar</button>
        <button class="btn btn-sm btn-primary" onClick=${handleSave} disabled=${saving}>${saving ? 'Guardando…' : '💾 Guardar'}</button>
        <button class="btn btn-sm btn-danger" onClick=${() => setConfirmDelete(true)}>🗑</button>
      </div>

      <div class="tab-body">
        <${FlowCanvas}
          nodes=${nodes}
          edges=${edges}
          onNodesChange=${onNodesChange}
          onEdgesChange=${onEdgesChange}
          catalog=${catalog}
          onSelectNode=${setSelectedNodeId}
          onAddNode=${handleAddNode}
          onConnect=${handleConnect}
          onToast=${onToast}
        />
        <${PropertiesPanel}
          selectedNodeId=${selectedNodeId}
          nodes=${nodes}
          edges=${edges}
          catalog=${catalog}
          flowList=${flows}
          onUpdateNode=${handleUpdateNode}
          validationErrors=${validationErrors}
        />
      </div>

      <${RunPanel}
        activeFlow=${flowDef}
        validationErrors=${validationErrors}
        isDirty=${isDirty}
        onSaveFirst=${handleSave}
      />

      ${showInterface && html`
        <${InterfaceModal}
          flowDef=${flowDef}
          onSave=${handleInterfaceSave}
          onClose=${() => setShowInterface(false)}
        />
      `}

      ${showVariables && html`
        <${VariablesModal}
          variables=${flowDef.variables || []}
          onSave=${handleVariablesSave}
          onClose=${() => setShowVariables(false)}
        />
      `}

      ${confirmDelete && html`
        <div class="modal-overlay" onClick=${e => e.target===e.currentTarget && setConfirmDelete(false)}>
          <div class="modal">
            <div class="modal-title">¿Borrar "${flowDef.name}"?</div>
            <p style=${{ fontSize:13, color:'var(--text-muted)', marginTop:8 }}>Esta acción no se puede deshacer.</p>
            <div class="modal-footer">
              <button class="btn" onClick=${() => setConfirmDelete(false)}>Cancelar</button>
              <button class="btn btn-danger" onClick=${handleDelete}>Borrar</button>
            </div>
          </div>
        </div>
      `}
    </div>
  `;
}
