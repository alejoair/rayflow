import { Handle, Position } from '@xyflow/react'
import { typeColor } from '@/lib/translator'
import type { NodeSpec } from '@/lib/api'

interface NodeCardProps {
  data: { nodeType: string; meta: NodeSpec | null; literals: Record<string, unknown>; runStatus?: 'idle' | 'running' | 'done' | 'error' }
  selected: boolean
}

export default function NodeCard({ data, selected }: NodeCardProps) {
  const runStatus = data.runStatus
  const { nodeType, meta } = data

  const cls = [
    'rf-node',
    selected ? 'selected' : '',
    !meta ? 'has-error' : '',
    runStatus === 'running' ? 'node-running' : '',
    runStatus === 'done' ? 'node-done' : '',
  ].filter(Boolean).join(' ')

  if (!meta) {
    return (
      <div className={cls} style={{ minWidth: 140 }}>
        <div className="rf-node-header"><span>{nodeType}</span></div>
        <div className="rf-node-body">
          <div className="rf-pin-row" style={{ color: 'var(--destructive)', fontSize: 11, padding: '4px 10px' }}>
            Tipo desconocido
          </div>
        </div>
      </div>
    )
  }

  const hasExecIn = meta.has_exec_in
  const execOutputs = meta.exec_outputs || []
  const inputs = meta.inputs || []
  const outputs = meta.outputs || []

  const decorator = meta.decorator
  const isRay = decorator === 'ray_node'
  const runtimeBadge = isRay
    ? { label: 'RAY', color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' }
    : { label: 'LOCAL', color: '#34d399', bg: 'rgba(52,211,153,0.10)' }

  return (
    <div className={cls}>
      <div className="rf-node-header" style={{ paddingLeft: hasExecIn ? 24 : 10, paddingRight: execOutputs.length > 0 ? 24 : 10 }}>
        {hasExecIn && (
          <Handle
            type="target"
            position={Position.Left}
            id="exec-in"
            style={{ background: 'var(--exec-color)', borderColor: 'var(--exec-color)', width: 12, height: 12, left: 6 }}
          />
        )}
        {execOutputs.length > 0 && (
          <Handle
            type="source"
            position={Position.Right}
            id={`exec-out-${execOutputs[0]}`}
            style={{ background: 'var(--exec-color)', borderColor: 'var(--exec-color)', width: 12, height: 12, right: 6 }}
          />
        )}
        {hasExecIn && <span className="rf-node-header-dot" />}
        <span style={{ flex: 1 }}>{nodeType}</span>
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: '0.07em',
          color: runtimeBadge.color, background: runtimeBadge.bg,
          borderRadius: 4, padding: '1px 5px', lineHeight: '16px',
          flexShrink: 0,
        }}>{runtimeBadge.label}</span>
      </div>

      {execOutputs.slice(1).map(pin => (
        <div key={pin} className="rf-pin-row output" style={{ paddingRight: 28, position: 'relative' }}>
          <span className="rf-pin-label" style={{ color: 'var(--exec-color)', fontSize: 11 }}>{pin}</span>
          <Handle
            type="source"
            position={Position.Right}
            id={`exec-out-${pin}`}
            style={{ background: 'var(--exec-color)', borderColor: 'var(--exec-color)', width: 12, height: 12, right: 6 }}
          />
        </div>
      ))}

      <div className="rf-node-body">
        {inputs.map(p => {
          const color = typeColor(p.type)
          return (
            <div key={p.name} className="rf-pin-row" style={{ paddingLeft: 24 }}>
              <Handle
                type="target"
                position={Position.Left}
                id={`data-in-${p.name}`}
                style={{ background: 'var(--card)', borderColor: color, left: 6 }}
              />
              <span className="rf-pin-type" style={{ color }}>{p.type}</span>
              <span className="rf-pin-label">{p.name}</span>
            </div>
          )
        })}
        {outputs.map(p => {
          const color = typeColor(p.type)
          return (
            <div key={p.name} className="rf-pin-row output" style={{ paddingRight: 24 }}>
              <span className="rf-pin-label">{p.name}</span>
              <span className="rf-pin-type" style={{ color }}>{p.type}</span>
              <Handle
                type="source"
                position={Position.Right}
                id={`data-out-${p.name}`}
                style={{ background: 'var(--card)', borderColor: color, right: 6 }}
              />
            </div>
          )
        })}
        {inputs.length === 0 && outputs.length === 0 && !hasExecIn && execOutputs.length === 0 && (
          <div className="rf-pin-row" style={{ color: 'var(--muted-foreground)', fontSize: 11, fontStyle: 'italic', padding: '4px 10px' }}>
            sin pines
          </div>
        )}
      </div>
    </div>
  )
}
