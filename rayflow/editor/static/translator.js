// FlowDef (JSON) ↔ React Flow nodes/edges

export function isRef(val) {
  return typeof val === 'string' && val.includes('.');
}

// Parse "node_id" or "node_id.pin" → {srcId, srcPin}
function parseExecSrc(src) {
  const parts = src.split('.');
  return { srcId: parts[0], srcPin: parts.slice(1).join('.') || 'exec_out' };
}

// exec_in value → array of {srcId, srcPin}
export function parseExecIn(execIn) {
  if (!execIn) return [];
  if (typeof execIn === 'string') {
    return [parseExecSrc(execIn)];
  }
  if (Array.isArray(execIn)) {
    return execIn.map(parseExecSrc);
  }
  if (execIn && typeof execIn === 'object' && execIn.or) {
    return execIn.or.map(parseExecSrc);
  }
  return [];
}

// Detect exec_in join mode
export function execJoinMode(execIn) {
  if (!execIn) return 'none';
  if (typeof execIn === 'string') return 'single';
  if (Array.isArray(execIn)) return 'and';
  if (execIn && execIn.or) return 'or';
  return 'none';
}

// Auto-layout: simple left-to-right grid for nodes without ui positions
function autoPos(index) {
  const cols = 4;
  const col = index % cols;
  const row = Math.floor(index / cols);
  return { x: 80 + col * 220, y: 80 + row * 180 };
}

export function flowDefToRF(flowDef, catalog) {
  const nodes = (flowDef.nodes || []).map((n, i) => ({
    id: n.id,
    type: 'rayflowNode',
    position: n.ui ? { x: n.ui.x ?? 0, y: n.ui.y ?? 0 } : autoPos(i),
    data: {
      nodeType: n.type,
      meta: catalog[n.type] || null,
      // literal inputs (not refs to other nodes)
      literals: Object.fromEntries(
        Object.entries(n.inputs || {}).filter(([, v]) => !isRef(v))
      ),
    },
    selected: false,
  }));

  const edges = [];

  (flowDef.nodes || []).forEach(n => {
    // exec edges
    const srcs = parseExecIn(n.exec_in);
    const mode = execJoinMode(n.exec_in);
    srcs.forEach(({ srcId, srcPin }, idx) => {
      edges.push({
        id: `exec-${srcId}-${srcPin}-${n.id}-${idx}`,
        source: srcId,
        sourceHandle: `exec-out-${srcPin}`,
        target: n.id,
        targetHandle: 'exec-in',
        type: 'exec',
        data: { joinMode: mode },
        style: { stroke: 'var(--exec-color)', strokeWidth: 2.5 },
        animated: true,
      });
    });

    // data edges
    Object.entries(n.inputs || {}).forEach(([pin, val]) => {
      if (isRef(val)) {
        const dotIdx = val.indexOf('.');
        const srcId = val.slice(0, dotIdx);
        const srcPin = val.slice(dotIdx + 1);
        edges.push({
          id: `data-${srcId}-${srcPin}-${n.id}-${pin}`,
          source: srcId,
          sourceHandle: `data-out-${srcPin}`,
          target: n.id,
          targetHandle: `data-in-${pin}`,
          type: 'default',
        });
      }
    });
  });

  return { nodes, edges };
}

export function rfToFlowDef(rfNodes, rfEdges, flowMeta) {
  // Build lookup: target node → incoming edges
  const execEdgesByTarget = {};
  const dataEdgesByTarget = {};

  rfEdges.forEach(e => {
    if (e.type === 'exec') {
      if (!execEdgesByTarget[e.target]) execEdgesByTarget[e.target] = [];
      execEdgesByTarget[e.target].push(e);
    } else {
      if (!dataEdgesByTarget[e.target]) dataEdgesByTarget[e.target] = [];
      dataEdgesByTarget[e.target].push(e);
    }
  });

  const nodes = rfNodes.map(rn => {
    const execEdges = execEdgesByTarget[rn.id] || [];
    const dataEdges = dataEdgesByTarget[rn.id] || [];

    // Build exec_in
    let execIn = null;
    if (execEdges.length === 1) {
      const e = execEdges[0];
      const srcPin = (e.sourceHandle || 'exec-out-exec_out').replace('exec-out-', '');
      execIn = srcPin === 'exec_out' ? e.source : `${e.source}.${srcPin}`;
    } else if (execEdges.length > 1) {
      const mode = execEdges[0]?.data?.joinMode || 'and';
      const refs = execEdges.map(e => {
        const srcPin = (e.sourceHandle || 'exec-out-exec_out').replace('exec-out-', '');
        return srcPin === 'exec_out' ? e.source : `${e.source}.${srcPin}`;
      });
      execIn = mode === 'or' ? { or: refs } : refs;
    }

    // Build inputs: literals + data refs
    const inputs = { ...rn.data.literals };
    dataEdges.forEach(e => {
      const targetPin = (e.targetHandle || '').replace('data-in-', '');
      const srcPin = (e.sourceHandle || '').replace('data-out-', '');
      if (targetPin && srcPin) {
        inputs[targetPin] = `${e.source}.${srcPin}`;
      }
    });

    const node = { id: rn.id, type: rn.data.nodeType };
    if (Object.keys(inputs).length) node.inputs = inputs;
    if (execIn !== null) node.exec_in = execIn;
    node.ui = { x: Math.round(rn.position.x), y: Math.round(rn.position.y) };
    return node;
  });

  return { ...flowMeta, nodes };
}

// Map pin type string to CSS variable
export function typeColor(type) {
  const t = (type || 'Any').toLowerCase().split('[')[0];
  const map = {
    int: 'var(--type-int)',
    float: 'var(--type-float)',
    str: 'var(--type-str)',
    bool: 'var(--type-bool)',
    list: 'var(--type-list)',
    dict: 'var(--type-dict)',
    any: 'var(--type-any)',
  };
  return map[t] || 'var(--type-any)';
}
