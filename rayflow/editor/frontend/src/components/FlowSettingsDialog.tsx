import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const PIN_TYPES = ['str', 'int', 'float', 'bool', 'list', 'dict', 'list[str]', 'list[int]', 'list[float]', 'Any']

interface PinRow { name: string; type: string }

function parsePins(record: Record<string, string>): PinRow[] {
  return Object.entries(record).map(([name, type]) => ({ name, type }))
}

function pinsToRecord(rows: PinRow[]): Record<string, string> {
  const result: Record<string, string> = {}
  for (const r of rows) {
    if (r.name.trim()) result[r.name.trim()] = r.type
  }
  return result
}

const sectionLabel: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  color: 'var(--muted-foreground)',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  marginBottom: 10,
}

function PinEditor({ rows, onChange }: { rows: PinRow[]; onChange: (rows: PinRow[]) => void }) {
  function updateRow(i: number, patch: Partial<PinRow>) {
    onChange(rows.map((r, j) => j === i ? { ...r, ...patch } : r))
  }
  function removeRow(i: number) {
    onChange(rows.filter((_, j) => j !== i))
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {rows.length === 0 && (
        <div style={{ fontSize: 13, color: 'var(--muted-foreground)', padding: '6px 0' }}>
          Sin pins definidos
        </div>
      )}
      {rows.map((row, i) => (
        <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Input
            placeholder="nombre"
            value={row.name}
            onChange={e => updateRow(i, { name: e.target.value })}
            style={{ flex: 1, height: 32, fontSize: 13, background: 'var(--secondary)', borderColor: 'var(--border)', color: 'var(--foreground)' }}
          />
          <Select value={row.type} onValueChange={v => updateRow(i, { type: v })}>
            <SelectTrigger
              style={{ width: 136, height: 32, fontSize: 13, background: 'var(--secondary)', borderColor: 'var(--border)', color: 'var(--foreground)', flexShrink: 0 }}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[var(--card)] border-[var(--border)]">
              {PIN_TYPES.map(t => (
                <SelectItem key={t} value={t} style={{ fontSize: 13 }}>{t}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <button
            onClick={() => removeRow(i)}
            title="Eliminar"
            style={{
              width: 32, height: 32, flexShrink: 0,
              borderRadius: 6, border: '1px solid var(--border)',
              background: 'transparent', color: 'var(--muted-foreground)',
              cursor: 'pointer', fontSize: 18, lineHeight: 1,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'color 0.15s, border-color 0.15s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = 'var(--destructive)'; (e.currentTarget as HTMLElement).style.borderColor = 'var(--destructive)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = 'var(--muted-foreground)'; (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)' }}
          >×</button>
        </div>
      ))}
      <button
        onClick={() => onChange([...rows, { name: '', type: 'str' }])}
        style={{
          height: 32, borderRadius: 6,
          border: '1px dashed var(--border)',
          background: 'transparent', color: 'var(--muted-foreground)',
          cursor: 'pointer', fontSize: 13, marginTop: 2,
          transition: 'color 0.15s, border-color 0.15s',
        }}
        onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = 'var(--foreground)'; (e.currentTarget as HTMLElement).style.borderColor = 'var(--foreground)' }}
        onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = 'var(--muted-foreground)'; (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)' }}
      >
        + Añadir pin
      </button>
    </div>
  )
}

interface Props {
  inputs: Record<string, string>
  outputs: Record<string, string>
  onClose: () => void
  onSave: (inputs: Record<string, string>, outputs: Record<string, string>) => void
}

export default function FlowSettingsDialog({ inputs, outputs, onClose, onSave }: Props) {
  const [inputRows, setInputRows] = useState<PinRow[]>(parsePins(inputs))
  const [outputRows, setOutputRows] = useState<PinRow[]>(parsePins(outputs))
  const [err, setErr] = useState('')

  function handleSave() {
    setErr('')
    const names = [...inputRows, ...outputRows].map(r => r.name.trim()).filter(Boolean)
    const dupes = names.filter((n, i) => names.indexOf(n) !== i)
    if (dupes.length) { setErr(`Nombres duplicados: ${dupes.join(', ')}`); return }
    onSave(pinsToRecord(inputRows), pinsToRecord(outputRows))
    onClose()
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent
        className="bg-[var(--card)] border-[var(--border)] text-[var(--foreground)]"
        style={{ maxWidth: 480, padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}
      >
        <DialogHeader>
          <DialogTitle style={{ fontSize: 15, fontWeight: 600 }}>Flow settings</DialogTitle>
        </DialogHeader>

        <div>
          <div style={sectionLabel}>Inputs</div>
          <PinEditor rows={inputRows} onChange={setInputRows} />
        </div>

        <div style={{ height: 1, background: 'var(--border)' }} />

        <div>
          <div style={sectionLabel}>Outputs</div>
          <PinEditor rows={outputRows} onChange={setOutputRows} />
        </div>

        {err && (
          <div style={{ fontSize: 12, color: '#fca5a5', padding: '6px 10px', background: 'rgba(220,38,38,0.08)', borderRadius: 6, border: '1px solid rgba(220,38,38,0.25)' }}>
            {err}
          </div>
        )}

        <DialogFooter style={{ marginTop: 4 }}>
          <Button variant="ghost" onClick={onClose} style={{ fontSize: 13 }}>Cancelar</Button>
          <Button onClick={handleSave} style={{ fontSize: 13 }}>Guardar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
