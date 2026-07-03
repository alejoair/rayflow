import { useEffect, useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useFlowStore, selectActiveTab, selectActiveTabAny, initWorkspaceStore } from '@/store/flowStore'
import { getEditorInfo, getNodes, getFlows, getFlow, createFlow, deleteFlow, updateFlow, validateFlow, loadFlow, updateCustomNodeSource } from '@/lib/api'
import { flowDefToRF, rfToFlowDef } from '@/lib/translator'
import NodePalette from '@/components/NodePalette'
import FlowCanvas from '@/components/FlowCanvas'
import PropertiesPanel from '@/components/PropertiesPanel'
import RunsPanel from '@/components/RunsPanel'
import FlowSettingsDialog from '@/components/FlowSettingsDialog'
import VariablesPanel from '@/components/VariablesPanel'
import CustomNodesPanel from '@/components/CustomNodesPanel'
import CodeEditor from '@/components/CodeEditor'
import type { FlowDef } from '@/lib/api'
import { useResizable } from '@/hooks/useResizable'

interface Toast { id: number; msg: string; type: 'info' | 'success' | 'error' }

function NewFlowDialog({ onClose, onCreate }: { onClose: () => void; onCreate: (flow: FlowDef) => void }) {
  const [name, setName] = useState('')
  const [err, setErr] = useState('')

  async function handleCreate() {
    setErr('')
    if (!name.trim()) { setErr('El nombre es requerido'); return }
    try {
      const flow = await createFlow({ name: name.trim(), version: '1', outputs: {}, variables: [], events: [], nodes: [] })
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
            Los outputs se configuran después con ⚙ Flow settings.
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
  const [cwd, setCwd] = useState<string | null>(null)

  // Primer efecto: obtener el cwd del servidor y apuntar el store al namespace correcto
  useEffect(() => {
    getEditorInfo()
      .then(info => {
        initWorkspaceStore(info.cwd)
        setCwd(info.cwd)
      })
      .catch(() => {
        // Si falla (servidor no disponible), usar clave genérica para no bloquear la UI
        initWorkspaceStore('default')
        setCwd('')
      })
  }, [])

  const {
    catalog, setCatalog,
    flowList, setFlowList,
    tabs, activeTabName,
    openTab, closeTab, setActiveTab,
    setNodes, setEdges, setDirty, setValidationErrors,
    updateVariables,
    updateCodeSource, markCodeSaved,
  } = useFlowStore()

  const tab = useFlowStore(selectActiveTab)
  const activeTab = useFlowStore(selectActiveTabAny)
  const isCodeTab = activeTab?.kind === 'code'

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [codeSaving, setCodeSaving] = useState(false)
  const [codeError, setCodeError] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
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
            if (tab.kind !== 'flow' || !tab.flowDef) return tab
            // Entry nodes (OnStart, ChatTrigger, custom @entry_node, ...)
            // keep their real catalog meta as-is — their pins are static,
            // declared on the class, not derived from a flow-level field.
            const foMeta = {
              ...(m['FlowOutput'] ?? { type: 'FlowOutput', decorator: 'engine_node', is_exec_node: true, has_exec_in: true, has_exec_out: false, is_parallel: false, exec_outputs: [] }),
              inputs: Object.entries(tab.flowDef.outputs || {}).map(([name, type]) => ({ name, type, kind: 'input' as const, required: false })),
              outputs: [],
            }
            return {
              ...tab,
              nodes: tab.nodes.map(n => {
                const nodeType = (n.data as { nodeType: string }).nodeType
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
    if (cwd === null) return  // esperar hasta conocer el workspace
    refreshCatalog()
    getFlows()
      .then(data => setFlowList(data.flows || []))
      .catch(console.error)
  }, [cwd])

  function addToast(msg: string, type: Toast['type'] = 'info') {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev, { id, msg, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3500)
  }

  // Valida el flow activo y, si es válido, lo carga en Ray en background.
  // tabName es opcional: si se omite usa el tab activo.
  async function autoLoadFlow(flowDef: Parameters<typeof rfToFlowDef>[2] & { name: string }, nodes: Parameters<typeof rfToFlowDef>[0], edges: Parameters<typeof rfToFlowDef>[1]) {
    // Validar primero
    const fd = rfToFlowDef(nodes, edges, {
      name: flowDef.name, version: flowDef.version || '1',
      outputs: flowDef.outputs || {},
      variables: flowDef.variables || [], events: flowDef.events || [],
    })
    let valid = false
    try {
      const result = await validateFlow(fd)
      // Actualizar errores en el tab correspondiente
      useFlowStore.setState(s => ({
        tabs: s.tabs.map(t => t.name !== flowDef.name ? t : { ...t, validationErrors: result.errors || [] }),
      }))
      valid = result.valid
    } catch {
      return
    }
    if (!valid) return

    // Cargar en Ray en background
    useFlowStore.setState(s => ({
      tabs: s.tabs.map(t => t.name !== flowDef.name ? t : { ...t, loadingIntoRay: true }),
    }))
    try {
      await loadFlow(flowDef.name)
      useFlowStore.setState(s => ({
        tabs: s.tabs.map(t => t.name !== flowDef.name ? t : { ...t, loaded: true, loadingIntoRay: false, stale: false }),
      }))
    } catch {
      useFlowStore.setState(s => ({
        tabs: s.tabs.map(t => t.name !== flowDef.name ? t : { ...t, loadingIntoRay: false }),
      }))
    }
  }

  async function handleOpenFlow(name: string) {
    if (!name) return
    const existing = tabs.find(t => t.name === name)
    if (existing) { setActiveTab(name); return }
    try {
      const data = await getFlow(name)
      const { nodes, edges } = flowDefToRF(data, catalog)
      openTab(data, nodes, edges)
      // Validar y cargar en Ray en background sin bloquear la UI
      autoLoadFlow(data, nodes, edges)
    } catch (e) { addToast(`Error abriendo: ${(e as Error).message}`, 'error') }
  }

  async function handleSave() {
    const tab = selectActiveTab(useFlowStore.getState())
    if (!tab?.flowDef) return
    setSaving(true)
    try {
      const flowDef = rfToFlowDef(tab.nodes, tab.edges, {
        name: tab.flowDef.name,
        version: tab.flowDef.version || '1',
        outputs: tab.flowDef.outputs || {},
        variables: tab.flowDef.variables || [],
        events: tab.flowDef.events || [],
      })
      await updateFlow(tab.name, flowDef)
      setDirty(false)
      addToast('Flow guardado', 'success')
      // Recargar en Ray automáticamente tras guardar
      autoLoadFlow(tab.flowDef, tab.nodes, tab.edges)
    } catch (e) { addToast(`Error guardando: ${(e as Error).message}`, 'error') }
    finally { setSaving(false) }
  }

  async function handleValidate() {
    const tab = selectActiveTab(useFlowStore.getState())
    if (!tab?.flowDef) return
    try {
      const flowDef = rfToFlowDef(tab.nodes, tab.edges, {
        name: tab.flowDef.name, version: tab.flowDef.version || '1',
        outputs: tab.flowDef.outputs || {},
        variables: tab.flowDef.variables || [], events: tab.flowDef.events || [],
      })
      const result = await validateFlow(flowDef)
      setValidationErrors(result.errors || [])
      if (result.valid) {
        addToast('Flow válido ✓', 'success')
      } else {
        // Mostrar mensaje con más detalles
        const errorDetails = result.errors.slice(0, 3).join('\n')
        const moreErrors = result.errors.length > 3 ? `\n... y ${result.errors.length - 3} más` : ''
        addToast(`${result.errors.length} error(es):\n${errorDetails}${moreErrors}`, 'error')
      }
    } catch (e) { addToast(`Error validando: ${(e as Error).message}`, 'error') }
  }

  async function handleSaveCode() {
    if (activeTab?.kind !== 'code') return
    setCodeSaving(true)
    setCodeError(null)
    try {
      await updateCustomNodeSource(activeTab.name, activeTab.source)
      markCodeSaved(activeTab.name)
      refreshCatalog()
      addToast('Nodo guardado', 'success')
    } catch (e) {
      setCodeError((e as Error).message)
    } finally {
      setCodeSaving(false)
    }
  }

  async function handleLoadIntoRay() {
    const tab = selectActiveTab(useFlowStore.getState())
    if (!tab?.flowDef) return
    await autoLoadFlow(tab.flowDef, tab.nodes, tab.edges)
  }

  function handleSaveSettings(outputs: Record<string, string>) {
    const tab = selectActiveTab(useFlowStore.getState())
    if (!tab?.flowDef) return

    // Meta sintética para FlowOutput con los nuevos pines. El entry node
    // (OnStart, ChatTrigger, ...) no se toca: sus pines son estáticos, no
    // derivados de un campo del flow.
    const newFlowOutputMeta = {
      ...(catalog['FlowOutput'] ?? { type: 'FlowOutput', decorator: 'engine_node', is_exec_node: true, has_exec_in: true, has_exec_out: false, is_parallel: false, exec_outputs: [] }),
      inputs: Object.entries(outputs).map(([name, type]) => ({ name, type, kind: 'input' as const, required: false })),
      outputs: [],
    }

    useFlowStore.setState(s => ({
      tabs: s.tabs.map(t => t.name !== tab.name || t.kind !== 'flow' ? t : {
        ...t,
        flowDef: { ...t.flowDef!, outputs },
        nodes: t.nodes.map(n => {
          const nodeType = (n.data as { nodeType: string }).nodeType
          if (nodeType === 'FlowOutput') return { ...n, data: { ...n.data, meta: newFlowOutputMeta } }
          return n
        }),
        dirty: true,
      }),
    }))

    addToast('Flow settings guardados', 'success')
  }

  async function handleDelete() {
    const tab = selectActiveTab(useFlowStore.getState())
    if (!tab) return
    try {
      await deleteFlow(tab.name)
      closeTab(tab.name)
      setFlowList(flowList.filter(f => f.name !== tab.name))
      addToast('Flow eliminado', 'info')
    } catch (e) { addToast(`Error borrando: ${(e as Error).message}`, 'error') }
    finally { setShowDeleteConfirm(false) }
  }

  const handleUpdateNode = useCallback((nodeId: string, update: Record<string, unknown>) => {
    const tab = selectActiveTab(useFlowStore.getState())
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

  const validStatus = !tab ? 'unknown' : tab.validationErrors.length === 0 ? 'valid' : 'invalid'

  const leftSidebar = useResizable({ key: 'rf-sidebar-left', default: 224, min: 160, max: 400, side: 'left' })
  const rightSidebar = useResizable({ key: 'rf-sidebar-right', default: 240, min: 180, max: 420, side: 'right' })
  const bottomPanel = useResizable({ key: 'rf-panel-bottom', default: 200, min: 100, max: 420, side: 'top' })

  return (
    <div className="flex flex-col h-screen bg-[var(--background)] text-[var(--foreground)]">

      {/* Header */}
      <header style={{
        height: 52,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '0 16px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--card)',
        flexShrink: 0,
        zIndex: 10,
      }}>
        {/* Marca */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginRight: 8 }}>
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <polygon points="4,3 18,11 4,19" fill="var(--primary)" opacity="0.9" />
            <polygon points="11,3 18,11 11,19" fill="var(--primary)" opacity="0.4" />
          </svg>
          <span style={{ fontWeight: 700, fontSize: 17, color: 'var(--foreground)', letterSpacing: '-0.01em' }}>
            Rayflow
          </span>
        </div>

        <div style={{ width: 1, height: 24, background: 'var(--border)' }} />

        {/* Abrir / nuevo flow */}
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

        {/* Acciones del flow activo */}
        {tab && (<>
          <div style={{ width: 1, height: 24, background: 'var(--border)', margin: '0 2px' }} />
          <Button size="sm" onClick={handleSave} disabled={saving}
            style={{ height: 32, fontSize: 13, padding: '0 14px' }}>
            {saving ? 'Guardando…' : 'Guardar'}
          </Button>
          <Button size="sm" variant="outline" onClick={handleValidate}
            style={{ height: 32, fontSize: 13, padding: '0 12px' }}>
            Validar
          </Button>
          <Button size="sm" variant="outline" onClick={() => setShowSettings(true)}
            style={{ height: 32, fontSize: 13, padding: '0 12px' }}>
            Flow settings
          </Button>
          {!tab.loaded && !tab.loadingIntoRay && tab.validationErrors.length === 0 && (
            <Button size="sm" variant="outline" onClick={handleLoadIntoRay}
              style={{ height: 32, fontSize: 13, padding: '0 12px', borderColor: 'rgba(16,185,129,0.35)', color: '#34d399' }}>
              Cargar en Ray
            </Button>
          )}
          <div style={{ width: 1, height: 24, background: 'var(--border)', margin: '0 2px' }} />
          <Button size="sm" variant="destructive" onClick={() => setShowDeleteConfirm(true)}
            style={{ height: 32, fontSize: 13, padding: '0 10px' }}>
            Eliminar
          </Button>
        </>)}

        <div style={{ flex: 1 }} />

        {/* Workspace path */}
        {cwd !== null && cwd !== '' && (
          <span title={cwd} style={{
            fontSize: 11,
            color: 'var(--muted-foreground)',
            maxWidth: 200,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {cwd.split(/[\\/]/).pop()}
          </span>
        )}

        {/* Chip de validación */}
        {tab && (
          <span style={{
            fontSize: 11,
            fontWeight: 600,
            padding: '3px 10px',
            borderRadius: 6,
            letterSpacing: '0.02em',
            background: validStatus === 'valid'
              ? 'rgba(16,185,129,0.12)'
              : validStatus === 'invalid'
              ? 'rgba(239,68,68,0.12)'
              : 'var(--secondary)',
            color: validStatus === 'valid'
              ? '#34d399'
              : validStatus === 'invalid'
              ? 'var(--destructive)'
              : 'var(--muted-foreground)',
            border: `1px solid ${validStatus === 'valid'
              ? 'rgba(16,185,129,0.25)'
              : validStatus === 'invalid'
              ? 'rgba(239,68,68,0.25)'
              : 'var(--border)'}`,
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
          overflowX: 'auto',
        }}>
          {tabs.map(t => {
            const isActive = t.name === activeTabName
            const isCode = t.kind === 'code'
            const accentColor = isCode ? 'var(--exec-color)' : 'var(--primary)'
            const isDirty = isCode ? t.source !== t.savedSource : t.dirty
            const isRunning = !isCode && t.runs.some(r => r.status === 'running')
            return (
              <div
                key={t.name}
                onClick={() => setActiveTab(t.name)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '10px 14px',
                  fontSize: 13,
                  cursor: 'pointer',
                  borderBottom: `2px solid ${isActive ? accentColor : 'transparent'}`,
                  color: isActive ? 'var(--foreground)' : 'var(--muted-foreground)',
                  transition: 'color 0.15s, border-color 0.15s',
                  whiteSpace: 'nowrap',
                  flexShrink: 0,
                }}
              >
                {isCode && (
                  <span style={{ fontSize: 10, color: isActive ? 'var(--exec-color)' : 'var(--muted-foreground)', fontFamily: 'monospace', fontWeight: 700 }}>py</span>
                )}
                <span>{t.name}{isCode ? '.py' : ''}</span>
                {isDirty && <span style={{ color: accentColor, fontSize: 10 }}>●</span>}
                {isRunning && (
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#facc15', display: 'inline-block' }} />
                )}
                <button
                  onClick={e => { e.stopPropagation(); closeTab(t.name) }}
                  style={{
                    marginLeft: 2, fontSize: 15, lineHeight: 1,
                    color: 'var(--muted-foreground)', background: 'none',
                    border: 'none', cursor: 'pointer', padding: '0 2px',
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
          width: leftSidebar.width,
          position: 'relative',
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
          {/* Handle de resize */}
          <div
            style={leftSidebar.handleStyle}
            onMouseDown={leftSidebar.onMouseDown}
          />
        </div>

        {/* Área central */}
        {isCodeTab && activeTab?.kind === 'code'
          ? <CodeEditor
              name={activeTab.name}
              source={activeTab.source}
              savedSource={activeTab.savedSource}
              saving={codeSaving}
              error={codeError}
              onSourceChange={src => updateCodeSource(activeTab.name, src)}
              onSave={handleSaveCode}
            />
          : <FlowCanvas onSelectNode={setSelectedNodeId} onToast={addToast} validationErrors={tab?.validationErrors ?? []} />
        }

        {/* Sidebar derecho — solo en tabs de flow */}
        {!isCodeTab && (
          <PropertiesPanel
            selectedNodeId={selectedNodeId}
            nodes={tab?.nodes ?? []}
            edges={tab?.edges ?? []}
            catalog={catalog}
            flowList={flowList}
            validationErrors={tab?.validationErrors ?? []}
            onUpdateNode={handleUpdateNode}
            width={rightSidebar.width}
            resizeHandleStyle={rightSidebar.handleStyle}
            onResizeMouseDown={rightSidebar.onMouseDown}
          />
        )}
      </div>

      {/* Footer — solo en tabs de flow */}
      {!isCodeTab && (
        <RunsPanel
          activeFlow={tab?.flowDef ?? null}
          validationErrors={tab?.validationErrors ?? []}
          onLoad={handleLoadIntoRay}
          height={bottomPanel.height}
          onResizeMouseDown={bottomPanel.onMouseDown}
          resizeHandleStyle={bottomPanel.handleStyle}
        />
      )}

      {/* Flow settings */}
      {showSettings && tab?.flowDef && (
        <FlowSettingsDialog
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
              outputs: flow.outputs,
            }])
            const { nodes, edges } = flowDefToRF(flow, catalog)
            openTab(flow, nodes, edges)
          }}
        />
      )}

      {/* Confirmación de eliminación */}
      {showDeleteConfirm && tab && (
        <Dialog open onOpenChange={() => setShowDeleteConfirm(false)}>
          <DialogContent style={{ maxWidth: 400, padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}
            className="bg-[var(--card)] border-[var(--border)] text-[var(--foreground)]">
            <DialogHeader>
              <DialogTitle style={{ fontSize: 15, fontWeight: 600 }}>Eliminar flow</DialogTitle>
            </DialogHeader>
            <p style={{ fontSize: 13, color: 'var(--muted-foreground)', margin: 0 }}>
              ¿Eliminar <span style={{ color: 'var(--foreground)', fontWeight: 600 }}>"{tab.name}"</span>? Esta acción no se puede deshacer.
            </p>
            <DialogFooter style={{ marginTop: 4 }}>
              <Button variant="ghost" onClick={() => setShowDeleteConfirm(false)} style={{ fontSize: 13 }}>Cancelar</Button>
              <Button variant="destructive" onClick={handleDelete} style={{ fontSize: 13 }}>Eliminar</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
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
