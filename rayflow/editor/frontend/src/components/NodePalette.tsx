import { useState, useMemo } from 'react'
import type { CSSProperties } from 'react'
import { Input } from '@/components/ui/input'
import type { NodeSpec } from '@/lib/api'

interface Props {
  catalog: Record<string, NodeSpec>
}

// Función para agrupar nodos por categoría
function groupByCategory(nodes: NodeSpec[]): Record<string, NodeSpec[]> {
  const groups: Record<string, NodeSpec[]> = {}
  for (const node of nodes) {
    const cat = node.category || 'General'
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(node)
  }
  return groups
}

// Genera color consistente basado en el nombre de la categoría
function getCategoryColor(category: string): string {
  // Paleta de colores base HSL más distintivos
  const baseHues = [0, 45, 90, 135, 180, 225, 270, 315]

  // Generar un hash simple del nombre de la categoría
  let hash = 0
  for (let i = 0; i < category.length; i++) {
    hash = category.charCodeAt(i) + ((hash << 5) - hash)
  }

  // Usar el hash para seleccionar un tono base y variación
  const hueIndex = Math.abs(hash) % baseHues.length
  const hue = baseHues[hueIndex]
  const saturation = 70 + (Math.abs(hash >> 8) % 25) // 70-95% (más saturado)
  const lightness = 70 + (Math.abs(hash >> 16) % 15) // 70-85% (más visible)

  return `hsla(${hue}, ${saturation}%, ${lightness}%, 0.35)`
}

const itemStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '8px 10px',
  borderRadius: 6,
  cursor: 'grab',
  border: '1px solid var(--border)',
  userSelect: 'none',
  marginBottom: 4,
  background: 'var(--card)',
  transition: 'all 0.15s ease',
}

const badgeBase: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  borderRadius: 4,
  padding: '1px 6px',
  fontSize: 10,
  fontWeight: 500,
  lineHeight: '16px',
  flexShrink: 0,
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
        background: hovered ? 'var(--secondary)' : 'var(--card)',
        borderColor: hovered ? 'var(--primary)' : 'var(--border)',
        transform: hovered ? 'translateX(2px)' : 'translateX(0)',
      }}
      draggable
      onDragStart={e => onDragStart(e, node.type)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      title={node.description || `Arrastra ${node.type} al canvas`}
    >
      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--foreground)', lineHeight: 1.4, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {node.type}
      </span>
      <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
        <span style={{ ...badgeBase, border: '1px solid var(--border)', color: 'var(--muted-foreground)', fontSize: 9 }}>
          {node.is_exec_node ? 'exec' : 'pure'}
        </span>
        <span style={{ ...badgeBase, background: decoratorColor.bg, color: decoratorColor.text, fontSize: 9 }}>
          {node.decorator.replace('_node', '')}
        </span>
      </div>
    </div>
  )
}

function Section({ label, nodes, onDragStart }: { label: string; nodes: NodeSpec[]; onDragStart: (e: React.DragEvent, type: string) => void }) {
  const [open, setOpen] = useState(true)
  const categoryBg = getCategoryColor(label)

  return (
    <div style={{ marginBottom: 4 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 8px 4px',
          background: categoryBg,
          border: 'none',
          cursor: 'pointer',
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--foreground)',
          textTransform: 'uppercase',
          letterSpacing: '0.07em',
          borderRadius: 4,
        }}
      >
        <span>{label}</span>
        <span style={{ fontSize: 8, transition: 'transform 0.15s', display: 'inline-block', transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▾</span>
      </button>
      {open && (
        <div style={{ background: categoryBg, borderRadius: 4, padding: '4px 8px', marginTop: 2, marginLeft: 8 }}>
          {nodes.map(n => <NodeItem key={n.type} node={n} onDragStart={onDragStart} />)}
        </div>
      )}
    </div>
  )
}

export default function NodePalette({ catalog }: Props) {
  const [open, setOpen] = useState(true)
  const [search, setSearch] = useState('')
  const [builtinOpen, setBuiltinOpen] = useState(true)
  const [customOpen, setCustomOpen] = useState(true)

  const { builtin, custom } = useMemo(() => {
    const q = search.toLowerCase()
    const all = Object.values(catalog).filter(n => !q || n.type.toLowerCase().includes(q))
    return {
      builtin: all.filter(n => n.is_builtin),
      custom: all.filter(n => !n.is_builtin),
    }
  }, [catalog, search])

  const builtinGroups = useMemo(() => groupByCategory(builtin), [builtin])
  const customGroups = useMemo(() => groupByCategory(custom), [custom])

  function onDragStart(e: React.DragEvent, nodeType: string) {
    e.dataTransfer.setData('application/rayflow-node', nodeType)
    e.dataTransfer.effectAllowed = 'copy'
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      ...(open
        ? { flex: 1, overflow: 'hidden', minHeight: 0 }
        : { flexShrink: 0 }
      ),
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
            {Object.keys(builtinGroups).length === 0 && Object.keys(customGroups).length === 0 && (
              <div style={{ textAlign: 'center', color: 'var(--muted-foreground)', fontSize: 13, padding: '24px 0' }}>
                Sin resultados
              </div>
            )}

            {/* BUILTIN SECTION */}
            {Object.keys(builtinGroups).length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <button
                  onClick={() => setBuiltinOpen(o => !o)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 12px 8px',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: 12,
                    fontWeight: 700,
                    color: 'var(--foreground)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                  }}
                >
                  <span>Builtin</span>
                  <span style={{ fontSize: 10, transition: 'transform 0.15s', display: 'inline-block', transform: builtinOpen ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▾</span>
                </button>
                {builtinOpen && (
                  <div style={{ paddingLeft: 20 }}>
                    {Object.entries(builtinGroups).map(([cat, nodes]) => (
                      <Section key={`builtin-${cat}`} label={cat} nodes={nodes} onDragStart={onDragStart} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* CUSTOM SECTION */}
            {Object.keys(customGroups).length > 0 && (
              <div>
                <button
                  onClick={() => setCustomOpen(o => !o)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 12px 8px',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: 12,
                    fontWeight: 700,
                    color: 'var(--foreground)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                  }}
                >
                  <span>Custom</span>
                  <span style={{ fontSize: 10, transition: 'transform 0.15s', display: 'inline-block', transform: customOpen ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▾</span>
                </button>
                {customOpen && (
                  <div style={{ paddingLeft: 20 }}>
                    {Object.entries(customGroups).map(([cat, nodes]) => (
                      <Section key={`custom-${cat}`} label={cat} nodes={nodes} onDragStart={onDragStart} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
