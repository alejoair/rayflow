import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { type Node, type Edge, applyNodeChanges, applyEdgeChanges, type NodeChange, type EdgeChange } from '@xyflow/react'
import type { FlowDef, FlowMeta, NodeSpec } from '@/lib/api'

export type RunStatus = 'idle' | 'running' | 'done' | 'error'

export interface RunEvent {
  event: string
  run_id?: string
  node_id?: string
  from?: string
  to?: string
  pin?: string
  outputs?: Record<string, unknown>
  ts: number
}

export interface Run {
  runId: string
  status: RunStatus
  activeNodes: Set<string>
  doneNodes: Set<string>
  activeEdges: Set<string>
  logs: RunEvent[]
  result?: Record<string, unknown>
  error?: string
  startedAt: number
  endedAt?: number
}

export interface FlowTab {
  kind: 'flow'
  name: string
  flowDef: FlowDef | null
  nodes: Node[]
  edges: Edge[]
  dirty: boolean
  loaded: boolean
  loadingIntoRay: boolean  // cargando en Ray en background
  stale: boolean           // cargado pero con cambios estructurales sin recargar
  validationErrors: string[]
  runs: Run[]
  activeRunId: string | null
}

export interface CodeTab {
  kind: 'code'
  name: string          // nombre del archivo sin .py
  source: string
  savedSource: string
}

export type Tab = FlowTab | CodeTab

interface FlowStore {
  catalog: Record<string, NodeSpec>
  setCatalog: (catalog: Record<string, NodeSpec>) => void

  flowList: FlowMeta[]
  setFlowList: (list: FlowMeta[]) => void

  animMinMs: number
  setAnimMinMs: (ms: number) => void

  tabs: Tab[]
  activeTabName: string | null

  openTab: (flowDef: FlowDef, nodes: Node[], edges: Edge[]) => void
  closeTab: (name: string) => void
  setActiveTab: (name: string) => void
  openCodeTab: (name: string, source: string) => void
  updateCodeSource: (name: string, source: string) => void
  markCodeSaved: (name: string) => void

