import { html } from 'htm/react';
import { useState, useEffect, useCallback } from 'react';
import { useNodesState, useEdgesState, addEdge } from '@xyflow/react';
import { getNodes, getFlows, getFlow, updateFlow, validateFlow } from './api.js';
import { flowDefToRF, rfToFlowDef } from './translator.js';
import NodePalette from './NodePalette.js';
import FlowCanvas from './FlowCanvas.js';
import PropertiesPanel from './PropertiesPanel.js';
import FlowManager from './FlowManager.js';
import RunPanel from './RunPanel.js';

function Toasts({ toasts }) {
  return html`
    <div class="toast-container">
      ${toasts.map(t => html`<div key=${t.id} class=${'toast ' + t.type}>${t.msg}</div>`)}
    </div>
  `;
}

let _nodeCounter = 1;
function freshId(type) { return `${type.toLowerCase()}_${_nodeCounter++}`; }

export default function App() {
  const [catalog, setCatalog] = useState({});
  const [flows, setFlows] = useState([]);
  const [activeFlow, setActiveFlow] = useState(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [validationErrors, setValidationErrors] = useState([]);
  const [saving, setSaving] = useState(false);
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    getNodes()
      .then(list => { const m = {}; list.forEach(n => { m[n.type] = n; }); setCatalog(m); })
      .catch(console.error);
    getFlows()
      .then(data => setFlows(data.flows || []))
      .catch(console.error);
  }, []);

  function addToast(msg, type = 'info') {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, msg, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3500);
  }

  async function handleSelectFlow(name) {
    if (!name) { setActiveFlow(null); setNodes([]); setEdges([]); return; }
    try {
      const data = await getFlow(name);
      setActiveFlow(data);
      const { nodes: rfN, edges: rfE } = flowDefToRF(data, catalog);
      setNodes(rfN);
      setEdges(rfE);
      setSelectedNodeId(null);
      setValidationErrors([]);
    } catch (e) { addToast(`Error abriendo: ${e.message}`, 'error'); }
  }

  function handleFlowCreated(flow) {
    setFlows(prev => [...prev, { name: flow.name, version: flow.version, inputs: flow.inputs, outputs: flow.outputs }]);
    handleSelectFlow(flow.name);
  }

  function handleFlowDeleted(name) {
    setFlows(prev => prev.filter(f => f.name !== name));
    setActiveFlow(null); setNodes([]); setEdges([]); setValidationErrors([]);
  }

  function buildFlowDef() {
    if (!activeFlow) return null;
    return rfToFlowDef(nodes, edges, {
      name: activeFlow.name,
      version: activeFlow.version || '1',
      inputs: activeFlow.inputs || {},
      outputs: activeFlow.outputs || {},
      variables: activeFlow.variables || [],
      events: activeFlow.events || [],
    });
  }

  async function handleSave() {
    if (!activeFlow) return;
    setSaving(true);
    try {
      const flowDef = buildFlowDef();
      await updateFlow(activeFlow.name, flowDef);
      setActiveFlow(prev => ({ ...prev, ...flowDef }));
      addToast('Flow guardado', 'success');
    } catch (e) { addToast(`Error guardando: ${e.message}`, 'error'); }
    finally { setSaving(false); }
  }

  async function handleValidate() {
    if (!activeFlow) return;
    try {
      const result = await validateFlow(buildFlowDef());
      setValidationErrors(result.errors || []);
      if (result.valid) addToast('Flow válido ✓', 'success');
      else addToast(`${result.errors.length} error(es)`, 'error');
    } catch (e) { addToast(`Error validando: ${e.message}`, 'error'); }
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

  return html`
    <div id="root">
      <${FlowManager}
        flows=${flows}
        activeFlow=${activeFlow}
        onSelectFlow=${handleSelectFlow}
        onFlowCreated=${handleFlowCreated}
        onFlowDeleted=${handleFlowDeleted}
        onSave=${handleSave}
        onValidate=${handleValidate}
        validationErrors=${validationErrors}
        saving=${saving}
      />
      <div class="app-body">
        <${NodePalette} catalog=${catalog} />
        <${FlowCanvas}
          nodes=${nodes}
          edges=${edges}
          onNodesChange=${onNodesChange}
          onEdgesChange=${onEdgesChange}
          catalog=${catalog}
          onSelectNode=${setSelectedNodeId}
          onAddNode=${handleAddNode}
          onConnect=${handleConnect}
          onToast=${addToast}
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
      <${RunPanel} activeFlow=${activeFlow} validationErrors=${validationErrors} />
      <${Toasts} toasts=${toasts} />
    </div>
  `;
}
