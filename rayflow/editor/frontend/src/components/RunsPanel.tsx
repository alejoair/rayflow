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
  height: number
  onResizeMouseDown: (e: React.MouseEvent) => void
  resizeHandleStyle: React.CSSProperties
}

export default function RunsPanel({ activeFlow, validationErrors, onLoad, height, onResizeMouseDown, resizeHandleStyle }: Props) {
  const tab = useFlowStore(selectActiveTab)
  const { setActiveRun } = useFlowStore()
  const { startRun, unload, abort } = useRunStream(activeFlow?.name ?? '')
  const [inputs, setInputs] = useState<Record<string, string>>({})

  useEffect(() => {
    return () => { abort() }
  }, [activeFlow?.name])

  if (!activeFlow || !tab) {
    return (
      <div style={{
        position: 'relative',
        borderTop: '1px solid var(--border)',
        background: 'var(--card)',
        padding: '10px 16px',
        fontSize: 13,
        color: 'var(--muted-foreground)',
        flexShrink: 0,
        height,
      }}>
        <div style={resizeHandleStyle} onMouseDown={onResizeMouseDown} />
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

  // Colores del estado de carga
  const loadStateColor = isLoading ? '#f59e0b' : isLoaded ? '#10b981' : hasErrors ? 'var(--destructive)' : '#475569'
  const loadStateBg = isLoading ? 'rgba(245,158,11,0.08)' : isLoaded ? 'rgba(16,185,129,0.08)' : hasErrors ? 'rgba(239,68,68,0.08)' : 'transparent'
  const loadStateBorder = isLoading ? 'rgba(245,158,11,0.25)' : isLoaded ? 'rgba(16,185,129,0.25)' : hasErrors ? 'rgba(239,68,68,0.25)' : 'var(--border)'
  const loadStateText = isLoading ? 'Cargando en Ray…'
    : isLoaded ? (isStale ? 'Cargado — cambios pendientes' : 'Listo para ejecutar')
    : hasErrors ? `${validationErrors.length} error(es)`
    : 'No cargado'

  return (
    <div style={{
      position: 'relative',
      borderTop: '1px solid var(--border)',
      background: 'var(--card)',
      display: 'flex',
      flexShrink: 0,
      height,
      overflow: 'hidden',
    }}>
      {/* Handle de resize superior */}
      <div style={resizeHandleStyle} onMouseDown={onResizeMouseDown} />

      {/* ── Columna de control ── */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: '12px 14px',
        borderRight: '1px solid var(--border)',
        flexShrink: 0,
        width: 220,
        overflow: 'hidden',
      }}>
        {/* Título de sección */}
        <div style={{
          fontSize: 11, fontWeight: 600,
          color: 'var(--muted-foreground)',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}>Ejecutar</div>

        {/* Inputs del flow en fila */}
        {Object.keys(flowInputs).length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {Object.entries(flowInputs).map(([name, type]) => {
              const color = typeColor(type)
              return (
                <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <label style={{
                    fontSize: 11, color: 'var(--muted-foreground)',
                    flexShrink: 0, minWidth: 60,
                    display: 'flex', alignItems: 'center', gap: 4,
                  }}>
                    <span style={{ color, fontWeight: 500 }}>{type}</span>
                    <span>{name}</span>
                  </label>
                  <Input
                    type={type === 'int' || type === 'float' ? 'number' : 'text'}
                    placeholder={name}
                    value={inputs[name] ?? ''}
                    onChange={e => setInputs(p => ({ ...p, [name]: e.target.value }))}
                    style={{ height: 28, fontSize: 12, flex: 1 }}
                  />
                </div>
              )
            })}
          </div>
        )}

        {/* Botones: ejecutar + descargar */}
        <div style={{ display: 'flex', gap: 6 }}>
          <Button
            size="sm"
            onClick={handleRun}
            disabled={!canRun}
            style={{ height: 30, fontSize: 12, flex: 1 }}
          >
            {isRunning ? '⏳ Ejecutando…'
              : isLoading ? '⏳ Cargando…'
              : '▶ Ejecutar'}
          </Button>
          {isLoaded && !isLoading && !isRunning && (
            <button
              onClick={unload}
              title="Descargar flow de Ray"
              style={{
                height: 30, width: 30, borderRadius: 6, border: '1px solid var(--border)',
                background: 'transparent', cursor: 'pointer', fontSize: 13,
                color: 'var(--muted-foreground)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--destructive)')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
            >⏹</button>
          )}
        </div>

        {/* Chip de estado de carga */}
        {!isLoaded && !isLoading && !hasErrors ? (
          <button
            onClick={onLoad}
            title="Cargar flow en Ray"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '4px 8px', borderRadius: 5,
              background: 'transparent',
              border: '1px solid var(--border)',
              cursor: 'pointer', textAlign: 'left',
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
            <span style={{ width: 6, height: 6, borderRadius: '50%', flexShrink: 0, background: '#475569' }} />
            <span style={{ fontSize: 11, color: 'var(--muted-foreground)', fontWeight: 500 }}>
              No cargado — click para cargar
            </span>
          </button>
        ) : (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '4px 8px', borderRadius: 5,
            background: loadStateBg,
            border: `1px solid ${loadStateBorder}`,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', flexShrink: 0, background: loadStateColor }} />
            <span style={{ fontSize: 11, fontWeight: 500, color: loadStateColor }}>{loadStateText}</span>
          </div>
        )}

        {isStale && isLoaded && (
          <span style={{ fontSize: 11, color: '#f59e0b', paddingLeft: 2 }}>
            ⚠ guarda para recargar en Ray
          </span>
        )}
      </div>

      {/* ── Lista de runs ── */}
      {runs.length > 0 && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          padding: '12px 6px',
          borderRight: '1px solid var(--border)',
          overflowY: 'auto',
          flexShrink: 0,
          width: 148,
          gap: 3,
        }}>
          <div style={{
            fontSize: 11, fontWeight: 600, color: 'var(--muted-foreground)',
            textTransform: 'uppercase', letterSpacing: '0.06em',
            padding: '0 6px', marginBottom: 4,
          }}>Historial</div>
          {[...runs].reverse().map(run => {
            const isActive = run.runId === activeRunId
            const dot = statusDot(run.status)
            const dur = formatDuration(run.startedAt, run.endedAt)
            return (
              <button
                key={run.runId}
                onClick={() => setActiveRun(activeFlow.name, run.runId)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 7,
                  padding: '5px 8px',
                  borderRadius: 6,
                  border: `1px solid ${isActive ? 'var(--primary)' : 'transparent'}`,
                  background: isActive ? 'rgba(99,102,241,0.10)' : 'transparent',
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                  transition: 'background 0.1s, border-color 0.1s',
                }}
                onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'var(--secondary)' }}
                onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}
              >
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: dot, flexShrink: 0 }} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 1, overflow: 'hidden', flex: 1 }}>
                  <span style={{ fontSize: 11, color: 'var(--foreground)', whiteSpace: 'nowrap', fontWeight: isActive ? 600 : 400 }}>
                    {new Date(run.startedAt).toLocaleTimeString()}
                  </span>
                  <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                    <span style={{ fontSize: 10, color: dot }}>{statusLabel(run.status)}</span>
                    {dur && <span style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>{dur}</span>}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      )}

      {/* ── Detalle del run activo ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        {!activeRun && (
          <div style={{
            flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--muted-foreground)', fontSize: 12,
          }}>
            {runs.length === 0 ? 'Ejecuta el flow para ver resultados' : 'Selecciona un run'}
          </div>
        )}

        {activeRun?.status === 'running' && (
          <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: '#facc15', flexShrink: 0,
              boxShadow: '0 0 0 3px rgba(250,204,21,0.25)',
            }} />
            <span style={{ fontSize: 13, color: 'var(--muted-foreground)' }}>Ejecutando…</span>
          </div>
        )}

        {activeRun?.status === 'done' && (
          <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto', flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%',
                background: '#10b981', flexShrink: 0,
              }} />
              <span style={{ fontSize: 11, fontWeight: 600, color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Completado
              </span>
              {activeRun.endedAt && (
                <span style={{ fontSize: 11, color: 'var(--muted-foreground)', marginLeft: 'auto' }}>
                  {formatDuration(activeRun.startedAt, activeRun.endedAt)}
                </span>
              )}
            </div>
            <pre style={{
              fontSize: 12, fontFamily: 'monospace', margin: 0,
              whiteSpace: 'pre-wrap', wordBreak: 'break-all',
              color: activeRun.result && Object.keys(activeRun.result).length > 0 ? '#10b981' : 'var(--muted-foreground)',
              background: 'rgba(0,0,0,0.2)',
              borderRadius: 6, padding: '8px 10px',
              border: '1px solid var(--border)',
            }}>
              {activeRun.result && Object.keys(activeRun.result).length > 0
                ? JSON.stringify(activeRun.result, null, 2)
                : '{}'}
            </pre>
          </div>
        )}

        {activeRun?.status === 'error' && (
          <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto', flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--destructive)', flexShrink: 0 }} />
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--destructive)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Error
              </span>
              {activeRun.endedAt && (
                <span style={{ fontSize: 11, color: 'var(--muted-foreground)', marginLeft: 'auto' }}>
                  {formatDuration(activeRun.startedAt, activeRun.endedAt)}
                </span>
              )}
            </div>
            <div style={{
              fontSize: 12, fontFamily: 'monospace',
              color: 'var(--destructive)',
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.2)',
              borderRadius: 6, padding: '8px 10px',
              whiteSpace: 'pre-wrap', wordBreak: 'break-all',
            }}>
              {activeRun.error ?? 'Error desconocido'}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
