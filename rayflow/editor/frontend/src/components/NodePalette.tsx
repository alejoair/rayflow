import { useState, useMemo } from 'react'
import type { CSSProperties } from 'react'
import { Input } from '@/components/ui/input'
import type { NodeSpec } from '@/lib/api'

const BUILTIN_TYPES = new Set([
  'OnStart','FlowOutput','Branch','Sequence','Parallel','ForEach','Map',
  'Get','Set','CallFlow','OnEvent','EmitEvent',
  'Add','GreaterThan','ToInt','ToFloat','ToStr','ToBool',
])

interface Props {
  catalog: Record<string, NodeSpec>
}

const itemStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  padding: '10px 12px',
  borderRadius: 8,
  cursor: 'grab',
  border: '1px solid transparent',
  userSelect: 'none',
  marginBottom: 6,
}

const badgeBase: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  borderRadius: 5,
  padding: '2px 8px',
  fontSize: 11,
  fontWeight: 500,
  lineHeight: '18px',
}

function NodeItem({ node, onDragStart }: { node: NodeSpec; onDragStart: (e: React.DragEvent, type: string) => void }) {
  const [hovered, setHovered] = useState(false)
  const decoratorColor = node.decorator === 'ray_node'
    ? { bg: '#052e16', text: '#6ee7b7' }
    : node.decorator === 'parallel_node'
    ? { bg: '#2d1b69', text: '#c4b5fd' }
    : { bg: '#1e1b4b', text: '#a5b4fc' }

  return (
    <div
      style={{
        ...itemStyle,
        background: hovered ? 'var(--secondary)' : 'transparent',
        borderColor: hovered ? 'var(--border)' : 'transparent',
      }}
      draggable
      onDragStart={e => onDragStart(e, node.type)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      title="Arrastra al canvas"
    >
      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--foreground)', lineHeight: 1.3 }}>
        {node.type}
      </span>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <span style={{ ...badgeBase, border: '1px solid var(--border)', color: 'var(--muted-foreground)' }}>
          {node.is_exec_node ? 'exec' : 'pure'}
        </span>
        <span style={{ ...badgeBase, background: decoratorColor.bg, color: decoratorColor.text }}>
          {node.decorator.replace('_node', '')}
        </span>
      </div>
    </div>
  )
}

function Section({ label, nodes, onDragStart }: { label: string; nodes: NodeSpec[]; onDragStart: (e: React.DragEvent, type: string) => void }) {
  const [open, setOpen] = useState(true)

  return (
    <div>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 12px 6px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--muted-foreground)',
          textTransform: 'uppercase',
          letterSpacing: '0.07em',
        }}
      >
        <span>{label}</span>
        <span style={{ fontSize: 10, transition: 'transform 0.15s', display: 'inline-block', transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▾</span>
      </button>
      {open && nodes.map(n => <NodeItem key={n.type} node={n} onDragStart={onDragStart} />)}
    </div>
  )
}

export default function NodePalette({ catalog }: Props) {
  const [open, setOpen] = useState(true)
  const [search, setSearch] = useState('')

  const { builtin, custom } = useMemo(() => {
    const q = search.toLowerCase()
    const all = Object.values(catalog).filter(n => !q || n.type.toLowerCase().includes(q))
    return {
      builtin: all.filter(n => BUILTIN_TYPES.has(n.type)),
      custom: all.filter(n => !BUILTIN_TYPES.has(n.type)),
    }
  }, [catalog, search])

  function onDragStart(e: React.DragEvent, nodeType: string) {
    e.dataTransfer.setData('application/rayflow-node', nodeType)
    e.dataTransfer.effectAllowed = 'copy'
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      flex: open ? 1 : 0,
      overflow: 'hidden',
      minHeight: 0,
      flexShrink: open ? 1 : 0,
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 12px 10px 16px',
          background: 'none',
          border: 'none',
          borderBottom: open ? '1px solid var(--border)' : 'none',
          cursor: 'pointer',
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--muted-foreground)',
          textTransform: 'uppercase',
          letterSpacing: '0.07em',
          flexShrink: 0,
        }}
      >
        <span>Nodos</span>
        <span style={{ fontSize: 10, transition: 'transform 0.15s', display: 'inline-block', transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▾</span>
      </button>
      {open && (
        <>
          <div style={{ padding: '10px 12px', flexShrink: 0 }}>
            <Input
              placeholder="Buscar..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ height: 32, fontSize: 13 }}
              className="bg-[var(--secondary)] border-[var(--border)] text-[var(--foreground)]"
            />
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '0 4px 16px' }}>
            {builtin.length === 0 && custom.length === 0 && (
              <div style={{ textAlign: 'center', color: 'var(--muted-foreground)', fontSize: 13, padding: '24px 0' }}>
                Sin resultados
              </div>
            )}
            {builtin.length > 0 && (
              <Section label="Builtin" nodes={builtin} onDragStart={onDragStart} />
            )}
            {custom.length > 0 && (
              <Section label="Custom" nodes={custom} onDragStart={onDragStart} />
            )}
          </div>
        </>
      )}
    </div>
  )
}
