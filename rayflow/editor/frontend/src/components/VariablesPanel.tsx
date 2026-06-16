import { useState } from 'react'
import type { FlowDef } from '@/lib/api'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

type Variable = FlowDef['variables'][number]

const VAR_TYPES = ['str', 'int', 'float', 'bool', 'list', 'dict', 'list[str]', 'list[int]', 'Any']

const DEFAULT_BY_TYPE: Record<string, unknown> = {
  str: '', int: 0, float: 0.0, bool: false, list: [], dict: {}, 'list[str]': [], 'list[int]': [], Any: null,
}

interface Props {
  variables: Variable[]
  onChange: (vars: Variable[]) => void
}

function parseDefault(raw: string, type: string): unknown {
  if (type === 'str') return raw
  try { return JSON.parse(raw) } catch { return raw }
}

function formatDefault(val: unknown): string {
  if (val === null || val === undefined) return ''
  if (typeof val === 'string') return val
  return JSON.stringify(val)
}

export default function VariablesPanel({ variables, onChange }: Props) {
  const [open, setOpen] = useState(true)
  const [editingIdx, setEditingIdx] = useState<number | null>(null)
  const [draft, setDraft] = useState<Variable | null>(null)

  function startEdit(idx: number) {
    setEditingIdx(idx)
    setDraft({ ...variables[idx] })
  }

  function commitEdit() {
    if (editingIdx === null || !draft) return
    const updated = variables.map((v, i) => i === editingIdx ? draft : v)
    onChange(updated)
    setEditingIdx(null)
    setDraft(null)
  }

  function cancelEdit() {
    setEditingIdx(null)
    setDraft(null)
  }

  function addVariable() {
    const base = 'variable'
    const existing = new Set(variables.map(v => v.name))
    let name = base
    let n = 1
    while (existing.has(name)) name = `${base}_${n++}`
    const newVar: Variable = { name, type: 'str', default: '' }
    const newVars = [...variables, newVar]
    onChange(newVars)
    setEditingIdx(newVars.length - 1)
    setDraft({ ...newVar })
  }

  function removeVariable(idx: number) {
    if (editingIdx === idx) { setEditingIdx(null); setDraft(null) }
    onChange(variables.filter((_, i) => i !== idx))
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
          padding: '10px 12px 6px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--muted-foreground)',
          textTransform: 'uppercase',
          letterSpacing: '0.07em',
        }}
      >
        <span>Variables</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            role="button"
            onClick={e => { e.stopPropagation(); addVariable() }}
            title="Nueva variable"
            style={{
              fontSize: 16,
              lineHeight: 1,
              color: 'var(--muted-foreground)',
              padding: '0 2px',
              borderRadius: 4,
              cursor: 'pointer',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--foreground)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted-foreground)')}
          >+</span>
          <span style={{
            fontSize: 10,
            transition: 'transform 0.15s',
            display: 'inline-block',
            transform: open ? 'rotate(0deg)' : 'rotate(-90deg)',
          }}>▾</span>
        </div>
      </button>

      {open && (
        <div style={{ padding: '0 4px 10px' }}>
          {variables.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--muted-foreground)', padding: '6px 8px', textAlign: 'center' }}>
              Sin variables
            </div>
          )}

          {variables.map((v, idx) => (
            <div key={idx}>
              {editingIdx === idx && draft ? (
                /* Fila de edición */
                <div style={{
                  background: 'var(--secondary)',
                  borderRadius: 8,
                  padding: '8px 10px',
                  margin: '2px 0',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                }}>
                  <input
                    autoFocus
                    value={draft.name}
                    onChange={e => setDraft(d => ({ ...d!, name: e.target.value }))}
                    onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit() }}
                    placeholder="nombre"
                    style={{
                      height: 28,
                      padding: '0 8px',
                      borderRadius: 5,
                      border: '1px solid var(--border)',
                      background: 'var(--card)',
                      color: 'var(--foreground)',
                      fontSize: 12,
                      outline: 'none',
                      width: '100%',
                      boxSizing: 'border-box',
                    }}
                  />
                  <Select
                    value={draft.type}
                    onValueChange={t => setDraft(d => ({ ...d!, type: t, default: DEFAULT_BY_TYPE[t] ?? null }))}
                  >
                    <SelectTrigger style={{ height: 28, fontSize: 12 }}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {VAR_TYPES.map(t => (
                        <SelectItem key={t} value={t} style={{ fontSize: 12 }}>{t}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <input
                    value={formatDefault(draft.default)}
                    onChange={e => setDraft(d => ({ ...d!, default: parseDefault(e.target.value, d!.type) }))}
                    onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit() }}
                    placeholder="default"
                    style={{
                      height: 28,
                      padding: '0 8px',
                      borderRadius: 5,
                      border: '1px solid var(--border)',
                      background: 'var(--card)',
                      color: 'var(--foreground)',
                      fontSize: 12,
                      outline: 'none',
                      width: '100%',
                      boxSizing: 'border-box',
                    }}
                  />
                  <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                    <button
                      onClick={cancelEdit}
                      style={{ fontSize: 11, padding: '3px 10px', borderRadius: 5, border: '1px solid var(--border)', background: 'transparent', color: 'var(--muted-foreground)', cursor: 'pointer' }}
                    >Cancelar</button>
                    <button
                      onClick={commitEdit}
                      style={{ fontSize: 11, padding: '3px 10px', borderRadius: 5, border: 'none', background: 'var(--primary)', color: '#fff', cursor: 'pointer' }}
                    >OK</button>
                  </div>
                </div>
              ) : (
                /* Fila normal */
                <div
                  onClick={() => startEdit(idx)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 8px',
                    borderRadius: 6,
                    cursor: 'pointer',
                    margin: '1px 0',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--secondary)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  {/* Indicador de tipo */}
                  <span style={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: typeColor(v.type),
                    flexShrink: 0,
                  }} />
                  <span style={{ fontSize: 12, color: 'var(--foreground)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {v.name}
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--muted-foreground)', flexShrink: 0 }}>{v.type}</span>
                  <button
                    onClick={e => { e.stopPropagation(); removeVariable(idx) }}
                    title="Eliminar"
                    style={{
                      fontSize: 14,
                      lineHeight: 1,
                      background: 'none',
                      border: 'none',
                      color: 'var(--muted-foreground)',
                      cursor: 'pointer',
                      padding: '0 2px',
                      flexShrink: 0,
                    }}
                    onMouseEnter={e => (e.currentTarget.style.color = 'var(--destructive)')}
                    onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted-foreground)')}
                  >×</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function typeColor(type: string): string {
  const t = (type || 'any').toLowerCase().split('[')[0]
  const map: Record<string, string> = {
    int: 'var(--type-int)', float: 'var(--type-float)', str: 'var(--type-str)',
    bool: 'var(--type-bool)', list: 'var(--type-list)', dict: 'var(--type-dict)', any: 'var(--type-any)',
  }
  return map[t] ?? 'var(--type-any)'
}
