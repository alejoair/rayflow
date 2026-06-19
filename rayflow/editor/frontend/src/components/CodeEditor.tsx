import { useCallback, useMemo } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { python } from '@codemirror/lang-python'
import { oneDark } from '@codemirror/theme-one-dark'
import { Button } from '@/components/ui/button'
import { rayflowHighlight, rayflowTooltip } from '@/lib/rayflowHighlight'

interface Props {
  name: string
  source: string
  savedSource: string
  saving: boolean
  error: string | null
  onSourceChange: (source: string) => void
  onSave: () => void
}

export default function CodeEditor({ name, source, savedSource, saving, error, onSourceChange, onSave }: Props) {
  const isDirty = source !== savedSource

  const extensions = useMemo(() => [python(), rayflowHighlight, rayflowTooltip], [])

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault()
      onSave()
    }
  }, [onSave])

  return (
    <div
      style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}
      onKeyDown={handleKeyDown as unknown as React.KeyboardEventHandler}
    >
      {/* Toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '0 16px',
        height: 40,
        borderBottom: '1px solid var(--border)',
        background: 'var(--card)',
        flexShrink: 0,
      }}>
        {/* Ícono de código */}
        <span style={{ fontSize: 13, color: 'var(--exec-color)', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '-0.05em' }}>{'{ }'}</span>
        <span style={{ fontSize: 13, color: 'var(--foreground)', fontWeight: 500 }}>
          {name}.py
        </span>
        {isDirty && (
          <span style={{ fontSize: 11, color: 'var(--exec-color)', fontWeight: 600 }}>●</span>
        )}

        <div style={{ flex: 1 }} />

        {error && (
          <span style={{
            fontSize: 11, fontFamily: 'monospace',
            color: 'var(--destructive)',
            background: 'rgba(239,68,68,0.10)',
            border: '1px solid rgba(239,68,68,0.25)',
            borderRadius: 5, padding: '3px 8px',
            maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }} title={error}>{error}</span>
        )}

        <Button
          size="sm"
          onClick={onSave}
          disabled={saving || !isDirty}
          style={{
            height: 28, fontSize: 12, padding: '0 14px',
            background: isDirty ? 'var(--exec-color)' : undefined,
            color: isDirty ? '#000' : undefined,
            opacity: (!isDirty || saving) ? 0.5 : 1,
          }}
        >
          {saving ? 'Guardando…' : 'Guardar'}
        </Button>

        <span style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>Ctrl+S</span>
      </div>

      {/* Editor */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        <CodeMirror
          value={source}
          onChange={onSourceChange}
          extensions={extensions}
          theme={oneDark}
          style={{ fontSize: 13, height: '100%' }}
          height="100%"
          basicSetup={{ lineNumbers: true, foldGutter: true, autocompletion: true }}
        />
      </div>
    </div>
  )
}
