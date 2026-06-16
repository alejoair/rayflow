import htm from 'htm';
import { createElement, useCallback, useRef } from 'react';
const html = htm.bind(createElement);
import {
  ReactFlow, Background, Controls, MiniMap,
  addEdge, BackgroundVariant,
} from '@xyflow/react';
import NodeCard from './NodeCard.js';
import { typeCheck } from './api.js';

const nodeTypes = { rayflowNode: NodeCard };

export default function FlowCanvas({
  nodes, edges, onNodesChange, onEdgesChange,
  catalog, onSelectNode, onAddNode, onConnect: onConnectProp,
  onToast,
}) {
  const wrapperRef = useRef(null);

  const onInit = useCallback(instance => {
    window._rfInstance = instance;
  }, []);

  const onDragOver = useCallback(e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  }, []);

  const onDrop = useCallback(e => {
    e.preventDefault();
    const nodeType = e.dataTransfer.getData('application/rayflow-node');
    if (!nodeType || !window._rfInstance) return;
    const bounds = wrapperRef.current.getBoundingClientRect();
    const pos = window._rfInstance.screenToFlowPosition({
      x: e.clientX - bounds.left,
      y: e.clientY - bounds.top,
    });
    onAddNode(nodeType, pos);
  }, [onAddNode]);

  const onConnect = useCallback(async params => {
    const isExec = (params.sourceHandle || '').startsWith('exec-out-')
      && params.targetHandle === 'exec-in';

    if (isExec) {
      onConnectProp({
        ...params, type: 'exec', animated: true,
        style: { stroke: 'var(--exec-color)', strokeWidth: 2.5 },
        data: { joinMode: 'single' },
      });
      return;
    }

    // data edge — type check
    const srcPin = (params.sourceHandle || '').replace('data-out-', '');
    const tgtPin = (params.targetHandle || '').replace('data-in-', '');
    const srcNode = nodes.find(n => n.id === params.source);
    const tgtNode = nodes.find(n => n.id === params.target);
    const srcMeta = srcNode ? catalog[srcNode.data.nodeType] : null;
    const tgtMeta = tgtNode ? catalog[tgtNode.data.nodeType] : null;
    const fromType = srcMeta?.outputs?.find(p => p.name === srcPin)?.type || 'Any';
    const toType = tgtMeta?.inputs?.find(p => p.name === tgtPin)?.type || 'Any';

    try {
      const result = await typeCheck(fromType, toType);
      if (!result.compatible) {
        onToast(`Incompatible: ${fromType} → ${toType}`, 'error');
        return;
      }
    } catch (err) {
      onToast(`Type-check error: ${err.message}`, 'error');
      return;
    }

    onConnectProp({ ...params, type: 'default' });
  }, [nodes, catalog, onConnectProp, onToast]);

  return html`
    <div class="canvas-wrap" ref=${wrapperRef}>
      ${nodes.length === 0 && html`
        <div class="canvas-empty">
          <div class="canvas-empty-icon">⬡</div>
          <div class="canvas-empty-text">Arrastra nodos desde la paleta</div>
        </div>
      `}
      <${ReactFlow}
        nodes=${nodes}
        edges=${edges}
        onNodesChange=${onNodesChange}
        onEdgesChange=${onEdgesChange}
        onConnect=${onConnect}
        onInit=${onInit}
        onDrop=${onDrop}
        onDragOver=${onDragOver}
        onNodeClick=${(_e, n) => onSelectNode(n.id)}
        onPaneClick=${() => onSelectNode(null)}
        nodeTypes=${nodeTypes}
        fitView
        deleteKeyCode="Delete"
        proOptions=${{ hideAttribution: true }}
      >
        <${Background} variant=${BackgroundVariant.Dots} gap=${20} size=${1} color="var(--border)" />
        <${Controls} />
        <${MiniMap} nodeColor=${'var(--surface2)'} maskColor=${'rgba(0,0,0,0.4)'} />
      </${ReactFlow}>
    </div>
  `;
}
