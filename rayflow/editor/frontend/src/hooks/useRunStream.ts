import { useCallback } from 'react'
import { useFlowStore, type Run, type RunEvent } from '@/store/flowStore'
import { unloadFlow, runFlowUrl } from '@/lib/api'

export function useRunStream(tabName: string) {
  const { addRun, updateRun, animMinMs } = useFlowStore()

  const startRun = useCallback(async (inputs: Record<string, unknown>) => {

    const runId = crypto.randomUUID()
    const run: Run = {
      runId,
      status: 'running',
      activeNodes: new Set(),
      doneNodes: new Set(),
      activeEdges: new Set(),
      logs: [],
      startedAt: Date.now(),
    }
    addRun(tabName, run)

    const url = runFlowUrl(tabName)
    let response: Response
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(inputs),
      })
    } catch (e) {
      updateRun(tabName, runId, {
        status: 'error',
        error: (e as Error).message,
        activeNodes: new Set(),
        activeEdges: new Set(),
      })
      return runId
    }

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: response.statusText }))
      updateRun(tabName, runId, {
        status: 'error',
        error: err.detail || response.statusText,
        activeNodes: new Set(),
        activeEdges: new Set(),
      })
      return runId
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    const patchRun = (patch: (run: Run) => Partial<Run>) => {
      useFlowStore.setState(s => ({
        tabs: s.tabs.map(t => t.name !== tabName ? t : {
          ...t,
          runs: t.runs.map(r => r.runId !== runId ? r : { ...r, ...patch(r) }),
        }),
      }))
    }

    // ─── Sistema de agrupación por ventana de tiempo ─────────────────────────
    // Eventos que llegan dentro de BATCH_WINDOW_MS entre sí se reproducen juntos
    // (son nodos paralelos). Después de cada grupo se espera animMinMs.
    const BATCH_WINDOW_MS = 50

    const groups: RunEvent[][] = []
    let pendingGroup: RunEvent[] = []
    let groupTimer: ReturnType<typeof setTimeout> | null = null
    let playing = false

    const playNextGroup = () => {
      if (groups.length === 0) { playing = false; return }
      playing = true
      const group = groups.shift()!

      // ¿Hay un evento terminal en el grupo?
      const terminal = group.find(e => e.event === 'flow_done' || e.event === 'flow_error')

      // Aplicar todos los eventos no-terminales del grupo al store simultáneamente
      const nonTerminal = group.filter(e => e.event !== 'flow_done' && e.event !== 'flow_error')
      if (nonTerminal.length > 0) applyGroup(nonTerminal)

      if (terminal) {
        setTimeout(() => {
          if (terminal.event === 'flow_done') {
            const result = (terminal as unknown as Record<string, unknown>).outputs as Record<string, unknown>
              ?? (terminal as unknown as Record<string, unknown>).result as Record<string, unknown>
            patchRun(() => ({ status: 'done', result, endedAt: Date.now(), activeNodes: new Set(), activeEdges: new Set() }))
          } else {
            const error = (terminal as unknown as Record<string, unknown>).error as string
            patchRun(() => ({ status: 'error', error, endedAt: Date.now(), activeNodes: new Set(), activeEdges: new Set() }))
          }
          playing = false
        }, animMinMs)
        return
      }

      setTimeout(playNextGroup, animMinMs)
    }

    const flushGroup = () => {
      groupTimer = null
      if (pendingGroup.length === 0) return
      groups.push([...pendingGroup])
      pendingGroup = []
      if (!playing) playNextGroup()
    }

    const enqueue = (evt: RunEvent) => {
      pendingGroup.push(evt)
      if (groupTimer !== null) clearTimeout(groupTimer)
      groupTimer = setTimeout(flushGroup, BATCH_WINDOW_MS)
    }

    const applyGroup = (group: RunEvent[]) => {
      const tabEdges = useFlowStore.getState().tabs.find(t => t.name === tabName)?.edges ?? []

      const edgeKeysToRemove: string[] = []

      patchRun(r => {
        const activeNodes = new Set(r.activeNodes)
        const doneNodes = new Set(r.doneNodes)
        const activeEdges = new Set(r.activeEdges)
        const logs = [...r.logs, ...group]

        for (const evt of group) {
          if (evt.event === 'node_start' && evt.node_id) {
            const nodeId = evt.node_id
            activeNodes.add(nodeId)
            // Nodos sin exec_in (ej: OnStart): emitir data edges salientes desde el inicio
            const hasExecIn = tabEdges.some(e => e.target === nodeId && (e.type === 'exec' || e.id?.startsWith('exec-')))
            if (!hasExecIn) {
              tabEdges
                .filter(e => e.source === nodeId && e.type !== 'exec' && !e.id?.startsWith('exec-'))
                .forEach(e => {
                  const k = `data:${e.source}-${e.target}`
                  activeEdges.add(k)
                  edgeKeysToRemove.push(k)
                })
            }
          }

          if (evt.event === 'node_done' && evt.node_id) {
            const nodeId = evt.node_id
            if (doneNodes.has(nodeId)) continue  // engine lo reporta tarde (padre esperando hijos)
            // Nodo que no tuvo node_start (ej: FlowOutput): flash breve como activo
            if (!activeNodes.has(nodeId)) activeNodes.add(nodeId)
            activeNodes.delete(nodeId)
            doneNodes.add(nodeId)
            // Data edges salientes de nodos con exec_in
            const hasExecIn = tabEdges.some(e => e.target === nodeId && (e.type === 'exec' || e.id?.startsWith('exec-')))
            if (hasExecIn) {
              tabEdges
                .filter(e => e.source === nodeId && e.type !== 'exec' && !e.id?.startsWith('exec-'))
                .forEach(e => {
                  const k = `data:${e.source}-${e.target}`
                  activeEdges.add(k)
                  edgeKeysToRemove.push(k)
                })
            }
          }

          if (evt.event === 'edge_fire' && evt.from && evt.to) {
            const isExec = evt.pin?.startsWith('exec') ?? true
            const k = `${isExec ? 'exec' : 'data'}:${evt.from}-${evt.to}`
            activeEdges.add(k)
            edgeKeysToRemove.push(k)
          }
        }

        return { logs, activeNodes, doneNodes, activeEdges }
      })

      // Limpiar edges activados en este grupo tras animMinMs
      if (edgeKeysToRemove.length > 0) {
        setTimeout(() => patchRun(r => ({
          activeEdges: new Set([...r.activeEdges].filter(k => !edgeKeysToRemove.includes(k))),
        })), animMinMs)
      }
    }

    // ─── Lectura del stream SSE ───────────────────────────────────────────────
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        let evt: RunEvent
        try {
          evt = JSON.parse(line.slice(6))
        } catch {
          continue
        }
        enqueue(evt)
      }
    }

    // Forzar flush del último grupo al cerrar el stream
    if (groupTimer !== null) {
      clearTimeout(groupTimer)
      flushGroup()
    }

    return runId
  }, [tabName, addRun, updateRun, animMinMs])

  const unload = useCallback(async () => {
    await unloadFlow(tabName)
    useFlowStore.setState(s => ({
      tabs: s.tabs.map(t => t.name !== tabName ? t : { ...t, loaded: false }),
    }))
  }, [tabName])

  return { startRun, unload }
}
