import { useCallback, useRef } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap,
  addEdge, BackgroundVariant,
  type Connection, type NodeTypes,
} from '@xyflow/react'
import { useFlowStore } from '@/store/flowStore'
import { typeCheck } from '@/lib/api'
import NodeCard from './NodeCard'

let nodeCounter = 1
function freshId(type: string) { return `${type.toLowerCase()}_${nodeCounter++}` }

const nodeTypes: NodeTypes = { rayflowNode: NodeCard as never }

interface Props {
  onSelectNode: (id: string | null) => void
  onToast: (msg: string, type?: 'info' | 'success' | 'error') => void
}

export default function FlowCanvas({ onSelectNode, onToast }: Props) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const tab = useFlowStore(s => s.getActiveTab())
  const catalog = useFlowStore(s => s.catalog)
  const { onNodesChange, onEdgesChange, setEdges, setNodes } = useFlowStore()

  const activeRun = tab?.runs.find(r => r.runId === tab.activeRunId)

  const onInit = useCallback((instance: { screenToFlowPosition: (p: { x: number; y: number }) => { x: number; y: number } }) => {
    ;(window as unknown as Record<string, unknown>)._rfInstance = instance
  }, [])

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const nodeType = e.dataTransfer.getData('application/rayflow-node')
    const rfInstance = (window as unknown as Record<string, unknown>)._rfInstance as { screenToFlowPosition: (p: { x: number; y: number }) => { x: number; y: number } } | undefined
    if (!nodeType || !rfInstance || !wrapperRef.current) return
    const bounds = wrapperRef.current.getBoundingClientRect()
    const pos = rfInstance.screenToFlowPosition({ x: e.clientX - bounds.left, y: e.clientY - bounds.top })
    const id = freshId(nodeType)
    setNodes([...(tab?.nodes ?? []), {
      id, type: 'rayflowNode', position: pos,
      data: { nodeType, meta: catalog[nodeType] ?? null, literals: {} },
      selected: false,
    }])
  }, [tab, catalog, setNodes])

  const onConnect = useCallback(async (params: Connection) => {
    const isExec = (params.sourceHandle || '').startsWith('exec-out-') && params.targetHandle === 'exec-in'

    if (isExec) {
      const execEdge = {
        ...params,
        id: `${params.source}-${params.sourceHandle}-${params.target}`,
        type: 'exec',
        animated: true,
        style: { stroke: 'var(--exec-color)', strokeWidth: 2.5 },
        data: { joinMode: 'single' },
      }
      setEdges(addEdge(execEdge as Parameters<typeof addEdge>[0], tab?.edges ?? []))
      return
    }

    const srcPin = (params.sourceHandle || '').replace('data-out-', '')
    const tgtPin = (params.targetHandle || '').replace('data-in-', '')
    const srcNode = tab?.nodes.find(n => n.id === params.source)
    const tgtNode = tab?.nodes.find(n => n.id === params.target)
    const srcMeta = srcNode ? catalog[(srcNode.data as { nodeType: string }).nodeType] : null
    const tgtMeta = tgtNode ? catalog[(tgtNode.data as { nodeType: string }).nodeType] : null
    const fromType = srcMeta?.outputs?.find(p => p.name === srcPin)?.type || 'Any'
    const toType = tgtMeta?.inputs?.find(p => p.name === tgtPin)?.type || 'Any'

    try {
      const result = await typeCheck(fromType, toType)
      if (!result.compatible) {
        onToast(`Incompatible: ${fromType} → ${toType}`, 'error')
        return
      }
    } catch {
      onToast('Error verificando tipos', 'error')
      return
    }

    setEdges(addEdge({ ...params, type: 'default' }, tab?.edges ?? []))
  }, [tab, catalog, setEdges, onToast])

  if (!tab) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[var(--background)] text-[var(--muted-foreground)]">
        <div className="text-center">
          <div className="text-5xl opacity-20 mb-3">⬡</div>
          <div className="text-sm">Abre o crea un flow para empezar</div>
        </div>
      </div>
    )
  }

  // Aplicar estilos de run activo a nodos y edges
  const nodes = tab.nodes.map(n => {
    if (!activeRun) return n
    const runStatus = activeRun.activeNodes.has(n.id) ? 'running'
      : activeRun.doneNodes.has(n.id) ? 'done' : 'idle'
    return { ...n, data: { ...n.data, runStatus } }
  })

  const edges = tab.edges.map(e => {
    if (!activeRun) return e
    const key = `${e.source}-${e.target}`
    const isActive = activeRun.activeEdges.has(key)
    return isActive
      ? { ...e, animated: true, style: { ...e.style, stroke: 'var(--exec-color)', strokeWidth: 3 } }
      : e
  })

  return (
    <div className="flex-1 relative" ref={wrapperRef}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onInit={onInit as never}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onNodeClick={(_e, n) => onSelectNode(n.id)}
        onPaneClick={() => onSelectNode(null)}
        nodeTypes={nodeTypes}
        fitView
        deleteKeyCode="Delete"
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--border)" />
        <Controls />
        <MiniMap nodeColor="var(--secondary)" maskColor="rgba(0,0,0,0.4)" />
      </ReactFlow>
    </div>
  )
}
