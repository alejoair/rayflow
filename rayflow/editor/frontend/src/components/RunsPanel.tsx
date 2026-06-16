import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useFlowStore, type Run } from '@/store/flowStore'
import { useRunStream } from '@/hooks/useRunStream'
import type { FlowMeta } from '@/lib/api'

function statusColor(status: Run['status']) {
  if (status === 'running') return 'bg-yellow-500'
  if (status === 'done') return 'bg-green-500'
  if (status === 'error') return 'bg-red-500'
  return 'bg-gray-500'
}

function statusVariant(status: Run['status']): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'done') return 'default'
  if (status === 'error') return 'destructive'
  return 'secondary'
}

interface Props {
  activeFlow: FlowMeta | null
  validationErrors: string[]
}

export default function RunsPanel({ activeFlow, validationErrors }: Props) {
  const tab = useFlowStore(s => s.getActiveTab())
  const { setActiveRun } = useFlowStore()
  const { startRun } = useRunStream(activeFlow?.name ?? '')
  const [inputs, setInputs] = useState<Record<string, string>>({})

  if (!activeFlow || !tab) {
    return (
      <div className="border-t border-[var(--border)] bg-[var(--card)] px-4 py-3 text-xs text-[var(--muted-foreground)]">
        Abre un flow para ejecutarlo
      </div>
    )
  }

  const flowInputs = activeFlow.inputs || {}

  async function handleRun() {
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
    <div className="border-t border-[var(--border)] bg-[var(--card)] flex flex-shrink-0" style={{ maxHeight: 220 }}>

      {/* Inputs + botón */}
      <div className="flex items-start gap-3 p-3 border-r border-[var(--border)] flex-shrink-0">
        {Object.keys(flowInputs).length > 0 && (
          <div className="flex gap-2 flex-wrap items-end">
            {Object.entries(flowInputs).map(([name, type]) => (
              <div key={name} className="flex flex-col gap-0.5">
                <label className="text-[10px] text-[var(--muted-foreground)]">{name} ({type})</label>
                <Input
                  type={type === 'int' || type === 'float' ? 'number' : 'text'}
                  placeholder={name}
                  value={inputs[name] ?? ''}
                  onChange={e => setInputs(p => ({ ...p, [name]: e.target.value }))}
                  className="h-7 w-28 text-xs bg-[var(--secondary)] border-[var(--border)] text-[var(--foreground)]"
                />
              </div>
            ))}
          </div>
        )}
        <div className="flex flex-col gap-1 justify-end" style={{ paddingTop: Object.keys(flowInputs).length ? 18 : 0 }}>
          <Button
            size="sm"
            onClick={handleRun}
            disabled={validationErrors.length > 0 || tab.runs.some(r => r.status === 'running')}
            className="h-7 text-xs"
          >
            ▶ Ejecutar
          </Button>
          {validationErrors.length > 0 && (
            <div className="text-[10px] text-red-400">{validationErrors.length} error(es)</div>
          )}
        </div>
      </div>

      {/* Historial de runs */}
      {runs.length > 0 && (
        <div className="flex gap-2 p-3 overflow-x-auto items-start">
          {runs.map(run => (
            <button
              key={run.runId}
              onClick={() => setActiveRun(activeFlow.name, run.runId)}
              className={`flex flex-col gap-1 p-2 rounded border text-left flex-shrink-0 transition-colors ${
                run.runId === activeRunId
                  ? 'border-[var(--primary)] bg-[var(--secondary)]'
                  : 'border-[var(--border)] hover:border-[var(--muted-foreground)]'
              }`}
              style={{ minWidth: 100 }}
            >
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${statusColor(run.status)}`} />
                <span className="text-[10px] text-[var(--muted-foreground)]">
                  {new Date(run.startedAt).toLocaleTimeString()}
                </span>
              </div>
              <Badge variant={statusVariant(run.status)} className="text-[10px] h-4 px-1 w-fit">
                {run.status}
              </Badge>
              {run.status === 'done' && run.result && (
                <pre className="text-[10px] text-green-400 mt-1 max-w-[160px] overflow-hidden text-ellipsis">
                  {JSON.stringify(run.result)}
                </pre>
              )}
              {run.status === 'error' && (
                <div className="text-[10px] text-red-400 mt-1 max-w-[160px] overflow-hidden text-ellipsis">
                  {run.error}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Resultado del run activo */}
      {activeRun?.status === 'done' && activeRun.result && (
        <div className="p-3 border-l border-[var(--border)] flex-shrink-0">
          <div className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-1">Resultado</div>
          <ScrollArea className="max-h-40">
            <pre className="text-[11px] text-green-400 font-mono">{JSON.stringify(activeRun.result, null, 2)}</pre>
          </ScrollArea>
        </div>
      )}
    </div>
  )
}
