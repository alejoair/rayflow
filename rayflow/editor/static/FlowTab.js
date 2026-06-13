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

export default function FlowTab({ flowData, catalog, flows, isActive, onDirtyChange, onFlowDeleted, onToast }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [flowDef, setFlowDef] = useState(flowData);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [validationErrors, setValidationErrors] = useState([]);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const initialized = useRef(false);

  // Load flow into canvas on mount (catalog must be ready)
  useEffect(() => {
    if (initialized.current) return;
    const { nodes: rfN, edges: rfE } = flowDefToRF(flowData, catalog);
    setNodes(rfN);
    setEdges(rfE);
    initialized.current = true;
  }, [catalog]);

  // Track dirty state after initial load
  const initializedForDirty = useRef(false);
  useEffect(() => {
    if (!initialized.current) return;
    if (!initializedForDirty.current) { initializedForDirty.current = true; return; }
    onDirtyChange(true);
  }, [nodes, edges]);

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
      onDirtyChange(false);
      onToast('Flow guardado', 'success');
    } catch (e) {
      onToast(`Error guardando: ${e.message}`, 'error');
    } finally {
      setSaving(false);
    }
  }

  async function handleValidate() {
    try {
      const result = await validateFlow(buildFlowDef());
      setValidationErrors(result.errors || []);
      if (result.valid) onToast('Flow válido ✓', 'success');
      else onToast(`${result.errors.length} error(es)`, 'error');
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

  const handleAddNode = useCallback((nodeType, position) => {
    const id = freshId(nodeType);
    setNodes(prev => [...prev, {
      id, type: 'rayflowNode', position,
      data: { nodeType, meta: catalog[nodeType] || null, literals: {} },
    }]);
  }, [catalog]);

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

  const validStatus = validationErrors.length === 0 ? 'valid' : 'invalid';

  return html`
    <div class="flow-tab" style=${{ display: isActive ? 'flex' : 'none' }}>

      <!-- Tab toolbar -->
      <div class="tab-toolbar">
        <span class="tab-toolbar-name">${flowDef.name}</span>
        <div class="tab-toolbar-inputs" style=${{ fontSize: 11, color: 'var(--text-muted)' }}>
          ${Object.entries(flowDef.inputs || {}).map(([k,v]) => html`
            <span key=${k} style=${{ marginRight: 8 }}>${k}: <span style=${{ color: 'var(--type-any)' }}>${v}</span></span>
          `)}
        </div>
        <div style=${{ flex: 1 }}></div>
        ${validationErrors.length > 0 && html`
          <span class="status-badge status-invalid" style=${{ marginRight: 4 }}>✗ ${validationErrors.length} error(es)</span>
        `}
        ${validationErrors.length === 0 && html`
          <span class="status-badge status-valid" style=${{ marginRight: 4, opacity: 0.7 }}>✓</span>
        `}
        <button class="btn btn-sm" onClick=${handleValidate}>Validar</button>
        <button class="btn btn-sm btn-primary" onClick=${handleSave} disabled=${saving}>
          ${saving ? 'Guardando…' : '💾 Guardar'}
        </button>
        <button class="btn btn-sm btn-danger" onClick=${() => setConfirmDelete(true)}>🗑</button>
      </div>

      <!-- Canvas + properties -->
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

      <!-- Run panel -->
      <${RunPanel} activeFlow=${flowDef} validationErrors=${validationErrors} />

      <!-- Delete confirm modal -->
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
