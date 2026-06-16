import { useEffect, useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useFlowStore } from '@/store/flowStore'
import { getNodes, getFlows, getFlow, createFlow, deleteFlow, updateFlow, validateFlow } from '@/lib/api'
import { flowDefToRF, rfToFlowDef } from '@/lib/translator'
import NodePalette from '@/components/NodePalette'
import FlowCanvas from '@/components/FlowCanvas'
import PropertiesPanel from '@/components/PropertiesPanel'
import RunsPanel from '@/components/RunsPanel'
import FlowSettingsDialog from '@/components/FlowSettingsDialog'
import VariablesPanel from '@/components/VariablesPanel'
import CustomNodesPanel from '@/components/CustomNodesPanel'
import type { FlowDef } from '@/lib/api'

interface Toast { id: number; msg: string; type: 'info' | 'success' | 'error' }

function NewFlowDialog({ onClose, onCreate }: { onClose: () => void; onCreate: (flow: FlowDef) => void }) {
  const [name, setName] = useState('')
  const [err, setErr] = useState('')

  async function handleCreate() {
    setErr('')
    if (!name.trim()) { setErr('El nombre es requerido'); return }
    try {
      const flow = await createFlow({ name: name.trim(), version: '1', inputs: {}, outputs: {}, variables: [], events: [], nodes: [] })
      onCreate(flow)
      onClose()
    } catch (e) { setErr((e as Error).message) }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-[var(--card)] border-[var(--border)] text-[var(--foreground)]">
        <DialogHeader>
          <DialogTitle>Nuevo flow</DialogTitle>
        </DialogHeader>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, color: 'var(--muted-foreground)' }}>Nombre</label>
            <Input
              autoFocus value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleCreate() }}
              placeholder="mi_flow"
              style={{ fontSize: 13 }}
              className="bg-[var(--secondary)] border-[var(--border)]"
            />
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted-foreground)' }}>
            Los inputs y outputs se configuran después con ⚙ Flow settings.
          </div>
          {err && <div style={{ fontSize: 12, color: '#fca5a5' }}>{err}</div>}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} style={{ fontSize: 13 }}>Cancelar</Button>
          <Button onClick={handleCreate} style={{ fontSize: 13 }}>Crear</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function App() {
  const {
    catalog, setCatalog,
    flowList, setFlowList,
    tabs, activeTabName,
    openTab, closeTab, setActiveTab,
    setNodes, setEdges, setDirty, setValidationErrors,
    updateVariables,
    getActiveTab,
  } = useFlowStore()

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])

  const refreshCatalog = useCallback(() => {
    getNodes()
      .then(list => {
        const m: Record<string, typeof list[0]> = {}
        list.forEach(n => { m[n.type] = n })
        setCatalog(m)
        // Actualizar meta de nodos en tabs ya abiertas (rehidratadas desde localStorage)
        useFlowStore.setState(s => ({
          tabs: s.tabs.map(tab => {
            if (!tab.flowDef) return tab
            const fiMeta = {
              ...(m['OnStart'] ?? { type: 'OnStart', decorator: 'engine_node', is_exec_node: true, has_exec_in: false, has_exec_out: true, is_parallel: false, exec_outputs: ['exec_out'] }),
              outputs: Object.entries(tab.flowDef.inputs || {}).map(([name, type]) => ({ name, type, kind: 'output' as const, required: false })),
              inputs: [],
            }
            const foMeta = {
              ...(m['FlowOutput'] ?? { type: 'FlowOutput', decorator: 'engine_node', is_exec_node: true, has_exec_in: true, has_exec_out: false, is_parallel: false, exec_outputs: [] }),
              inputs: Object.entries(tab.flowDef.outputs || {}).map(([name, type]) => ({ name, type, kind: 'input' as const, required: false })),
              outputs: [],
            }
            return {
              ...tab,
              nodes: tab.nodes.map(n => {
                const nodeType = (n.data as { nodeType: string }).nodeType
                if (nodeType === 'OnStart') return { ...n, data: { ...n.data, meta: fiMeta } }
                if (nodeType === 'FlowOutput') return { ...n, data: { ...n.data, meta: foMeta } }
                return { ...n, data: { ...n.data, meta: m[nodeType] ?? (n.data as { meta: unknown }).meta } }
              }),
            }
          }),
        }))
      })
      .catch(console.error)
  }, [setCatalog])

  useEffect(() => {
    refreshCatalog()
    getFlows()
      .then(data => setFlowList(data.flows || []))
      .catch(console.error)
  }, [])

  function addToast(msg: string, type: Toast['type'] = 'info') {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev, { id, msg, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3500)
  }

  async function handleOpenFlow(name: string) {
    if (!name) return
    const existing = tabs.find(t => t.name === name)
    if (existing) { setActiveTab(name); return }
    try {
      const data = await getFlow(name)
      const { nodes, edges } = flowDefToRF(data, catalog)
      openTab(data, nodes, edges)
    } catch (e) { addToast(`Error abriendo: ${(e as Error).message}`, 'error') }
  }

  async function handleSave() {
    const tab = getActiveTab()
    if (!tab?.flowDef) return
    setSaving(true)
    try {
      const flowDef = rfToFlowDef(tab.nodes, tab.edges, {
        name: tab.flowDef.name,
        version: tab.flowDef.version || '1',
        inputs: tab.flowDef.inputs || {},
        outputs: tab.flowDef.outputs || {},
        variables: tab.flowDef.variables || [],
        events: tab.flowDef.events || [],
      })
      await updateFlow(tab.name, flowDef)
      setDirty(false)
      addToast('Flow guardado', 'success')
    } catch (e) { addToast(`Error guardando: ${(e as Error).message}`, 'error') }
    finally { setSaving(false) }
  }

  async function handleValidate() {
    const tab = getActiveTab()
    if (!tab?.flowDef) return
    try {
      const flowDef = rfToFlowDef(tab.nodes, tab.edges, {
        name: tab.flowDef.name, version: tab.flowDef.version || '1',
        inputs: tab.flowDef.inputs || {}, outputs: tab.flowDef.outputs || {},
        variables: tab.flowDef.variables || [], events: tab.flowDef.events || [],
      })
      const result = await validateFlow(flowDef)
      setValidationErrors(result.errors || [])
      if (result.valid) addToast('Flow válido ✓', 'success')
      else addToast(`${result.errors.length} error(es)`, 'error')
    } catch (e) { addToast(`Error validando: ${(e as Error).message}`, 'error') }
  }

  function handleSaveSettings(inputs: Record<string, string>, outputs: Record<string, string>) {
    const tab = getActiveTab()
    if (!tab?.flowDef) return
    const prevInputNames = new Set(Object.keys(tab.flowDef.inputs || {}))
    const removed = [...prevInputNames].filter(n => !Object.keys(inputs).includes(n))

    // Meta sintética para FlowInput y FlowOutput con los nuevos pines
    const newFlowInputMeta = {
      ...(catalog['OnStart'] ?? { type: 'OnStart', decorator: 'engine_node', is_exec_node: true, has_exec_in: false, has_exec_out: true, is_parallel: false, exec_outputs: ['exec_out'] }),
      outputs: Object.entries(inputs).map(([name, type]) => ({ name, type, kind: 'output' as const, required: false })),
      inputs: [],
    }
    const newFlowOutputMeta = {
      ...(catalog['FlowOutput'] ?? { type: 'FlowOutput', decorator: 'engine_node', is_exec_node: true, has_exec_in: true, has_exec_out: false, is_parallel: false, exec_outputs: [] }),
      inputs: Object.entries(outputs).map(([name, type]) => ({ name, type, kind: 'input' as const, required: false })),
      outputs: [],
    }

    useFlowStore.setState(s => ({
      tabs: s.tabs.map(t => t.name !== tab.name ? t : {
        ...t,
        flowDef: { ...t.flowDef!, inputs, outputs },
        // Actualiza la meta de FlowInput/FlowOutput en los nodos del canvas
        nodes: t.nodes.map(n => {
          const nodeType = (n.data as { nodeType: string }).nodeType
          if (nodeType === 'OnStart') return { ...n, data: { ...n.data, meta: newFlowInputMeta } }
          if (nodeType === 'FlowOutput') return { ...n, data: { ...n.data, meta: newFlowOutputMeta } }
          return n
        }),
        dirty: true,
      }),
    }))

    if (removed.length) {
      addToast(`Inputs eliminados: ${removed.join(', ')} — revisa conexiones huérfanas`, 'info')
    } else {
      addToast('Flow settings guardados', 'success')
    }
  }

  async function handleDelete() {
    const tab = getActiveTab()
    if (!tab) return
    if (!confirm(`¿Borrar "${tab.name}"?`)) return
    try {
      await deleteFlow(tab.name)
      closeTab(tab.name)
      setFlowList(flowList.filter(f => f.name !== tab.name))
      addToast('Flow eliminado', 'info')
    } catch (e) { addToast(`Error borrando: ${(e as Error).message}`, 'error') }
  }

  const handleUpdateNode = useCallback((nodeId: string, update: Record<string, unknown>) => {
    const tab = useFlowStore.getState().getActiveTab()
    if (!tab) return
    if (update.newId) {
      const newId = update.newId as string
      setNodes(tab.nodes.map(n => n.id === nodeId ? { ...n, id: newId } : n))
      setEdges(tab.edges.map(e => ({
        ...e,
        source: e.source === nodeId ? newId : e.source,
        target: e.target === nodeId ? newId : e.target,
        id: e.id.replace(new RegExp(`\\b${nodeId}\\b`), newId),
      })))
      setSelectedNodeId(newId)
      return
    }
    setNodes(tab.nodes.map(n => n.id === nodeId ? { ...n, data: { ...n.data, ...update } } : n))
    setDirty(true)
  }, [setNodes, setEdges, setDirty])

  const tab = getActiveTab()
  const validStatus = !tab ? 'unknown' : tab.validationErrors.length === 0 ? 'valid' : 'invalid'

  return (
    <div className="flex flex-col h-screen bg-[var(--background)] text-[var(--foreground)]">

      {/* Header */}
      <header style={{
        height: 48,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '0 16px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--card)',
        flexShrink: 0,
        zIndex: 10,
      }}>
        <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--primary)', marginRight: 4 }}>Rayflow</span>
        <div style={{ width: 1, height: 24, background: 'var(--border)' }} />

        <Select onValueChange={handleOpenFlow}>
          <SelectTrigger style={{ height: 32, width: 180, fontSize: 13 }} className="bg-[var(--secondary)] border-[var(--border)]">
            <SelectValue placeholder="Abrir flow…" />
          </SelectTrigger>
          <SelectContent className="bg-[var(--card)] border-[var(--border)]">
            {flowList.map(f => (
              <SelectItem key={f.name} value={f.name} style={{ fontSize: 13 }}>{f.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button size="sm" variant="outline" onClick={() => setShowNew(true)}
          style={{ height: 32, fontSize: 13, padding: '0 12px' }}>
          + Nuevo
        </Button>
        <div style={{ width: 1, height: 24, background: 'var(--border)' }} />

        {tab && (<>
          <Button size="sm" onClick={handleSave} disabled={saving}
            style={{ height: 32, fontSize: 13, padding: '0 12px' }}>
            {saving ? 'Guardando…' : '💾 Guardar'}
          </Button>
          <Button size="sm" variant="outline" onClick={handleValidate}
            style={{ height: 32, fontSize: 13, padding: '0 12px' }}>
            ✓ Validar
          </Button>
          <Button size="sm" variant="outline" onClick={() => setShowSettings(true)}
            style={{ height: 32, fontSize: 13, padding: '0 12px' }}>
            ⚙ Flow
          </Button>
          <Button size="sm" variant="destructive" onClick={handleDelete}
            style={{ height: 32, fontSize: 13, padding: '0 12px' }}>
            🗑
          </Button>
          <div style={{ width: 1, height: 24, background: 'var(--border)' }} />
        </>)}

        <div style={{ flex: 1 }} />

        {tab && (
          <span style={{
            fontSize: 12,
            fontWeight: 500,
            padding: '3px 10px',
            borderRadius: 6,
            background: validStatus === 'valid' ? '#052e16' : validStatus === 'invalid' ? '#3b0a0a' : 'var(--secondary)',
            color: validStatus === 'valid' ? '#6ee7b7' : validStatus === 'invalid' ? '#fca5a5' : 'var(--muted-foreground)',
          }}>
            {validStatus === 'valid' ? '✓ Válido'
              : validStatus === 'invalid' ? `✗ ${tab.validationErrors.length} error(es)` : '—'}
          </span>
        )}
      </header>

      {/* Tabs de flows abiertos */}
      {tabs.length > 0 && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          borderBottom: '1px solid var(--border)',
          background: 'var(--card)',
          padding: '0 8px',
          flexShrink: 0,
        }}>
          {tabs.map(t => {
            const isActive = t.name === activeTabName
            return (
              <div
                key={t.name}
                onClick={() => setActiveTab(t.name)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '10px 16px',
                  fontSize: 14,
                  cursor: 'pointer',
                  borderBottom: `2px solid ${isActive ? 'var(--primary)' : 'transparent'}`,
                  color: isActive ? 'var(--foreground)' : 'var(--muted-foreground)',
                  transition: 'color 0.15s, border-color 0.15s',
                }}
              >
                <span>{t.name}</span>
                {t.dirty && <span style={{ color: 'var(--primary)', fontSize: 10 }}>●</span>}
                {t.runs.some(r => r.status === 'running') && (
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#facc15', display: 'inline-block' }} />
                )}
                <button
                  onClick={e => { e.stopPropagation(); closeTab(t.name) }}
                  style={{
                    marginLeft: 2,
                    fontSize: 16,
                    lineHeight: 1,
                    color: 'var(--muted-foreground)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '0 2px',
                  }}
                >×</button>
              </div>
            )
          })}
        </div>
      )}

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar izquierdo */}
        <div style={{
          width: 224,
          display: 'flex',
          flexDirection: 'column',
          borderRight: '1px solid var(--border)',
          background: 'var(--card)',
          flexShrink: 0,
          overflow: 'hidden',
        }}>
          <NodePalette catalog={catalog} />
          <VariablesPanel
            variables={tab?.flowDef?.variables ?? []}
            onChange={updateVariables}
          />
          <CustomNodesPanel onReload={refreshCatalog} />
        </div>
        <FlowCanvas onSelectNode={setSelectedNodeId} onToast={addToast} />
        <PropertiesPanel
          selectedNodeId={selectedNodeId}
          nodes={tab?.nodes ?? []}
          edges={tab?.edges ?? []}
          catalog={catalog}
          flowList={flowList}
          validationErrors={tab?.validationErrors ?? []}
          onUpdateNode={handleUpdateNode}
        />
      </div>

      {/* Footer */}
      <RunsPanel
        activeFlow={tab?.flowDef ?? null}
        validationErrors={tab?.validationErrors ?? []}
        onSave={handleSave}
      />

      {/* Flow settings */}
      {showSettings && tab?.flowDef && (
        <FlowSettingsDialog
          inputs={tab.flowDef.inputs || {}}
          outputs={tab.flowDef.outputs || {}}
          onClose={() => setShowSettings(false)}
          onSave={handleSaveSettings}
        />
      )}

      {/* Dialogo de nuevo flow */}
      {showNew && (
        <NewFlowDialog
          onClose={() => setShowNew(false)}
          onCreate={flow => {
            setFlowList([...flowList, {
              name: flow.name, version: flow.version,
              inputs: flow.inputs, outputs: flow.outputs,
            }])
            const { nodes, edges } = flowDefToRF(flow, catalog)
            openTab(flow, nodes, edges)
          }}
        />
      )}

      {/* Toasts */}
      <div className="fixed bottom-5 right-5 flex flex-col gap-2 z-50">
        {toasts.map(t => (
          <div key={t.id} className={`px-4 py-2.5 rounded-lg text-xs border shadow-lg ${
            t.type === 'error' ? 'border-red-500 text-red-300 bg-[var(--card)]' :
            t.type === 'success' ? 'border-green-500 text-green-300 bg-[var(--card)]' :
            'border-[var(--border)] text-[var(--foreground)] bg-[var(--card)]'
          }`}>
            {t.msg}
          </div>
        ))}
      </div>
    </div>
  )
}
