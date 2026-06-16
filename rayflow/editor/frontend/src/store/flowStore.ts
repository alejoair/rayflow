import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { type Node, type Edge, applyNodeChanges, applyEdgeChanges, type NodeChange, type EdgeChange } from '@xyflow/react'
import type { FlowDef, FlowMeta, NodeSpec } from '@/lib/api'

export type RunStatus = 'idle' | 'running' | 'done' | 'error'

export interface RunEvent {
  event: string
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
}

export interface FlowTab {
  name: string
  flowDef: FlowDef | null
  nodes: Node[]
  edges: Edge[]
  dirty: boolean
  validationErrors: string[]
  runs: Run[]
  activeRunId: string | null
}

interface FlowStore {
  catalog: Record<string, NodeSpec>
  setCatalog: (catalog: Record<string, NodeSpec>) => void

  flowList: FlowMeta[]
  setFlowList: (list: FlowMeta[]) => void

  tabs: FlowTab[]
  activeTabName: string | null

  openTab: (flowDef: FlowDef, nodes: Node[], edges: Edge[]) => void
  closeTab: (name: string) => void
  setActiveTab: (name: string) => void

  onNodesChange: (changes: NodeChange[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  setNodes: (nodes: Node[]) => void
  setEdges: (edges: Edge[]) => void
  setDirty: (dirty: boolean) => void
  setValidationErrors: (errors: string[]) => void

  addRun: (tabName: string, run: Run) => void
  updateRun: (tabName: string, runId: string, patch: Partial<Run>) => void
  setActiveRun: (tabName: string, runId: string | null) => void

  getActiveTab: () => FlowTab | null
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
    const v = value as { state: { tabs: FlowTab[] } }
    const serialized = {
      ...v,
      state: {
        ...v.state,
        tabs: v.state.tabs.map(tab => ({
          ...tab,
          runs: tab.runs.map(serializeRun),
        })),
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

      tabs: [],
      activeTabName: null,

      openTab: (flowDef, nodes, edges) => {
        const existing = get().tabs.find(t => t.name === flowDef.name)
        if (existing) { set({ activeTabName: flowDef.name }); return }
        const tab: FlowTab = {
          name: flowDef.name, flowDef, nodes, edges,
          dirty: false, validationErrors: [], runs: [], activeRunId: null,
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

      onNodesChange: (changes) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({
          tabs: s.tabs.map(t => t.name !== name ? t : {
            ...t, nodes: applyNodeChanges(changes, t.nodes), dirty: true,
          }),
        }))
      },

      onEdgesChange: (changes) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({
          tabs: s.tabs.map(t => t.name !== name ? t : {
            ...t, edges: applyEdgeChanges(changes, t.edges), dirty: true,
          }),
        }))
      },

      setNodes: (nodes) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({ tabs: s.tabs.map(t => t.name !== name ? t : { ...t, nodes }) }))
      },

      setEdges: (edges) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({ tabs: s.tabs.map(t => t.name !== name ? t : { ...t, edges }) }))
      },

      setDirty: (dirty) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({ tabs: s.tabs.map(t => t.name !== name ? t : { ...t, dirty }) }))
      },

      setValidationErrors: (errors) => {
        const name = get().activeTabName
        if (!name) return
        set(s => ({ tabs: s.tabs.map(t => t.name !== name ? t : { ...t, validationErrors: errors }) }))
      },

      addRun: (tabName, run) => {
        set(s => ({
          tabs: s.tabs.map(t => t.name !== tabName ? t : {
            ...t, runs: [...t.runs, run], activeRunId: run.runId,
          }),
        }))
      },

      updateRun: (tabName, runId, patch) => {
        set(s => ({
          tabs: s.tabs.map(t => t.name !== tabName ? t : {
            ...t, runs: t.runs.map(r => r.runId !== runId ? r : { ...r, ...patch }),
          }),
        }))
      },

      setActiveRun: (tabName, runId) => {
        set(s => ({
          tabs: s.tabs.map(t => t.name !== tabName ? t : { ...t, activeRunId: runId }),
        }))
      },

      getActiveTab: () => {
        const { tabs, activeTabName } = get()
        return tabs.find(t => t.name === activeTabName) ?? null
      },
    }),
    {
      name: 'rayflow-ui-state',
      storage: setAwareStorage,
      // Solo persistimos tabs y qué tab está activa; catalog y flowList se recargan del servidor
      partialize: (state) => ({
        tabs: state.tabs,
        activeTabName: state.activeTabName,
      }),
      // Al rehidratar, los Sets dentro de los runs vienen como arrays — los convertimos de vuelta
      onRehydrateStorage: () => (state) => {
        if (!state) return
        state.tabs = state.tabs.map(tab => ({
          ...tab,
          // Descarta runs en vuelo al recargar (status running no tiene sentido tras recarga)
          runs: tab.runs
            .filter(r => r.status !== 'running')
            .map(r => deserializeRun(r as unknown as Record<string, unknown>)),
        }))
      },
    }
  )
)
