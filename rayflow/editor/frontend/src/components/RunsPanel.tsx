import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useFlowStore, selectActiveTab, type Run } from '@/store/flowStore'
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

function formatDuration(startedAt: number, endedAt?: number): string {
  if (!endedAt) return ''
  const ms = endedAt - startedAt
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

interface Props {
  activeFlow: FlowMeta | null
  validationErrors: string[]
  onLoad: () => void
}

export default function RunsPanel({ activeFlow, validationErrors, onLoad }: Props) {
  const tab = useFlowStore(selectActiveTab)
  const { setActiveRun } = useFlowStore()
  const { startRun, unload, abort } = useRunStream(activeFlow?.name ?? '')
  const [inputs, setInputs] = useState<Record<string, string>>({})

  // Cancelar stream SSE si el tab activo cambia mientras hay un run en vuelo
  useEffect(() => {
    return () => { abort() }
  }, [activeFlow?.name])

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
  const isLoading = tab.loadingIntoRay
  const isStale = tab.stale
  const canRun = isLoaded && !isLoading && !isRunning && !hasErrors

  async function handleRun() {
    if (!canRun) return
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
    await startRun(coerced)
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
            disabled={!canRun}
            style={{ height: 32, fontSize: 13, flex: 1 }}
          >
            {isRunning ? '⏳ Ejecutando…'
              : isLoading ? '⏳ Cargando en Ray…'
              : '▶ Test flow'}
          </Button>
          {isLoaded && !isLoading && !isRunning && (
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

        {/* Indicador de estado */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {/* Chip clickable solo cuando no cargado y sin errores */}
          {!isLoaded && !isLoading && !hasErrors ? (
            <button
              onClick={onLoad}
              title="Cargar flow en Ray para poder ejecutarlo"
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '4px 8px', borderRadius: 5,
                background: 'transparent',
                border: '1px solid var(--border)',
                cursor: 'pointer',
                textAlign: 'left',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(16,185,129,0.08)'
                e.currentTarget.style.borderColor = 'rgba(16,185,129,0.4)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.borderColor = 'var(--border)'
              }}
            >
              <span style={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0, background: '#475569' }} />
              <span style={{ fontSize: 11, color: 'var(--muted-foreground)', fontWeight: 500 }}>
                No cargado — click para cargar
              </span>
            </button>
          ) : (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '4px 8px', borderRadius: 5,
              background: isLoading ? 'rgba(245,158,11,0.08)'
                : isLoaded ? 'rgba(16,185,129,0.08)'
                : 'rgba(239,68,68,0.08)',
              border: `1px solid ${isLoading ? 'rgba(245,158,11,0.25)'
                : isLoaded ? 'rgba(16,185,129,0.25)'
                : 'rgba(239,68,68,0.25)'}`,
            }}>
              <span style={{
                width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                background: isLoading ? '#f59e0b' : isLoaded ? '#10b981' : 'var(--destructive)',
              }} />
              <span style={{
                fontSize: 11, fontWeight: 500,
                color: isLoading ? '#fcd34d' : isLoaded ? '#34d399' : 'var(--destructive)',
              }}>
                {isLoading ? 'Cargando en Ray…'
                  : isLoaded ? 'Listo para ejecutar'
                  : `${validationErrors.length} error(es) — no cargado`}
              </span>
            </div>
          )}
          {isStale && (
            <span style={{ fontSize: 11, color: '#f59e0b', paddingLeft: 2 }}>⚠ cambios sin recargar — guarda para actualizar</span>
          )}
        </div>
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
                  <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
                    <span style={{ fontSize: 11, color: dot, fontWeight: 500 }}>{statusLabel(run.status)}</span>
                    {run.endedAt && (
                      <span style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>
                        {formatDuration(run.startedAt, run.endedAt)}
                      </span>
                    )}
                  </div>
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
                {activeRun.endedAt && (
                  <span style={{ fontSize: 11, color: 'var(--muted-foreground)', marginLeft: 'auto' }}>
                    {formatDuration(activeRun.startedAt, activeRun.endedAt)}
                  </span>
                )}
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
                {activeRun.endedAt && (
                  <span style={{ fontSize: 11, color: 'var(--muted-foreground)', marginLeft: 'auto' }}>
                    {formatDuration(activeRun.startedAt, activeRun.endedAt)}
                  </span>
                )}
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
