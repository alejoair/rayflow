import { html } from 'htm/react';
import { useState, useEffect, useCallback } from 'react';
import { getNodes, getFlows, getFlow } from './api.js';
import NodePalette from './NodePalette.js';
import FlowManager from './FlowManager.js';
import FlowTab from './FlowTab.js';
import TabBar from './TabBar.js';

function Toasts({ toasts }) {
  return html`
    <div class="toast-container">
      ${toasts.map(t => html`<div key=${t.id} class=${'toast ' + t.type}>${t.msg}</div>`)}
    </div>
  `;
}

let _tabCounter = 1;

export default function App() {
  const [catalog, setCatalog] = useState({});
  const [flows, setFlows] = useState([]);
  // tabs: [{id, flowName, flowData, dirty}]
  const [tabs, setTabs] = useState([]);
  const [activeTabId, setActiveTabId] = useState(null);
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

  async function handleOpenFlow(name) {
    // If already open, just activate that tab
    const existing = tabs.find(t => t.flowName === name);
    if (existing) { setActiveTabId(existing.id); return; }

    try {
      const flowData = await getFlow(name);
      const id = `tab-${_tabCounter++}`;
      setTabs(prev => [...prev, { id, flowName: name, flowData, dirty: false }]);
      setActiveTabId(id);
    } catch (e) {
      addToast(`Error abriendo: ${e.message}`, 'error');
    }
  }

  function handleFlowCreated(flow) {
    setFlows(prev => {
      if (prev.find(f => f.name === flow.name)) return prev;
      return [...prev, { name: flow.name, version: flow.version, inputs: flow.inputs, outputs: flow.outputs }];
    });
    handleOpenFlow(flow.name);
  }

  function handleCloseTab(tabId) {
    const idx = tabs.findIndex(t => t.id === tabId);
    const tab = tabs[idx];
    if (tab?.dirty) {
      if (!confirm(`"${tab.flowName}" tiene cambios sin guardar. ¿Cerrar de todas formas?`)) return;
    }
    setTabs(prev => prev.filter(t => t.id !== tabId));
    setActiveTabId(prev => {
      if (prev !== tabId) return prev;
      // Activate neighbour tab
      const remaining = tabs.filter(t => t.id !== tabId);
      if (!remaining.length) return null;
      const newIdx = Math.min(idx, remaining.length - 1);
      return remaining[newIdx].id;
    });
  }

  function handleFlowDeleted(name) {
    setFlows(prev => prev.filter(f => f.name !== name));
    const tab = tabs.find(t => t.flowName === name);
    if (tab) handleCloseTab(tab.id);
    addToast(`Flow "${name}" eliminado`, 'success');
  }

  function handleTabDirty(tabId, dirty) {
    setTabs(prev => prev.map(t => t.id === tabId ? { ...t, dirty } : t));
  }

  const noTabs = tabs.length === 0;

  return html`
    <div id="root">
      <${FlowManager}
        flows=${flows}
        onOpenFlow=${handleOpenFlow}
        onFlowCreated=${handleFlowCreated}
      />

      <${TabBar}
        tabs=${tabs}
        activeTabId=${activeTabId}
        onActivate=${setActiveTabId}
        onClose=${handleCloseTab}
      />

      <div class="app-body">
        <${NodePalette} catalog=${catalog} />

        <div class="tab-container">
          ${noTabs && html`
            <div class="canvas-empty" style=${{ flex: 1 }}>
              <div class="canvas-empty-icon">⬡</div>
              <div class="canvas-empty-text">Abre un flow para empezar</div>
            </div>
          `}
          ${tabs.map(tab => html`
            <${FlowTab}
              key=${tab.id}
              flowData=${tab.flowData}
              catalog=${catalog}
              flows=${flows}
              isActive=${tab.id === activeTabId}
              onDirtyChange=${dirty => handleTabDirty(tab.id, dirty)}
              onFlowDeleted=${handleFlowDeleted}
              onToast=${addToast}
            />
          `)}
        </div>
      </div>

      <${Toasts} toasts=${toasts} />
    </div>
  `;
}
