import { useCallback } from 'react'
import { useFlowStore, type Run, type RunEvent } from '@/store/flowStore'
import { loadFlow, unloadFlow, runFlowUrl } from '@/lib/api'

export function useRunStream(tabName: string) {
  const { addRun, updateRun, setLoaded, setDirty } = useFlowStore()

  const startRun = useCallback(async (
    inputs: Record<string, unknown>,
    opts: { dirty: boolean; loaded: boolean; onSave: () => Promise<void> }
  ) => {
    const needsSave = opts.dirty || !opts.loaded
    const needsLoad = opts.dirty || !opts.loaded

    if (needsSave) {
      await opts.onSave()
      setDirty(false)
    }

    if (needsLoad) {
      await loadFlow(tabName)
      setLoaded(true)
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

        useFlowStore.setState(s => ({
          tabs: s.tabs.map(t => {
            if (t.name !== tabName) return t
            const run = t.runs.find(r => r.runId === runId)
            if (!run) return t

            const updatedRun: Run = { ...run, logs: [...run.logs, evt] }

            if (evt.event === 'node_start' && evt.node_id) {
              updatedRun.activeNodes = new Set([...run.activeNodes, evt.node_id])
            }
            if (evt.event === 'node_done' && evt.node_id) {
              updatedRun.activeNodes = new Set([...run.activeNodes].filter(n => n !== evt.node_id))
              updatedRun.doneNodes = new Set([...run.doneNodes, evt.node_id])
            }
            if (evt.event === 'edge_fire' && evt.from && evt.to) {
              const edgeKey = `${evt.from}-${evt.to}`
              updatedRun.activeEdges = new Set([...run.activeEdges, edgeKey])
              setTimeout(() => {
                useFlowStore.setState(s2 => ({
                  tabs: s2.tabs.map(t2 => t2.name !== tabName ? t2 : {
                    ...t2,
                    runs: t2.runs.map(r => r.runId !== runId ? r : {
                      ...r,
                      activeEdges: new Set([...r.activeEdges].filter(e => e !== edgeKey)),
                    }),
                  }),
                }))
              }, 600)
            }
            if (evt.event === 'flow_done') {
              updatedRun.status = 'done'
              updatedRun.result = evt.outputs ?? (evt as unknown as Record<string, unknown>).result as Record<string, unknown>
              updatedRun.activeNodes = new Set()
              updatedRun.activeEdges = new Set()
            }
            if (evt.event === 'flow_error') {
              updatedRun.status = 'error'
              updatedRun.error = (evt as unknown as Record<string, unknown>).error as string
              updatedRun.activeNodes = new Set()
              updatedRun.activeEdges = new Set()
            }

            return { ...t, runs: t.runs.map(r => r.runId === runId ? updatedRun : r) }
          }),
        }))
      }
    }

    return runId
  }, [tabName, addRun, updateRun, setLoaded, setDirty])

  const unload = useCallback(async () => {
    await unloadFlow(tabName)
    useFlowStore.setState(s => ({
      tabs: s.tabs.map(t => t.name !== tabName ? t : { ...t, loaded: false }),
    }))
  }, [tabName])

  return { startRun, unload }
}
