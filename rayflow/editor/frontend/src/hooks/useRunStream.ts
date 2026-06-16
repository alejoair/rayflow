import { useCallback } from 'react'
import { useFlowStore, type Run, type RunEvent } from '@/store/flowStore'
import { runFlow } from '@/lib/api'

export function useRunStream(tabName: string) {
  const { addRun, updateRun } = useFlowStore()

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

    try {
      // Por ahora: ejecución simple sin streaming (hasta que el backend soporte SSE)
      const result = await runFlow(tabName, inputs)
      updateRun(tabName, runId, {
        status: 'done',
        result,
        activeNodes: new Set(),
        activeEdges: new Set(),
      })
    } catch (e) {
      updateRun(tabName, runId, {
        status: 'error',
        error: (e as Error).message,
        activeNodes: new Set(),
        activeEdges: new Set(),
      })
    }

    return runId
  }, [tabName, addRun, updateRun])

  // Cuando el backend implemente SSE, reemplazar startRun con esta lógica:
  const startRunSSE = useCallback(async (inputs: Record<string, unknown>) => {
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

    const url = `/editor/flows/${encodeURIComponent(tabName)}/run/stream`
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(inputs),
    })

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
        const evt: RunEvent = JSON.parse(line.slice(6))

        useFlowStore.setState(s => ({
          tabs: s.tabs.map(t => {
            if (t.name !== tabName) return t
            const run = t.runs.find(r => r.runId === runId)
            if (!run) return t

            const updatedRun = { ...run, logs: [...run.logs, evt] }

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
                  tabs: s2.tabs.map(t2 => {
                    if (t2.name !== tabName) return t2
                    return {
                      ...t2,
                      runs: t2.runs.map(r => r.runId !== runId ? r : {
                        ...r,
                        activeEdges: new Set([...r.activeEdges].filter(e => e !== edgeKey)),
                      }),
                    }
                  }),
                }))
              }, 600)
            }
            if (evt.event === 'flow_done') {
              updatedRun.status = 'done'
              updatedRun.result = evt.outputs
              updatedRun.activeNodes = new Set()
              updatedRun.activeEdges = new Set()
            }
            if (evt.event === 'flow_error') {
              updatedRun.status = 'error'
              updatedRun.activeNodes = new Set()
              updatedRun.activeEdges = new Set()
            }

            return { ...t, runs: t.runs.map(r => r.runId === runId ? updatedRun : r) }
          }),
        }))
      }
    }

    return runId
  }, [tabName, addRun])

  return { startRun, startRunSSE }
}
