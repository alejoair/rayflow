import { useState, useEffect, useCallback } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { python } from '@codemirror/lang-python'
import { oneDark } from '@codemirror/theme-one-dark'
import { Button } from '@/components/ui/button'
import {
  listCustomNodes, getCustomNodeSource, createCustomNode,
  updateCustomNodeSource, deleteCustomNode,
  type CustomNodeFile,
} from '@/lib/api'

interface Props {
  onReload: () => void  // recarga el catálogo en App tras guardar
}

export default function CustomNodesPanel({ onReload }: Props) {
  const [open, setOpen] = useState(false)
  const [files, setFiles] = useState<CustomNodeFile[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [source, setSource] = useState('')
  const [savedSource, setSavedSource] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [creatingName, setCreatingName] = useState('')
  const [showCreate, setShowCreate] = useState(false)

  const isDirty = source !== savedSource

  const refreshList = useCallback(async () => {
    try {
      const list = await listCustomNodes()
      setFiles(list)
    } catch { /* silencioso */ }
  }, [])

  useEffect(() => {
    if (open) refreshList()
  }, [open, refreshList])

  async function selectFile(name: string) {
    setLoading(true)
    setError(null)
    try {
      const res = await getCustomNodeSource(name)
      setSelected(name)
      setSource(res.source)
      setSavedSource(res.source)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!selected) return
    setSaving(true)
    setError(null)
    try {
      await updateCustomNodeSource(selected, source)
      setSavedSource(source)
      onReload()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function handleCreate() {
    const name = creatingName.trim()
    if (!name) return
    setError(null)
    try {
      const res = await createCustomNode(name)
      setShowCreate(false)
      setCreatingName('')
      await refreshList()
      await selectFile(res.name)
      onReload()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function handleDelete(name: string) {
    if (!confirm(`¿Eliminar el nodo "${name}"?`)) return
    setError(null)
    try {
      await deleteCustomNode(name)
      if (selected === name) {
        setSelected(null)
        setSource('')
        setSavedSource('')
      }
      await refreshList()
      onReload()
    } catch (e) {
      setError((e as Error).message)
    }
  }

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
            <div style={{ padding: '8px 12px', display: 'flex', gap: 6, borderBottom: '1px solid var(--border)' }}>
              <input
                autoFocus
                placeholder="NombreNodo"
                value={creatingName}
                onChange={e => setCreatingName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleCreate(); if (e.key === 'Escape') { setShowCreate(false); setCreatingName('') } }}
                style={{
                  flex: 1, height: 28, fontSize: 12, padding: '0 8px',
                  background: 'var(--secondary)', border: '1px solid var(--border)',
                  borderRadius: 5, color: 'var(--foreground)', outline: 'none',
                }}
              />
              <Button size="sm" onClick={handleCreate} style={{ height: 28, fontSize: 11, padding: '0 10px' }}>Crear</Button>
              <Button size="sm" variant="ghost" onClick={() => { setShowCreate(false); setCreatingName('') }} style={{ height: 28, fontSize: 11, padding: '0 8px' }}>✕</Button>
            </div>
          )}

          {/* Lista de archivos */}
          <div style={{ maxHeight: 120, overflowY: 'auto' }}>
            {files.length === 0 && (
              <div style={{ padding: '10px 16px', fontSize: 12, color: 'var(--muted-foreground)', fontStyle: 'italic' }}>
                Sin nodos custom
              </div>
            )}
            {files.map(f => (
              <div
                key={f.name}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '5px 12px',
                  background: selected === f.name ? 'var(--secondary)' : 'transparent',
                  borderLeft: selected === f.name ? '2px solid var(--primary)' : '2px solid transparent',
                  cursor: 'pointer',
                }}
                onClick={() => selectFile(f.name)}
              >
                <span style={{ flex: 1, fontSize: 12, color: selected === f.name ? 'var(--foreground)' : 'var(--muted-foreground)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {f.name}.py
                </span>
                <button
                  onClick={e => { e.stopPropagation(); handleDelete(f.name) }}
                  title="Eliminar"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--muted-foreground)', padding: '0 2px', lineHeight: 1 }}
                  onMouseEnter={e => (e.currentTarget.style.color = 'var(--destructive)')}
                  onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted-foreground)')}
                >✕</button>
              </div>
            ))}
          </div>

          {/* Editor CodeMirror */}
          {selected && (
            <div style={{ borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column' }}>
              {/* Toolbar del editor */}
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '5px 12px',
                borderBottom: '1px solid var(--border)',
              }}>
                <span style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
                  {selected}.py{isDirty ? ' ●' : ''}
                </span>
                <Button
                  size="sm"
                  onClick={handleSave}
                  disabled={saving || !isDirty}
                  style={{ height: 24, fontSize: 11, padding: '0 10px' }}
                >
                  {saving ? 'Guardando…' : 'Guardar'}
                </Button>
              </div>

              {loading ? (
                <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground)' }}>Cargando…</div>
              ) : (
                <CodeMirror
                  value={source}
                  onChange={setSource}
                  extensions={[python()]}
                  theme={oneDark}
                  style={{ fontSize: 12, maxHeight: 340, overflowY: 'auto' }}
                  basicSetup={{ lineNumbers: true, foldGutter: false, autocompletion: true }}
                />
              )}
            </div>
          )}

          {error && (
            <div style={{
              margin: '6px 12px', padding: '6px 8px', fontSize: 11,
              color: 'var(--destructive)', background: 'rgba(239,68,68,0.08)',
              borderRadius: 5, fontFamily: 'monospace',
            }}>{error}</div>
          )}
        </div>
      )}
    </div>
  )
}
