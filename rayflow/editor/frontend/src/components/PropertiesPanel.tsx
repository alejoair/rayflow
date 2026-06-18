import { useState } from 'react'
import type { Node, Edge } from '@xyflow/react'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { typeColor } from '@/lib/translator'
import type { NodeSpec, PinSpec, FlowMeta } from '@/lib/api'

// ── Estilos compartidos ────────────────────────────────────────────────────

const sectionLabel = {
  fontSize: 11, fontWeight: 600,
  color: 'var(--muted-foreground)',
  textTransform: 'uppercase' as const,
  letterSpacing: '0.06em',
  marginBottom: 10,
}

const fieldLabel = {
  fontSize: 11,
  color: 'var(--muted-foreground)',
  marginBottom: 4,
  display: 'block' as const,
}

// ── LiteralField ──────────────────────────────────────────────────────────

interface LiteralFieldProps {
  pin: PinSpec
  value: unknown
  onChange: (val: unknown) => void
  catalog: Record<string, NodeSpec>
  flowList: FlowMeta[]
}

function LiteralField({ pin, value, onChange, catalog, flowList }: LiteralFieldProps) {
  const t = (pin.type || 'Any').toLowerCase()
  const color = typeColor(pin.type)

  const labelEl = (
    <label style={fieldLabel}>
      <span style={{ color }}>{pin.type}</span>
      <span style={{ color: 'var(--foreground)', marginLeft: 6 }}>{pin.name}</span>
    </label>
  )

  if (pin.name === 'node_type') {
    return (
      <div>
        {labelEl}
        <Select value={String(value ?? '')} onValueChange={onChange}>
          <SelectTrigger style={{ height: 32, fontSize: 13 }}>
            <SelectValue placeholder="— elegir —" />
          </SelectTrigger>
          <SelectContent>
            {Object.keys(catalog).map(k => (
              <SelectItem key={k} value={k} style={{ fontSize: 13 }}>{k}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    )
  }

  if (pin.name === 'flow') {
    return (
      <div>
        {labelEl}
        <Select value={String(value ?? '')} onValueChange={onChange}>
          <SelectTrigger style={{ height: 32, fontSize: 13 }}>
            <SelectValue placeholder="— elegir —" />
          </SelectTrigger>
          <SelectContent>
            {flowList.map(f => (
              <SelectItem key={f.name} value={f.name} style={{ fontSize: 13 }}>{f.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    )
  }

  if (t === 'bool') {
    return (
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={!!value}
          onChange={e => onChange(e.target.checked)}
          style={{ accentColor: 'var(--primary)', width: 14, height: 14 }}
        />
        <span style={{ fontSize: 13, color: 'var(--foreground)' }}>{pin.name}</span>
        <span style={{ fontSize: 11, color }}>{pin.type}</span>
      </label>
    )
  }

  if (t === 'list' || t === 'dict' || t.startsWith('list[') || t.startsWith('dict[')) {
    const display = typeof value === 'string'
      ? value
      : JSON.stringify(value ?? (t.startsWith('list') ? [] : {}), null, 2)
    return (
      <div>
        {labelEl}
        <textarea
          value={display}
          onChange={e => {
            try { onChange(JSON.parse(e.target.value)) } catch { onChange(e.target.value) }
          }}
          rows={3}
          style={{
            width: '100%', boxSizing: 'border-box',
            padding: '6px 10px', borderRadius: 6,
            border: '1px solid var(--border)',
            background: 'var(--secondary)',
            color: 'var(--foreground)',
            fontSize: 12, fontFamily: 'monospace',
            resize: 'vertical', outline: 'none',
          }}
        />
      </div>
    )
  }

  return (
    <div>
      {labelEl}
      <Input
        type={t === 'int' || t === 'float' ? 'number' : 'text'}
        step={t === 'float' ? 'any' : undefined}
        value={String(value ?? (pin.default ?? ''))}
        onChange={e => {
          const v = e.target.value
          onChange(t === 'int' ? parseInt(v, 10) : t === 'float' ? parseFloat(v) : v)
        }}
        style={{ height: 32, fontSize: 13 }}
      />
    </div>
  )
}

// ── Sección colapsable ────────────────────────────────────────────────────

function Section({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div style={{ borderTop: '1px solid var(--border)', padding: '12px 16px' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginBottom: open ? 12 : 0,
        }}
      >
        <span style={sectionLabel}>{title}</span>
        <span style={{ fontSize: 10, color: 'var(--muted-foreground)', display: 'inline-block', transform: open ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.15s' }}>▾</span>
      </button>
      {open && children}
    </div>
  )
}

// ── PropertiesPanel ───────────────────────────────────────────────────────

interface Props {
  selectedNodeId: string | null
  nodes: Node[]
  edges: Edge[]
  catalog: Record<string, NodeSpec>
  flowList: FlowMeta[]
  validationErrors: string[]
  onUpdateNode: (nodeId: string, update: Record<string, unknown>) => void
}

const headerStyle = {
  padding: '12px 16px',
  borderBottom: '1px solid var(--border)',
  fontSize: 11, fontWeight: 600,
  color: 'var(--muted-foreground)',
  textTransform: 'uppercase' as const,
  letterSpacing: '0.06em',
  flexShrink: 0,
}

export default function PropertiesPanel({
  selectedNodeId, nodes, edges, catalog, flowList, validationErrors, onUpdateNode,
}: Props) {
  const node = nodes.find(n => n.id === selectedNodeId)

  if (!node) {
    return (
      <div style={{ width: 240, display: 'flex', flexDirection: 'column', borderLeft: '1px solid var(--border)', background: 'var(--card)', flexShrink: 0 }}>
        <div style={headerStyle}>Propiedades</div>
        <div style={{ padding: 16, fontSize: 13, color: 'var(--muted-foreground)', textAlign: 'center' }}>
          Selecciona un nodo
        </div>
      </div>
    )
  }

  const data = node.data as { nodeType: string; meta: NodeSpec | null; literals: Record<string, unknown> }
  // Preferir la meta del nodo (puede tener pins dinámicos) sobre el catálogo global
  const meta = data.meta ?? catalog[data.nodeType] ?? null
  const literals = data.literals || {}

  const connectedInputs = new Set(
    edges
      .filter(e => e.target === node.id && e.type !== 'exec')
      .map(e => (e.targetHandle || '').replace('data-in-', ''))
  )

  const editablePins = meta ? meta.inputs.filter(p => !connectedInputs.has(p.name)) : []
  const nodeErrors = validationErrors.filter(e => e.includes(node.id) || e.includes(data.nodeType))

  function updateLiteral(pinName: string, val: unknown) {
    onUpdateNode(node!.id, { literals: { ...literals, [pinName]: val } })
  }

  function updateId(newId: string) {
    if (newId && newId !== node!.id) onUpdateNode(node!.id, { newId })
  }

  return (
    <div style={{ width: 240, display: 'flex', flexDirection: 'column', borderLeft: '1px solid var(--border)', background: 'var(--card)', flexShrink: 0, overflow: 'hidden' }}>
      <div style={headerStyle}>Propiedades</div>

      <div style={{ flex: 1, overflowY: 'auto' }}>

        {/* Nodo */}
        <div style={{ padding: '12px 16px' }}>
          <div style={sectionLabel}>Nodo</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div>
              <span style={fieldLabel}>Tipo</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--primary)' }}>{data.nodeType}</span>
                {meta && (
                  <span style={{
                    fontSize: 10, padding: '1px 6px', borderRadius: 4,
                    border: '1px solid var(--border)', color: 'var(--muted-foreground)',
                  }}>{meta.is_exec_node ? 'exec' : 'pure'}</span>
                )}
              </div>
            </div>
            <div>
              <span style={fieldLabel}>ID</span>
              <Input
                defaultValue={node.id}
                onBlur={e => updateId(e.target.value.trim())}
                onKeyDown={e => { if (e.key === 'Enter') updateId((e.target as HTMLInputElement).value.trim()) }}
                style={{ height: 32, fontSize: 13 }}
              />
            </div>
          </div>
        </div>

        {/* Inputs literales */}
        {editablePins.length > 0 && (
          <Section title="Inputs">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {editablePins.map(p => (
                <LiteralField
                  key={p.name}
                  pin={p}
                  value={literals[p.name]}
                  onChange={val => updateLiteral(p.name, val)}
                  catalog={catalog}
                  flowList={flowList}
                />
              ))}
            </div>
          </Section>
        )}

        {/* Inputs conectados */}
        {connectedInputs.size > 0 && (
          <Section title="Conectados" defaultOpen={false}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[...connectedInputs].map(pin => {
                const pinSpec = meta?.inputs.find(p => p.name === pin)
                const color = typeColor(pinSpec?.type ?? 'Any')
                const sourceEdge = edges.find(e =>
                  e.target === node.id &&
                  e.type !== 'exec' &&
                  (e.targetHandle || '').replace('data-in-', '') === pin
                )
                return (
                  <div key={pin} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: color, flexShrink: 0 }} />
                    <span style={{ fontSize: 12, color: 'var(--foreground)' }}>{pin}</span>
                    <span style={{ fontSize: 11, color: 'var(--muted-foreground)', marginLeft: 'auto' }}>
                      ← {sourceEdge?.source ?? 'arista'}
                    </span>
                  </div>
                )
              })}
            </div>
          </Section>
        )}

        {/* Outputs (informativo) */}
        {meta && meta.outputs.length > 0 && (
          <Section title="Outputs" defaultOpen={false}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {meta.outputs.map(p => {
                const color = typeColor(p.type)
                return (
                  <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: color, flexShrink: 0 }} />
                    <span style={{ fontSize: 12, color: 'var(--foreground)' }}>{p.name}</span>
                    <span style={{ fontSize: 11, color, marginLeft: 'auto' }}>{p.type}</span>
                  </div>
                )
              })}
            </div>
          </Section>
        )}

        {/* Errores */}
        {nodeErrors.length > 0 && (
          <Section title="Errores">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {nodeErrors.map((e, i) => (
                <div key={i} style={{
                  fontSize: 11, fontFamily: 'monospace',
                  color: 'var(--destructive)',
                  background: 'rgba(239,68,68,0.08)',
                  borderRadius: 5, padding: '6px 8px',
                  lineHeight: 1.5,
                }}>{e}</div>
              ))}
            </div>
          </Section>
        )}

      </div>
    </div>
  )
}
