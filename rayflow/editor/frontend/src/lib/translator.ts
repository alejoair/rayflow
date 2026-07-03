import type { Node, Edge } from '@xyflow/react'
import type { FlowDef, NodeDef, NodeSpec } from './api'

export function isRef(val: unknown): val is string {
  return typeof val === 'string' && val.includes('.')
}

function parseExecSrc(src: string) {
  const parts = src.split('.')
  return { srcId: parts[0], srcPin: parts.slice(1).join('.') || 'exec_out' }
}

export function parseExecIn(execIn: NodeDef['exec_in']) {
  if (!execIn) return []
  if (typeof execIn === 'string') return [parseExecSrc(execIn)]
  if (Array.isArray(execIn)) return execIn.map(parseExecSrc)
  if (execIn && typeof execIn === 'object' && 'or' in execIn) return execIn.or.map(parseExecSrc)
  return []
}

export function execJoinMode(execIn: NodeDef['exec_in']): 'none' | 'single' | 'and' | 'or' {
  if (!execIn) return 'none'
  if (typeof execIn === 'string') return 'single'
  if (Array.isArray(execIn)) return 'and'
  if (execIn && 'or' in execIn) return 'or'
  return 'none'
}

function autoPos(index: number) {
  const cols = 4
  return { x: 80 + (index % cols) * 220, y: 80 + Math.floor(index / cols) * 180 }
}

export function typeColor(type: string): string {
  const t = (type || 'Any').toLowerCase().split('[')[0]
  const map: Record<string, string> = {
    int: 'var(--type-int)',
    float: 'var(--type-float)',
    str: 'var(--type-str)',
    bool: 'var(--type-bool)',
    list: 'var(--type-list)',
    dict: 'var(--type-dict)',
    any: 'var(--type-any)',
  }
  return map[t] ?? 'var(--type-any)'
}

function buildFlowIOmeta(catalog: Record<string, NodeSpec>, flowDef: FlowDef): Record<string, NodeSpec> {
  const base = { ...catalog }

  const baseMeta = (type: string): NodeSpec => catalog[type] ?? {
    type, decorator: 'engine_node', is_exec_node: true,
    has_exec_in: false, has_exec_out: true, is_parallel: false,
    inputs: [], outputs: [], exec_outputs: ['exec_out'],
  }

  // Entry nodes (OnStart, ChatTrigger, OnEvent, custom @entry_node, ...) are
  // NOT overridden here: they declare their own static Input/Output pins on
  // the class, already reflected verbatim in `catalog`. There's no more
  // flow-level `inputs` field to derive dynamic pins from.

  // FlowOutput: con exec_in, sin exec_out, inputs = outputs del flow
  const foBase = baseMeta('FlowOutput')
  base['FlowOutput'] = {
    ...foBase,
    has_exec_in: true,
    exec_outputs: [],
    inputs: Object.entries(flowDef.outputs || {}).map(([name, type]) => ({
      name, type, kind: 'input' as const, required: false,
    })),
  }

  return base
}

export function flowDefToRF(flowDef: FlowDef, catalog: Record<string, NodeSpec>): { nodes: Node[]; edges: Edge[] } {
  const enrichedCatalog = buildFlowIOmeta(catalog, flowDef)

  const nodes: Node[] = (flowDef.nodes || []).map((n, i) => ({
    id: n.id,
    type: 'rayflowNode',
    position: n.ui ? { x: n.ui.x, y: n.ui.y } : autoPos(i),
    data: {
      nodeType: n.type,
      meta: enrichedCatalog[n.type] ?? null,
      literals: Object.fromEntries(
        Object.entries(n.inputs || {}).filter(([, v]) => !isRef(v))
      ),
    },
    selected: false,
  }))

  const edges: Edge[] = []

  for (const n of flowDef.nodes || []) {
    const srcs = parseExecIn(n.exec_in)
    const mode = execJoinMode(n.exec_in)
    srcs.forEach(({ srcId, srcPin }, idx) => {
      edges.push({
        id: `exec-${srcId}-${srcPin}-${n.id}-${idx}`,
        source: srcId,
        sourceHandle: `exec-out-${srcPin}`,
        target: n.id,
        targetHandle: 'exec-in',
        type: 'exec',
        data: { joinMode: mode },
        animated: false,
      })
    })

    for (const [pin, val] of Object.entries(n.inputs || {})) {
      if (isRef(val)) {
        const dotIdx = (val as string).indexOf('.')
        const srcId = (val as string).slice(0, dotIdx)
        const srcPin = (val as string).slice(dotIdx + 1)
        edges.push({
          id: `data-${srcId}-${srcPin}-${n.id}-${pin}`,
          source: srcId,
          sourceHandle: `data-out-${srcPin}`,
          target: n.id,
          targetHandle: `data-in-${pin}`,
          type: 'default',
        })
      }
    }
  }

  return { nodes, edges }
}

export function rfToFlowDef(rfNodes: Node[], rfEdges: Edge[], flowMeta: Omit<FlowDef, 'nodes'>): FlowDef {
  const execByTarget: Record<string, Edge[]> = {}
  const dataByTarget: Record<string, Edge[]> = {}

  for (const e of rfEdges) {
    if (e.type === 'exec') {
      if (!execByTarget[e.target]) execByTarget[e.target] = []
      execByTarget[e.target].push(e)
    } else {
      if (!dataByTarget[e.target]) dataByTarget[e.target] = []
      dataByTarget[e.target].push(e)
    }
  }

  const nodes: NodeDef[] = rfNodes.map(rn => {
    const execEdges = execByTarget[rn.id] || []
    const dataEdges = dataByTarget[rn.id] || []

    let execIn: NodeDef['exec_in'] = undefined
    if (execEdges.length === 1) {
      const e = execEdges[0]
      const srcPin = (e.sourceHandle || 'exec-out-exec_out').replace('exec-out-', '')
      execIn = srcPin === 'exec_out' ? e.source : `${e.source}.${srcPin}`
    } else if (execEdges.length > 1) {
      const mode = (execEdges[0]?.data as { joinMode?: string })?.joinMode || 'and'
      const refs = execEdges.map(e => {
        const srcPin = (e.sourceHandle || 'exec-out-exec_out').replace('exec-out-', '')
        return srcPin === 'exec_out' ? e.source : `${e.source}.${srcPin}`
      })
      execIn = mode === 'or' ? { or: refs } : refs
    }

    const inputs: Record<string, unknown> = { ...(rn.data as { literals?: Record<string, unknown> }).literals }
    for (const e of dataEdges) {
      const targetPin = (e.targetHandle || '').replace('data-in-', '')
      const srcPin = (e.sourceHandle || '').replace('data-out-', '')
      if (targetPin && srcPin) inputs[targetPin] = `${e.source}.${srcPin}`
    }

    const node: NodeDef = { id: rn.id, type: (rn.data as { nodeType: string }).nodeType }
    if (Object.keys(inputs).length) node.inputs = inputs
    if (execIn !== undefined) node.exec_in = execIn
    node.ui = { x: Math.round(rn.position.x), y: Math.round(rn.position.y) }
    return node
  })

  return { ...flowMeta, nodes }
}
