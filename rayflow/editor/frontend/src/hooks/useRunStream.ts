import { useCallback } from 'react'
import { useFlowStore, type Run, type RunEvent } from '@/store/flowStore'
import { loadFlow, unloadFlow, runFlowUrl } from '@/lib/api'

export function useRunStream(tabName: string) {
  const { addRun, updateRun, setLoaded, setDirty, animMinMs } = useFlowStore()

  const startRun = useCallback(async (
    inputs: Record<string, unknown>,
    opts: { dirty: boolean; loaded: boolean; onSave: () => Promise<void> }
  ) => {
    const needsSave = opts.dirty || !opts.loaded
    const needsLoad = opts.dirty || !opts.loaded

    console.log('[run] dirty=%s loaded=%s → needsSave=%s needsLoad=%s', opts.dirty, opts.loaded, needsSave, needsLoad)

    if (needsSave) {
      console.log('[run] saving flow...')
      await opts.onSave()
      setDirty(false)
      console.log('[run] saved')
    }

    if (needsLoad) {
      console.log('[run] loading flow into Ray...')
      await loadFlow(tabName)
      setLoaded(true)
      console.log('[run] loaded')
    }

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
    console.log('[run] POST', url, inputs)
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

    console.log('[run] response status', response.status, response.headers.get('content-type'))

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: response.statusText }))
      console.error('[run] error response', err)
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

    // Cola de eventos recibidos del servidor
    const eventQueue: RunEvent[] = []
    let playing = false

    // Reproduce la cola secuencialmente: cada evento significativo espera animMinMs
    // antes de aplicar el siguiente. Así la ejecución siempre se ve paso a paso.
    const playNext = () => {
      if (eventQueue.length === 0) { playing = false; return }
      playing = true
      const evt = eventQueue.shift()!

      console.log('[SSE queue]', evt)
      patchRun(r => ({ logs: [...r.logs, evt] }))

      if (evt.event === 'node_start' && evt.node_id) {
        const nodeId = evt.node_id
        patchRun(r => ({ activeNodes: new Set([...r.activeNodes, nodeId]) }))
        setTimeout(playNext, animMinMs)

      } else if (evt.event === 'node_done' && evt.node_id) {
        const nodeId = evt.node_id
        const currentRun = useFlowStore.getState().tabs.find(t => t.name === tabName)
          ?.runs.find(r => r.runId === runId)

        // Si el nodo ya está en doneNodes, el engine lo reporta tarde (padre que espera hijos)
        // No lo re-animamos, simplemente pasamos al siguiente evento
        if (currentRun?.doneNodes.has(nodeId)) {
          playNext()
          return
        }

        // Activar data edges salientes
        const tabEdges = useFlowStore.getState().tabs.find(t => t.name === tabName)?.edges ?? []
        const dataEdgeKeys = tabEdges
          .filter(e => e.source === nodeId && e.type !== 'exec' && !e.id?.startsWith('exec-'))
          .map(e => `data:${e.source}-${e.target}`)

        // Si el nodo no tuvo node_start (ej: FlowOutput), lo animamos brevemente como activo antes de done
        const needsStart = !currentRun?.activeNodes.has(nodeId)
        if (needsStart) {
          patchRun(r => ({ activeNodes: new Set([...r.activeNodes, nodeId]) }))
        }

        setTimeout(() => {
          patchRun(r => ({
            activeNodes: new Set([...r.activeNodes].filter(n => n !== nodeId)),
            doneNodes: new Set([...r.doneNodes, nodeId]),
            activeEdges: dataEdgeKeys.length > 0 ? new Set([...r.activeEdges, ...dataEdgeKeys]) : r.activeEdges,
          }))
          if (dataEdgeKeys.length > 0) {
            setTimeout(() => patchRun(r => ({
              activeEdges: new Set([...r.activeEdges].filter(k => !dataEdgeKeys.includes(k))),
            })), animMinMs)
          }
          setTimeout(playNext, animMinMs)
        }, needsStart ? animMinMs : 0)

      } else if (evt.event === 'edge_fire' && evt.from && evt.to) {
        const isExec = evt.pin?.startsWith('exec') ?? true
        const edgeKey = `${isExec ? 'exec' : 'data'}:${evt.from}-${evt.to}`
        patchRun(r => ({ activeEdges: new Set([...r.activeEdges, edgeKey]) }))
        setTimeout(() => {
          patchRun(r => ({
            activeEdges: new Set([...r.activeEdges].filter(e => e !== edgeKey)),
          }))
          playNext()
        }, animMinMs)

      } else if (evt.event === 'flow_done') {
        const result = evt.outputs ?? (evt as unknown as Record<string, unknown>).result as Record<string, unknown>
        patchRun(() => ({
          status: 'done',
          result,
          activeNodes: new Set(),
          activeEdges: new Set(),
        }))
        playing = false

      } else if (evt.event === 'flow_error') {
        const error = (evt as unknown as Record<string, unknown>).error as string
        patchRun(() => ({
          status: 'error',
          error,
          activeNodes: new Set(),
          activeEdges: new Set(),
        }))
        playing = false

      } else {
        // evento desconocido — pasar inmediatamente al siguiente
        playNext()
      }
    }

    const enqueue = (evt: RunEvent) => {
      eventQueue.push(evt)
      if (!playing) playNext()
    }

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
        console.log('[SSE]', evt)
        enqueue(evt)
      }
    }

    return runId
  }, [tabName, addRun, updateRun, setLoaded, setDirty, animMinMs])

  const unload = useCallback(async () => {
    await unloadFlow(tabName)
    useFlowStore.setState(s => ({
      tabs: s.tabs.map(t => t.name !== tabName ? t : { ...t, loaded: false }),
    }))
  }, [tabName])

  return { startRun, unload }
}
