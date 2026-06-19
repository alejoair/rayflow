import { Handle, Position } from '@xyflow/react'
import { typeColor } from '@/lib/translator'
import type { NodeSpec } from '@/lib/api'

// Triángulo SVG que reemplaza visualmente el círculo del Handle de exec.
// El Handle real queda invisible (opacity 0) pero sigue siendo el punto de conexión.
function ExecHandle({ type, position, id, style }: {
  type: 'source' | 'target'
  position: Position
  id: string
  style: React.CSSProperties
}) {
  const isLeft = position === Position.Left
  // Triángulo apuntando hacia afuera del nodo
  const points = isLeft ? '10,2 10,10 2,6' : '2,2 2,10 10,6'
  return (
    <div style={{ position: 'absolute', ...style, width: 12, height: 12 }}>
      <Handle
        type={type}
        position={position}
        id={id}
        style={{ opacity: 0, width: 12, height: 12, minWidth: 0, minHeight: 0, border: 'none', background: 'transparent' }}
      />
      <svg
        width={12} height={12}
        style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none' }}
        viewBox="0 0 12 12"
      >
        <polygon points={points} fill="var(--exec-color)" />
      </svg>
    </div>
  )
}

interface NodeCardProps {
  data: { nodeType: string; meta: NodeSpec | null; literals: Record<string, unknown>; runStatus?: 'idle' | 'running' | 'done' | 'error'; hasValidationError?: boolean }
  selected: boolean
}

export default function NodeCard({ data, selected }: NodeCardProps) {
  const runStatus = data.runStatus
  const { nodeType, meta } = data

  const isPure = meta ? !meta.is_exec_node : false
  const cls = [
    'rf-node',
    isPure ? 'pure' : '',
    selected ? 'selected' : '',
    (!meta || data.hasValidationError) ? 'has-error' : '',
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
          <ExecHandle type="target" position={Position.Left} id="exec-in" style={{ top: '50%', transform: 'translateY(-50%)', left: 6 }} />
        )}
        {execOutputs.length > 0 && (
          <ExecHandle type="source" position={Position.Right} id={`exec-out-${execOutputs[0]}`} style={{ top: '50%', transform: 'translateY(-50%)', right: 6 }} />
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
          <ExecHandle type="source" position={Position.Right} id={`exec-out-${pin}`} style={{ top: '50%', transform: 'translateY(-50%)', right: 6 }} />
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
