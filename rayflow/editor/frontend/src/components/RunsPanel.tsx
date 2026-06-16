import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useFlowStore, type Run } from '@/store/flowStore'
import { useRunStream } from '@/hooks/useRunStream'
import { typeColor } from '@/lib/translator'
import type { FlowMeta } from '@/lib/api'

function statusDot(status: Run['status']) {
  if (status === 'running') return '#facc15'
  if (status === 'done') return '#10b981'
  if (status === 'error') return 'var(--destructive)'
  return 'var(--muted-foreground)'
}

function statusLabel(status: Run['status']) {
  if (status === 'running') return 'ejecutando'
  if (status === 'done') return 'listo'
  if (status === 'error') return 'error'
  return 'idle'
}

interface Props {
  activeFlow: FlowMeta | null
  validationErrors: string[]
  onSave: () => Promise<void>
}

export default function RunsPanel({ activeFlow, validationErrors, onSave }: Props) {
  const tab = useFlowStore(s => s.getActiveTab())
  const { setActiveRun } = useFlowStore()
  const { startRun, unload } = useRunStream(activeFlow?.name ?? '')
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [preparing, setPreparing] = useState(false)

  if (!activeFlow || !tab) {
    return (
      <div style={{
        borderTop: '1px solid var(--border)',
        background: 'var(--card)',
        padding: '10px 16px',
        fontSize: 13,
        color: 'var(--muted-foreground)',
        flexShrink: 0,
      }}>
        Abre un flow para ejecutarlo
      </div>
    )
  }

  const flowInputs = (activeFlow as { inputs?: Record<string, string> }).inputs || {}
  const isRunning = tab.runs.some(r => r.status === 'running')
  const hasErrors = validationErrors.length > 0
  const isLoaded = tab.loaded
  const isBusy = preparing || isRunning

  async function handleRun() {
    if (isBusy) return
    setPreparing(true)
    try {
      const coerced: Record<string, unknown> = {}
      Object.entries(flowInputs).forEach(([name, type]) => {
        const raw = inputs[name]
        if (!raw && raw !== '0') return
        const t = type.toLowerCase()
        if (t === 'int') coerced[name] = parseInt(raw, 10)
        else if (t === 'float') coerced[name] = parseFloat(raw)
        else if (t === 'bool') coerced[name] = raw === 'true'
        else if (t === 'list' || t === 'dict') { try { coerced[name] = JSON.parse(raw) } catch { coerced[name] = raw } }
        else coerced[name] = raw
      })
      await startRun(coerced, { dirty: tab?.dirty ?? false, loaded: tab?.loaded ?? false, onSave })
    } finally {
      setPreparing(false)
    }
  }

  const runs = tab.runs
  const activeRunId = tab.activeRunId
  const activeRun = runs.find(r => r.runId === activeRunId)

  return (
    <div style={{
      borderTop: '1px solid var(--border)',
      background: 'var(--card)',
      display: 'flex',
      flexShrink: 0,
      height: 200,
      overflow: 'hidden',
    }}>

      {/* Zona izquierda: inputs + botón */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: '12px 16px',
        borderRight: '1px solid var(--border)',
        flexShrink: 0,
        minWidth: 160,
        justifyContent: 'center',
      }}>
        {Object.entries(flowInputs).map(([name, type]) => {
          const color = typeColor(type)
          return (
            <div key={name} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 11, color: 'var(--muted-foreground)', display: 'flex', gap: 5, alignItems: 'center' }}>
                <span style={{ color }}>{type}</span>
                <span>{name}</span>
              </label>
              <Input
                type={type === 'int' || type === 'float' ? 'number' : 'text'}
                placeholder={name}
                value={inputs[name] ?? ''}
                onChange={e => setInputs(p => ({ ...p, [name]: e.target.value }))}
                style={{ height: 32, width: 140, fontSize: 13 }}
              />
            </div>
          )
        })}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Button
            size="sm"
            onClick={handleRun}
            disabled={hasErrors || isBusy}
            style={{ height: 32, fontSize: 13, flex: 1 }}
          >
            {isBusy ? '⏳ Ejecutando…' : '▶ Ejecutar'}
          </Button>
          {isLoaded && !isBusy && (
            <button
              onClick={unload}
              title="Descargar flow de Ray"
              style={{
                height: 32, width: 32, borderRadius: 6, border: '1px solid var(--border)',
                background: 'transparent', cursor: 'pointer', fontSize: 14,
                color: 'var(--muted-foreground)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--destructive)')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
            >⏹</button>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: isLoaded ? '#10b981' : 'var(--muted-foreground)', flexShrink: 0 }} />
          <span style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
            {isLoaded ? 'cargado en Ray' : 'no cargado'}
          </span>
          {tab.dirty && <span style={{ fontSize: 11, color: 'var(--primary)' }}>● cambios sin guardar</span>}
        </div>
        {hasErrors && (
          <div style={{ fontSize: 11, color: 'var(--destructive)' }}>{validationErrors.length} error(es)</div>
        )}
      </div>

      {/* Zona central: historial de runs */}
      {runs.length > 0 && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          padding: '12px 8px',
          borderRight: '1px solid var(--border)',
          overflowY: 'auto',
          flexShrink: 0,
          width: 160,
        }}>
          <div style={{
            fontSize: 11, fontWeight: 600, color: 'var(--muted-foreground)',
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4, padding: '0 4px',
          }}>Runs</div>
          {[...runs].reverse().map(run => {
            const isActive = run.runId === activeRunId
            const dot = statusDot(run.status)
            return (
              <button
                key={run.runId}
                onClick={() => setActiveRun(activeFlow.name, run.runId)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 8px',
                  borderRadius: 6,
                  border: `1px solid ${isActive ? 'var(--primary)' : 'var(--border)'}`,
                  background: isActive ? 'var(--secondary)' : 'transparent',
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                }}
              >
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: dot, flexShrink: 0 }} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 1, overflow: 'hidden' }}>
                  <span style={{ fontSize: 11, color: 'var(--muted-foreground)', whiteSpace: 'nowrap' }}>
                    {new Date(run.startedAt).toLocaleTimeString()}
                  </span>
                  <span style={{ fontSize: 11, color: dot, fontWeight: 500 }}>{statusLabel(run.status)}</span>
                </div>
              </button>
            )
          })}
        </div>
      )}

      {/* Zona derecha: detalle del run activo */}
      {activeRun && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {activeRun.status === 'running' && (
            <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#facc15', flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: 'var(--muted-foreground)' }}>Ejecutando…</span>
            </div>
          )}

          {activeRun.status === 'done' && (
            <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#10b981', flexShrink: 0 }} />
                <span style={{ fontSize: 11, fontWeight: 600, color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Completado</span>
              </div>
              <pre style={{
                fontSize: 12, fontFamily: 'monospace',
                color: activeRun.result && Object.keys(activeRun.result).length > 0 ? '#10b981' : 'var(--muted-foreground)',
                margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
              }}>
                {activeRun.result && Object.keys(activeRun.result).length > 0
                  ? JSON.stringify(activeRun.result, null, 2)
                  : '{}'}
              </pre>
            </div>
          )}

          {activeRun.status === 'error' && (
            <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--destructive)', flexShrink: 0 }} />
                <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--destructive)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Error</span>
              </div>
              <div style={{
                fontSize: 12, fontFamily: 'monospace', color: 'var(--destructive)',
                background: 'rgba(239,68,68,0.08)', borderRadius: 5, padding: '6px 8px',
              }}>{activeRun.error ?? 'Error desconocido'}</div>
            </div>
          )}

        </div>
      )}

    </div>
  )
}
