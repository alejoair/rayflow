import type { Node, Edge } from '@xyflow/react'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { NodeSpec, PinSpec, FlowMeta } from '@/lib/api'

interface LiteralFieldProps {
  pin: PinSpec
  value: unknown
  onChange: (val: unknown) => void
  catalog: Record<string, NodeSpec>
  flowList: FlowMeta[]
}

function LiteralField({ pin, value, onChange, catalog, flowList }: LiteralFieldProps) {
  const t = (pin.type || 'Any').toLowerCase()

  if (pin.name === 'node_type') {
    return (
      <div className="space-y-1">
        <label className="text-[11px] text-[var(--muted-foreground)]">{pin.name} ({pin.type})</label>
        <Select value={String(value ?? '')} onValueChange={onChange}>
          <SelectTrigger className="h-7 text-xs bg-[var(--secondary)] border-[var(--border)]">
            <SelectValue placeholder="— elegir —" />
          </SelectTrigger>
          <SelectContent className="bg-[var(--card)] border-[var(--border)]">
            {Object.keys(catalog).map(k => <SelectItem key={k} value={k} className="text-xs">{k}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
    )
  }

  if (pin.name === 'flow') {
    return (
      <div className="space-y-1">
        <label className="text-[11px] text-[var(--muted-foreground)]">{pin.name} (flow)</label>
        <Select value={String(value ?? '')} onValueChange={onChange}>
          <SelectTrigger className="h-7 text-xs bg-[var(--secondary)] border-[var(--border)]">
            <SelectValue placeholder="— elegir —" />
          </SelectTrigger>
          <SelectContent className="bg-[var(--card)] border-[var(--border)]">
            {flowList.map(f => <SelectItem key={f.name} value={f.name} className="text-xs">{f.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
    )
  }

  if (t === 'bool') {
    return (
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={!!value}
          onChange={e => onChange(e.target.checked)}
          className="accent-[var(--primary)] w-3.5 h-3.5"
        />
        <label className="text-[11px] text-[var(--muted-foreground)]">{pin.name}</label>
      </div>
    )
  }

  if (t === 'list' || t === 'dict' || t.startsWith('list[') || t.startsWith('dict[')) {
    const display = typeof value === 'string' ? value : JSON.stringify(value ?? (t.startsWith('list') ? [] : {}), null, 2)
    return (
      <div className="space-y-1">
        <label className="text-[11px] text-[var(--muted-foreground)]">{pin.name} ({pin.type})</label>
        <Textarea
          value={display}
          onChange={e => { try { onChange(JSON.parse(e.target.value)) } catch { onChange(e.target.value) } }}
          className="h-16 text-[11px] font-mono bg-[var(--secondary)] border-[var(--border)] text-[var(--foreground)] resize-none"
        />
      </div>
    )
  }

  return (
    <div className="space-y-1">
      <label className="text-[11px] text-[var(--muted-foreground)]">{pin.name} ({pin.type})</label>
      <Input
        type={t === 'int' || t === 'float' ? 'number' : 'text'}
        step={t === 'float' ? 'any' : undefined}
        value={String(value ?? (pin.default ?? ''))}
        onChange={e => {
          const v = e.target.value
          onChange(t === 'int' ? parseInt(v, 10) : t === 'float' ? parseFloat(v) : v)
        }}
        className="h-7 text-xs bg-[var(--secondary)] border-[var(--border)] text-[var(--foreground)]"
      />
    </div>
  )
}

interface Props {
  selectedNodeId: string | null
  nodes: Node[]
  edges: Edge[]
  catalog: Record<string, NodeSpec>
  flowList: FlowMeta[]
  validationErrors: string[]
  onUpdateNode: (nodeId: string, update: Record<string, unknown>) => void
}

export default function PropertiesPanel({ selectedNodeId, nodes, edges, catalog, flowList, validationErrors, onUpdateNode }: Props) {
  const node = nodes.find(n => n.id === selectedNodeId)

  if (!node) {
    return (
      <div className="w-64 flex flex-col border-l border-[var(--border)] bg-[var(--card)] flex-shrink-0">
        <div className="px-3 py-2 border-b border-[var(--border)] text-[11px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
          Propiedades
        </div>
        <div className="p-4 text-center text-xs text-[var(--muted-foreground)]">
          Selecciona un nodo en el canvas
        </div>
      </div>
    )
  }

  const data = node.data as { nodeType: string; meta: NodeSpec | null; literals: Record<string, unknown> }
  const meta = catalog[data.nodeType]
  const literals = data.literals || {}

  const connectedInputs = new Set(
    edges.filter(e => e.target === node.id && e.type !== 'exec')
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
    <div className="w-64 flex flex-col border-l border-[var(--border)] bg-[var(--card)] flex-shrink-0 overflow-hidden">
      <div className="px-3 py-2 border-b border-[var(--border)] text-[11px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider flex-shrink-0">
        Propiedades
      </div>
      <ScrollArea className="flex-1">
        <div className="divide-y divide-[var(--border)]">

          <div className="p-3 space-y-3">
            <div className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">Nodo</div>
            <div className="space-y-1">
              <label className="text-[11px] text-[var(--muted-foreground)]">Tipo</label>
              <div className="text-xs font-semibold text-[var(--primary)] py-0.5">{data.nodeType}</div>
            </div>
            <div className="space-y-1">
              <label className="text-[11px] text-[var(--muted-foreground)]">ID</label>
              <Input
                defaultValue={node.id}
                onBlur={e => updateId(e.target.value.trim())}
                onKeyDown={e => { if (e.key === 'Enter') updateId((e.target as HTMLInputElement).value.trim()) }}
                className="h-7 text-xs bg-[var(--secondary)] border-[var(--border)] text-[var(--foreground)]"
              />
            </div>
          </div>

          {editablePins.length > 0 && (
            <div className="p-3 space-y-3">
              <div className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">Inputs literales</div>
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
          )}

          {connectedInputs.size > 0 && (
            <div className="p-3 space-y-2">
              <div className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">Conectados</div>
              {[...connectedInputs].map(pin => (
                <div key={pin} className="text-[11px] text-[var(--muted-foreground)]">{pin} ← arista</div>
              ))}
            </div>
          )}

          {nodeErrors.length > 0 && (
            <div className="p-3 space-y-2">
              <div className="text-[10px] font-semibold text-red-400 uppercase tracking-wider">Errores</div>
              {nodeErrors.map((e, i) => (
                <div key={i} className="text-[11px] text-red-400 font-mono border-b border-[var(--border)] pb-1">{e}</div>
              ))}
            </div>
          )}

          {meta && (
            <div className="p-3 space-y-2">
              <div className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">Info</div>
              <div className="flex gap-1 flex-wrap">
                <Badge variant="outline" className="text-[10px] h-4 px-1">{meta.is_exec_node ? 'exec' : 'pure'}</Badge>
                <Badge variant="outline" className="text-[10px] h-4 px-1">{meta.decorator.replace('_node', '')}</Badge>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