  onNodesChange: (changes: NodeChange[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  setNodes: (nodes: Node[]) => void
  setEdges: (edges: Edge[]) => void
  setDirty: (dirty: boolean) => void
  setLoaded: (loaded: boolean) => void
  setLoadingIntoRay: (loading: boolean) => void
  setStale: (stale: boolean) => void
  setValidationErrors: (errors: string[]) => void
  updateVariables: (vars: FlowDef['variables']) => void

  addRun: (tabName: string, run: Run) => void
  updateRun: (tabName: string, runId: string, patch: Partial<Run>) => void
  setActiveRun: (tabName: string, runId: string | null) => void
}

// Set no es serializable en JSON — lo convertimos a array al guardar y lo restauramos al cargar
function serializeRun(run: Run): unknown {
  return {
    ...run,
    activeNodes: [...run.activeNodes],
    doneNodes: [...run.doneNodes],
    activeEdges: [...run.activeEdges],
  }
}

function deserializeRun(raw: Record<string, unknown>): Run {
  return {
    ...raw,
    activeNodes: new Set(raw.activeNodes as string[]),
    doneNodes: new Set(raw.doneNodes as string[]),
    activeEdges: new Set(raw.activeEdges as string[]),
  } as Run
}

// Storage custom que convierte Sets a arrays al guardar y los restaura al leer
const setAwareStorage = {
  getItem: (name: string) => {
    const raw = localStorage.getItem(name)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed?.state?.tabs) {
      parsed.state.tabs = parsed.state.tabs.map((tab: Record<string, unknown>) => ({
        ...tab,
        runs: (tab.runs as Record<string, unknown>[]).map(deserializeRun),
      }))
    }
    return parsed
  },
  setItem: (name: string, value: unknown) => {
    const v = value as { state: { tabs: Tab[] } }
    const serialized = {
      ...v,
      state: {
        ...v.state,
        tabs: v.state.tabs.map(tab =>
          tab.kind === 'flow'
            ? { ...tab, runs: tab.runs.map(serializeRun) }
            : tab
        ),
      },
    }
    localStorage.setItem(name, JSON.stringify(serialized))
  },
  removeItem: (name: string) => localStorage.removeItem(name),
}

export const useFlowStore = create<FlowStore>()(
  persist(
    (set, get) => ({
      catalog: {},
      setCatalog: (catalog) => set({ catalog }),

      flowList: [],
      setFlowList: (flowList) => set({ flowList }),

      animMinMs: 600,
      setAnimMinMs: (animMinMs) => set({ animMinMs }),

      tabs: [],
      activeTabName: null,

      openTab: (flowDef, nodes, edges) => {
        const existing = get().tabs.find(t => t.name === flowDef.name)
        if (existing) { set({ activeTabName: flowDef.name }); return }
        const tab: FlowTab = {
          kind: 'flow',
          name: flowDef.name, flowDef, nodes, edges,
          dirty: false, loaded: false, loadingIntoRay: false, stale: false,
          validationErrors: [], runs: [], activeRunId: null,
        }
        set(s => ({ tabs: [...s.tabs, tab], activeTabName: flowDef.name }))
      },

      closeTab: (name) => {
        set(s => {
          const tabs = s.tabs.filter(t => t.name !== name)
          const activeTabName = s.activeTabName === name
            ? (tabs[tabs.length - 1]?.name ?? null)
            : s.activeTabName
          return { tabs, activeTabName }
        })
      },

      setActiveTab: (name) => set({ activeTabName: name }),

      openCodeTab: (name, source) => {
        const existing = get().tabs.find(t => t.name === name && t.kind === 'code')
        if (existing) { set({ activeTabName: name }); return }
        const tab: CodeTab = { kind: 'code', name, source, savedSource: source }
        set(s => ({ tabs: [...s.tabs, tab], activeTabName: name }))
      },

      updateCodeSource: (name, source) => {
        set(s => ({
          tabs: s.tabs.map(t => t.name === name && t.kind === 'code' ? { ...t, source } : t),
        }))
      },

      markCodeSaved: (name) => {
        set(s => ({
          tabs: s.tabs.map(t => t.name === name && t.kind === 'code' ? { ...t, savedSource: t.source } : t),
        }))
      },

      onNodesChange: (changes) => {
        const name = get().activeTabName
        if (!name) return
        const isStructural = changes.some(c => c.type !== 'position' && c.type !== 'select' && c.type !== 'dimensions')
        set(s => ({
          tabs: s.tabs.map(t => {
            if (t.name !== name || t.kind !== 'flow') return t
            const stale = isStructural && t.loaded ? true : t.stale
            return { ...t, nodes: applyNodeChanges(changes, t.nodes), dirty: isStructural ? true : t.dirty, stale }
          }),
        }))
      },

      onEdgesChange: (changes) => {
        const name = get().activeTabName
        if (!name) return
        const isStructural = changes.some(c => c.type !== 'select')
        set(s => ({
          tabs: s.tabs.map(t => {
            if (t.name !== name || t.kind !== 'flow') return t
            const stale = isStructural && t.loaded ? true : t.stale
            return { ...t, edges: applyEdgeChanges(changes, t.edges), dirty: true, stale }
          }),
        }))
      },

      setNodes: (nodes) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({ tabs: s.tabs.map(t => t.name !== name || t.kind !== 'flow' ? t : { ...t, nodes }) }))
      },

      setEdges: (edges) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({ tabs: s.tabs.map(t => t.name !== name || t.kind !== 'flow' ? t : { ...t, edges }) }))
      },

