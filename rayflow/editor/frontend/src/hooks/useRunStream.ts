import { useCallback, useEffect, useRef } from 'react'
import { useFlowStore, type Run, type RunEvent } from '@/store/flowStore'
import { unloadFlow, runFlowUrl, reconnectRunUrl } from '@/lib/api'

export function useRunStream(tabName: string) {
  const { addRun, updateRun } = useFlowStore()
  const animMinMs = useFlowStore(s => s.animMinMs)
  const animMinMsRef = useRef(animMinMs)
  useEffect(() => { animMinMsRef.current = animMinMs }, [animMinMs])
  const abortRef = useRef<(() => void) | null>(null)

  const startRun = useCallback(async (inputs: Record<string, unknown>) => {

    const controller = new AbortController()
    abortRef.current = controller.abort.bind(controller)

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
        signal: controller.signal,
      })
    } catch (e) {
      // Cancelación intencional — no marcar como error
      if ((e as Error).name === 'AbortError') return runId
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

    const patchRun = (patch: (run: Run) => Partial<Run>) => {
      useFlowStore.setState(s => ({
        tabs: s.tabs.map(t => t.name !== tabName || t.kind !== 'flow' ? t : {
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
        }, animMinMsRef.current)
        return
      }

      setTimeout(playNextGroup, animMinMsRef.current)
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
      const activeTab = useFlowStore.getState().tabs.find(t => t.name === tabName)
      const tabEdges = activeTab?.kind === 'flow' ? activeTab.edges : []

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
        })), animMinMsRef.current)
      }
    }

    // ─── Lectura del stream SSE ───────────────────────────────────────────────
    // backendRunId: recibido en el evento run_start, necesario para reconexión
    let backendRunId: string | null = null
    // terminalReceived: true si flow_done/flow_error llegó en el stream — no reconectar
    let terminalReceived = false

    const drainStream = async (r: ReadableStreamDefaultReader<Uint8Array>) => {
      let buf = ''
      while (true) {
        const { done, value } = await r.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let evt: RunEvent
          try { evt = JSON.parse(line.slice(6)) } catch { continue }
          if (evt.event === 'run_start') { backendRunId = evt.run_id ?? null; continue }
          if (evt.event === 'flow_done' || evt.event === 'flow_error') terminalReceived = true
          enqueue(evt)
        }
      }
    }

    try {
      await drainStream(reader)
    } catch {
      // stream roto — intentar reconexión si el run sigue activo y tenemos run_id
    }

    // Reconexión: solo si el stream se rompió antes de recibir el evento terminal
    const MAX_RECONNECT_ATTEMPTS = 5
    let attempt = 0
    while (
      !terminalReceived &&
      backendRunId !== null &&
      !controller.signal.aborted &&
      attempt < MAX_RECONNECT_ATTEMPTS
    ) {
      attempt++
      // Backoff lineal: 500ms, 1000ms, 1500ms...
      await new Promise(res => setTimeout(res, attempt * 500))
      if (controller.signal.aborted) break

      try {
        const reconnectResponse = await fetch(reconnectRunUrl(tabName, backendRunId), {
          signal: controller.signal,
        })
        if (!reconnectResponse.ok) break
        await drainStream(reconnectResponse.body!.getReader())
        if (terminalReceived) break
      } catch {
        // Reintento en el siguiente ciclo del while
      }
    }

    // Forzar flush del último grupo al cerrar el stream
    if (groupTimer !== null) {
      clearTimeout(groupTimer)
      flushGroup()
    }

    return runId
  }, [tabName, addRun, updateRun])

  const unload = useCallback(async () => {
    await unloadFlow(tabName)
    useFlowStore.setState(s => ({
      tabs: s.tabs.map(t => t.name !== tabName ? t : { ...t, loaded: false }),
    }))
  }, [tabName])

  const abort = useCallback(() => {
    abortRef.current?.()
    abortRef.current = null
  }, [])

  return { startRun, unload, abort }
}
