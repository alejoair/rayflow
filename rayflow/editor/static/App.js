import { html } from 'htm/react';
import { useState, useEffect, useCallback } from 'react';
import { getNodes, getFlows, getFlow, getCustomNodeFile } from './api.js';
import { flowDefToRF, rfToFlowDef } from './translator.js';
import NodePalette from './NodePalette.js';
import FlowManager from './FlowManager.js';
import FlowTab from './FlowTab.js';
import NodeEditorTab from './NodeEditorTab.js';
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
  // tabs: [{id, type:'flow'|'code', label, flowData?, filename?, content?, dirty}]
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

  // ── Flow tabs ──────────────────────────────────────────────────────────────

  async function handleOpenFlow(name) {
    const existing = tabs.find(t => t.type === 'flow' && t.label === name);
    if (existing) { setActiveTabId(existing.id); return; }
    try {
      const flowData = await getFlow(name);
      const id = `tab-${_tabCounter++}`;
      setTabs(prev => [...prev, { id, type: 'flow', label: name, flowData, dirty: false }]);
      setActiveTabId(id);
    } catch (e) { addToast(`Error abriendo: ${e.message}`, 'error'); }
  }

  function handleFlowCreated(flow) {
    setFlows(prev => prev.find(f => f.name === flow.name) ? prev : [
      ...prev, { name: flow.name, version: flow.version, inputs: flow.inputs, outputs: flow.outputs }
    ]);
    handleOpenFlow(flow.name);
  }

  function handleFlowDeleted(name) {
    setFlows(prev => prev.filter(f => f.name !== name));
    const tab = tabs.find(t => t.type === 'flow' && t.label === name);
    if (tab) closeTab(tab.id, true);
    addToast(`Flow "${name}" eliminado`, 'success');
  }

  // ── Code tabs ──────────────────────────────────────────────────────────────

  async function handleOpenFile(filename, content) {
    const existing = tabs.find(t => t.type === 'code' && t.label === filename);
    if (existing) { setActiveTabId(existing.id); return; }

    let fileContent = content;
    if (fileContent === undefined) {
      // Load from server
      try {
        const data = await getCustomNodeFile(filename);
        fileContent = data.content;
      } catch {
        fileContent = null; // will use template
      }
    }

    const id = `tab-${_tabCounter++}`;
    setTabs(prev => [...prev, { id, type: 'code', label: filename, content: fileContent, dirty: false }]);
    setActiveTabId(id);
  }

  function handleFileDeleted(filename) {
    const tab = tabs.find(t => t.type === 'code' && t.label === filename);
    if (tab) closeTab(tab.id, true);
    if (NodePalette._refresh) NodePalette._refresh();
    addToast(`Archivo "${filename}" eliminado`, 'success');
  }

  function handleCatalogReloaded(nodeList) {
    const m = {};
    nodeList.forEach(n => { m[n.type] = n; });
    setCatalog(m);
    if (NodePalette._refresh) NodePalette._refresh();
  }

  // ── Tab management ─────────────────────────────────────────────────────────

  function closeTab(tabId, force = false) {
    const idx = tabs.findIndex(t => t.id === tabId);
    const tab = tabs[idx];
    if (!force && tab?.dirty) {
      if (!confirm(`"${tab.label}" tiene cambios sin guardar. ¿Cerrar de todas formas?`)) return;
    }
    setTabs(prev => {
      const remaining = prev.filter(t => t.id !== tabId);
      if (remaining.length > 0 && activeTabId === tabId) {
        const newIdx = Math.min(idx, remaining.length - 1);
        setActiveTabId(remaining[newIdx].id);
      } else if (remaining.length === 0) {
        setActiveTabId(null);
      }
      return remaining;
    });
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
        onClose=${id => closeTab(id)}
      />

      <div class="app-body">
        <${NodePalette}
          catalog=${catalog}
          onOpenFile=${handleOpenFile}
        />

        <div class="tab-container">
          ${noTabs && html`
            <div class="canvas-empty" style=${{ flex: 1 }}>
              <div class="canvas-empty-icon">⬡</div>
              <div class="canvas-empty-text">Abre un flow o edita nodos custom</div>
            </div>
          `}

          ${tabs.map(tab => tab.type === 'flow'
            ? html`
              <${FlowTab}
                key=${tab.id}
                flowData=${tab.flowData}
                catalog=${catalog}
                flows=${flows}
                isActive=${tab.id === activeTabId}
                onDirtyChange=${dirty => handleTabDirty(tab.id, dirty)}
                onFlowDeleted=${handleFlowDeleted}
                onToast=${addToast}
              />`
            : html`
              <${NodeEditorTab}
                key=${tab.id}
                filename=${tab.label}
                initialContent=${tab.content}
                isActive=${tab.id === activeTabId}
                onDirtyChange=${dirty => handleTabDirty(tab.id, dirty)}
                onFileDeleted=${handleFileDeleted}
                onCatalogReloaded=${handleCatalogReloaded}
                onToast=${addToast}
              />`
          )}
        </div>
      </div>

      <${Toasts} toasts=${toasts} />
    </div>
  `;
}