      setDirty: (dirty) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({
          tabs: s.tabs.map(t => {
            if (t.name !== name || t.kind !== 'flow') return t
            const stale = dirty && t.loaded ? true : dirty ? t.stale : false
            return { ...t, dirty, stale }
          }),
        }))
      },

      setLoaded: (loaded) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({ tabs: s.tabs.map(t => t.name !== name || t.kind !== 'flow' ? t : { ...t, loaded }) }))
      },

      setLoadingIntoRay: (loadingIntoRay) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({ tabs: s.tabs.map(t => t.name !== name || t.kind !== 'flow' ? t : { ...t, loadingIntoRay }) }))
      },

      setStale: (stale) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({ tabs: s.tabs.map(t => t.name !== name || t.kind !== 'flow' ? t : { ...t, stale }) }))
      },

      updateVariables: (vars) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({
          tabs: s.tabs.map(t => t.name !== name || t.kind !== 'flow' ? t : {
            ...t,
            flowDef: t.flowDef ? { ...t.flowDef, variables: vars } : t.flowDef,
            dirty: true,
          }),
        }))
      },

      setValidationErrors: (errors) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({ tabs: s.tabs.map(t => t.name !== name || t.kind !== 'flow' ? t : { ...t, validationErrors: errors }) }))
      },

      addRun: (tabName, run) => {
        set(s => ({
          tabs: s.tabs.map(t => t.name !== tabName || t.kind !== 'flow' ? t : {
            ...t, runs: [...t.runs, run], activeRunId: run.runId,
          }),
        }))
      },

      updateRun: (tabName, runId, patch) => {
        set(s => ({
          tabs: s.tabs.map(t => t.name !== tabName || t.kind !== 'flow' ? t : {
            ...t, runs: t.runs.map(r => r.runId !== runId ? r : { ...r, ...patch }),
          }),
        }))
      },

      setActiveRun: (tabName, runId) => {
        set(s => ({
          tabs: s.tabs.map(t => t.name !== tabName || t.kind !== 'flow' ? t : { ...t, activeRunId: runId }),
        }))
      },
    }),
    {
      name: 'rayflow-ui-state',  // sobrescrito por initWorkspaceStore() al arrancar
      storage: setAwareStorage,
      // Solo persistimos tabs y qué tab está activa; catalog y flowList se recargan del servidor
      partialize: (state) => ({
        // Los code tabs no se persisten — el source siempre se carga fresco del backend
        tabs: state.tabs.filter(t => t.kind === 'flow'),
        activeTabName: state.tabs.find(t => t.name === state.activeTabName)?.kind === 'flow'
          ? state.activeTabName
          : null,
        animMinMs: state.animMinMs,
      }),
      // Al rehidratar, los Sets dentro de los runs vienen como arrays — los convertimos de vuelta
      onRehydrateStorage: () => (state) => {
        if (!state) return
        state.tabs = state.tabs.map(tab => {
          if (tab.kind === 'code') return tab
          return {
            ...tab,
            kind: 'flow' as const,
            loaded: false,
            loadingIntoRay: false,
            stale: false,
            runs: tab.runs
              .filter(r => r.status !== 'running')
              .map(r => deserializeRun(r as unknown as Record<string, unknown>)),
          }
        })
      },
    }
  )
)

/** Selector puro — devuelve el tab activo solo si es de tipo flow. */
export const selectActiveTab = (s: FlowStore): FlowTab | null => {
  const t = s.tabs.find(t => t.name === s.activeTabName)
  return t?.kind === 'flow' ? t : null
}

/** Devuelve el tab activo independientemente del tipo. */
export const selectActiveTabAny = (s: FlowStore): Tab | null =>
  s.tabs.find(t => t.name === s.activeTabName) ?? null

/**
 * Cambia la clave de localStorage al namespace del workspace activo y rehidrata.
 * Llamar una vez al arrancar, después de obtener el cwd del servidor.
 *
 * Cada workspace usa su propia clave: "rayflow-ws-<hash(cwd)>"
 * así los tabs/animMinMs de carpetas distintas nunca se mezclan.
 */
export function initWorkspaceStore(cwd: string): void {
  // Hash simple pero suficiente para distinguir rutas
  let hash = 0
  for (let i = 0; i < cwd.length; i++) {
    hash = ((hash << 5) - hash + cwd.charCodeAt(i)) | 0
  }
  const key = `rayflow-ws-${Math.abs(hash).toString(36)}`
  useFlowStore.persist.setOptions({ name: key })
  useFlowStore.persist.rehydrate()
}
