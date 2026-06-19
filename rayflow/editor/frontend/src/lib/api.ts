async function apiFetch<T>(url: string, opts: RequestInit = {}): Promise<T> {
  const r = await fetch(url, opts)
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  if (r.status === 204) return null as T
  return r.json()
}

const json = (body: unknown) => ({
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export interface PinSpec {
  name: string
  kind: 'input' | 'output' | 'exec_input' | 'exec_output'
  type: string
  required: boolean
  default?: unknown
}

export interface NodeSpec {
  type: string
  decorator: string
  is_exec_node: boolean
  has_exec_in: boolean
  exec_outputs: string[]
  inputs: PinSpec[]
  outputs: PinSpec[]
}

export interface FlowMeta {
  name: string
  version: string
  inputs: Record<string, string>
  outputs: Record<string, string>
}

export interface FlowDef extends FlowMeta {
  variables: { name: string; type: string; default: unknown }[]
  events: string[]
  nodes: NodeDef[]
}

export interface NodeDef {
  id: string
  type: string
  exec_in?: string | string[] | { or: string[] }
  inputs?: Record<string, unknown>
  ui?: { x: number; y: number }
}

export interface ValidationResult {
  valid: boolean
  errors: string[]
}

export interface RunEvent {
  event: 'run_start' | 'node_start' | 'node_done' | 'edge_fire' | 'flow_done' | 'flow_error'
  run_id?: string
  node_id?: string
  from?: string
  to?: string
  pin?: string
  outputs?: Record<string, unknown>
  ts: number
}

export const getEditorInfo = () => apiFetch<{ cwd: string }>('/editor/info')
export const getNodes = () => apiFetch<NodeSpec[]>('/editor/nodes')
export const getFlows = () => apiFetch<{ flows: FlowMeta[] }>('/editor/flows')
export const getFlow = (name: string) => apiFetch<FlowDef>(`/editor/flows/${encodeURIComponent(name)}`)
export const createFlow = (body: FlowDef) => apiFetch<FlowDef>('/editor/flows', { method: 'POST', ...json(body) })
export const updateFlow = (name: string, body: FlowDef) => apiFetch<FlowDef>(`/editor/flows/${encodeURIComponent(name)}`, { method: 'PUT', ...json(body) })
export const deleteFlow = (name: string) => apiFetch<null>(`/editor/flows/${encodeURIComponent(name)}`, { method: 'DELETE' })
export const validateFlow = (body: FlowDef) => apiFetch<ValidationResult>('/editor/validate', { method: 'POST', ...json(body) })
export const typeCheck = (from_type: string, to_type: string) => apiFetch<{ compatible: boolean }>('/editor/type-check', { method: 'POST', ...json({ from_type, to_type }) })
export const loadFlow = (name: string) => apiFetch<{ graph_id: string; flow: string; loaded: boolean }>(`/editor/flows/${encodeURIComponent(name)}/load`, { method: 'POST' })
export const unloadFlow = (name: string) => apiFetch<{ flow: string; loaded: boolean }>(`/editor/flows/${encodeURIComponent(name)}/load`, { method: 'DELETE' })
export const flowLoadedStatus = (name: string) => apiFetch<{ flow: string; loaded: boolean }>(`/editor/flows/${encodeURIComponent(name)}/loaded`)

// runFlow devuelve un ReadableStream SSE — se consume en useRunStream
export const runFlowUrl = (name: string) => `/editor/flows/${encodeURIComponent(name)}/run`
export const reconnectRunUrl = (name: string, runId: string) => `/editor/flows/${encodeURIComponent(name)}/run/${encodeURIComponent(runId)}/stream`

// Custom nodes
export interface CustomNodeFile {
  name: string
  filename: string
  size: number
}

export const listCustomNodes = () => apiFetch<CustomNodeFile[]>('/editor/custom-nodes')
export const getCustomNodeSource = (name: string) => apiFetch<{ name: string; source: string }>(`/editor/custom-nodes/${encodeURIComponent(name)}/source`)
export const createCustomNode = (name: string, source?: string) => apiFetch<{ name: string; created: boolean; custom_nodes: string[] }>('/editor/custom-nodes', { method: 'POST', ...json({ name, source }) })
export const updateCustomNodeSource = (name: string, source: string) => apiFetch<{ name: string; saved: boolean; custom_nodes: string[] }>(`/editor/custom-nodes/${encodeURIComponent(name)}/source`, { method: 'PUT', ...json({ source }) })
export const deleteCustomNode = (name: string) => apiFetch<null>(`/editor/custom-nodes/${encodeURIComponent(name)}`, { method: 'DELETE' })
export const reloadCustomNodes = () => apiFetch<{ reloaded: boolean; custom_nodes: string[] }>('/editor/custom-nodes/reload', { method: 'POST' })
