import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import {
  listCustomNodes, getCustomNodeSource, createCustomNode,
  deleteCustomNode,
  type CustomNodeFile,
} from '@/lib/api'
import { useFlowStore } from '@/store/flowStore'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'

interface Props {
  onReload: () => void
}

export default function CustomNodesPanel({ onReload }: Props) {
  const [open, setOpen] = useState(false)
  const [files, setFiles] = useState<CustomNodeFile[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [creatingName, setCreatingName] = useState('')
  const [createError, setCreateError] = useState('')
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null)

  const { openCodeTab, activeTabName, tabs } = useFlowStore()

  const refreshList = useCallback(async () => {
    try {
      const list = await listCustomNodes()
      setFiles(list)
    } catch { /* silencioso */ }
  }, [])

  useEffect(() => {
    if (open) refreshList()
  }, [open, refreshList])

  async function handleOpen(name: string) {
    // Si ya hay una pestaña abierta para este archivo, simplemente activarla
    const existing = tabs.find(t => t.kind === 'code' && t.name === name)
    if (existing) {
      useFlowStore.setState({ activeTabName: name })
      return
    }
    try {
      const res = await getCustomNodeSource(name)
      openCodeTab(name, res.source)
    } catch { /* silencioso */ }
  }

  async function handleCreate() {
    const name = creatingName.trim()
    if (!name) return
    setCreateError('')
    try {
      const res = await createCustomNode(name)
      setShowCreate(false)
      setCreatingName('')
      await refreshList()
      const src = await getCustomNodeSource(res.name)
      openCodeTab(res.name, src.source)
      onReload()
    } catch (e) {
      setCreateError((e as Error).message)
    }
  }

  async function handleDelete(name: string) {
    try {
      await deleteCustomNode(name)
      // Cerrar la pestaña de código si estaba abierta
      useFlowStore.getState().closeTab(name)
      await refreshList()
      onReload()
    } catch { /* silencioso */ }
    setShowDeleteConfirm(null)
  }

  const openFileNames = new Set(tabs.filter(t => t.kind === 'code').map(t => t.name))

  return (
    <div style={{ borderTop: '1px solid var(--border)', flexShrink: 0 }}>
      {/* Header colapsable */}
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 12px 10px 16px',
          background: 'none',
          border: 'none',
          borderBottom: open ? '1px solid var(--border)' : 'none',
          cursor: 'pointer',
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--muted-foreground)',
          textTransform: 'uppercase',
          letterSpacing: '0.07em',
        }}
      >
        <span>Nodos custom</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {open && (
            <span
              role="button"
              title="Nuevo nodo"
              onClick={e => { e.stopPropagation(); setShowCreate(true) }}
              style={{ fontSize: 16, lineHeight: 1, color: 'var(--muted-foreground)', padding: '0 2px' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--foreground)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted-foreground)')}
            >+</span>
          )}
          <span style={{ fontSize: 10, transition: 'transform 0.15s', display: 'inline-block', transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▾</span>
        </div>
      </button>

      {open && (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {/* Formulario nuevo nodo */}
          {showCreate && (
            <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 6, borderBottom: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', gap: 6 }}>
                <input
                  autoFocus
                  placeholder="NombreNodo"
                  value={creatingName}
                  onChange={e => setCreatingName(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') handleCreate()
                    if (e.key === 'Escape') { setShowCreate(false); setCreatingName(''); setCreateError('') }
                  }}
                  style={{
                    flex: 1, height: 28, fontSize: 12, padding: '0 8px',
                    background: 'var(--secondary)', border: '1px solid var(--border)',
                    borderRadius: 5, color: 'var(--foreground)', outline: 'none',
                  }}
                />
                <Button size="sm" onClick={handleCreate} style={{ height: 28, fontSize: 11, padding: '0 10px' }}>Crear</Button>
                <Button size="sm" variant="ghost" onClick={() => { setShowCreate(false); setCreatingName(''); setCreateError('') }} style={{ height: 28, fontSize: 11, padding: '0 8px' }}>✕</Button>
              </div>
              {createError && (
                <div style={{ fontSize: 11, color: 'var(--destructive)', fontFamily: 'monospace' }}>{createError}</div>
              )}
            </div>
          )}

          {/* Lista de archivos */}
          <div style={{ maxHeight: 160, overflowY: 'auto' }}>
            {files.length === 0 && (
              <div style={{ padding: '10px 16px', fontSize: 12, color: 'var(--muted-foreground)', fontStyle: 'italic' }}>
                Sin nodos custom
              </div>
            )}
            {files.map(f => {
              const isOpen = openFileNames.has(f.name)
              const isActive = activeTabName === f.name
              return (
                <div
                  key={f.name}
                  onClick={() => handleOpen(f.name)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '5px 12px',
                    background: isActive ? 'rgba(245,158,11,0.10)' : 'transparent',
                    borderLeft: isActive ? '2px solid var(--exec-color)' : '2px solid transparent',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'var(--secondary)' }}
                  onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}
                >
                  <span style={{ fontSize: 10, color: 'var(--exec-color)', fontFamily: 'monospace', fontWeight: 700, flexShrink: 0 }}>py</span>
                  <span style={{
                    flex: 1, fontSize: 12,
                    color: isActive ? 'var(--foreground)' : isOpen ? 'var(--exec-color)' : 'var(--muted-foreground)',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    fontWeight: isOpen ? 500 : 400,
                  }}>
                    {f.name}.py
                  </span>
                  <button
                    onClick={e => { e.stopPropagation(); setShowDeleteConfirm(f.name) }}
                    title="Eliminar"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--muted-foreground)', padding: '0 2px', lineHeight: 1 }}
                    onMouseEnter={e => (e.currentTarget.style.color = 'var(--destructive)')}
                    onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted-foreground)')}
                  >✕</button>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Confirmación de eliminación */}
      {showDeleteConfirm && (
        <Dialog open onOpenChange={() => setShowDeleteConfirm(null)}>
          <DialogContent style={{ maxWidth: 380, padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}
            className="bg-[var(--card)] border-[var(--border)] text-[var(--foreground)]">
            <DialogHeader>
              <DialogTitle style={{ fontSize: 15, fontWeight: 600 }}>Eliminar nodo custom</DialogTitle>
            </DialogHeader>
            <p style={{ fontSize: 13, color: 'var(--muted-foreground)', margin: 0 }}>
              ¿Eliminar <span style={{ color: 'var(--foreground)', fontWeight: 600 }}>"{showDeleteConfirm}.py"</span>? Esta acción no se puede deshacer.
            </p>
            <DialogFooter style={{ marginTop: 4 }}>
              <Button variant="ghost" onClick={() => setShowDeleteConfirm(null)} style={{ fontSize: 13 }}>Cancelar</Button>
              <Button variant="destructive" onClick={() => handleDelete(showDeleteConfirm)} style={{ fontSize: 13 }}>Eliminar</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
