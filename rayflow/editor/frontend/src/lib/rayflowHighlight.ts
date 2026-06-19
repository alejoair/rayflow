import { ViewPlugin, Decoration, hoverTooltip, type DecorationSet, type EditorView, type ViewUpdate } from '@codemirror/view'
import { RangeSetBuilder } from '@codemirror/state'

// ── Tokens que Rayflow reconoce como parte del contrato de un nodo ──────────

interface TokenDef {
  pattern: RegExp
  /** Clase CSS que se aplica al token */
  cls: string
  /** Descripción corta para el tooltip */
  label: string
  /** Detalle largo para el tooltip */
  detail: string
}

const TOKENS: TokenDef[] = [
  // Decoradores
  {
    pattern: /@(?:ray_node|engine_node|parallel_node)\b/g,
    cls: 'rf-hl-decorator',
    label: 'Decorador de nodo Rayflow',
    detail: '@ray_node → actor Ray persistente (stateful). @engine_node / @parallel_node → ejecución local en el FlowEngine (stateless).',
  },
  // Tipos de pin exec
  {
    pattern: /\bExec(?:Input|Output)\b/g,
    cls: 'rf-hl-exec-pin',
    label: 'Pin de ejecución',
    detail: 'ExecInput: punto de entrada secuencial del nodo. ExecOutput: pin de salida que dispara el siguiente nodo de la cadena.',
  },
  // Tipos de pin de datos
  {
    pattern: /\b(?:Input|Output)\b(?=\s*\()/g,
    cls: 'rf-hl-data-pin',
    label: 'Pin de datos',
    detail: 'Input(type, default=…): declara un parámetro de entrada. Output(type): declara un valor de salida del nodo.',
  },
  // Función run
  {
    pattern: /\basync\s+def\s+run\b/g,
    cls: 'rf-hl-run',
    label: 'Función de ejecución del nodo',
    detail: 'Punto de entrada obligatorio. Recibe (self, ctx: ExecContext, **inputs). Llama ctx.set_output() y await ctx.fire() para avanzar la ejecución.',
  },
  // ExecContext
  {
    pattern: /\bExecContext\b/g,
    cls: 'rf-hl-ctx-type',
    label: 'Tipo de contexto de ejecución',
    detail: 'Objeto inyectado en run(). Expone: ctx.set_output(pin, val), await ctx.fire(pin), ctx.get_variable(name), ctx.set_variable(name, val).',
  },
  // Métodos del contexto
  {
    pattern: /\bctx\.(?:set_output|fire|get_variable|set_variable|emit_event)\b/g,
    cls: 'rf-hl-ctx-call',
    label: 'Llamada al contexto de ejecución',
    detail: 'set_output(pin, val): escribe un valor de salida. fire(pin): dispara un exec pin. get/set_variable: variables persistentes del flow. emit_event: publica un evento al EventBroker.',
  },
]

// ── Clases CSS inyectadas como estilo inline en el documento ─────────────────

const STYLE = `
.rf-hl-decorator     { color: #c792ea !important; font-weight: 600; border-bottom: 1.5px dotted #c792ea88; }
.rf-hl-exec-pin      { color: #f59e0b !important; font-weight: 600; border-bottom: 1.5px dotted #f59e0b88; }
.rf-hl-data-pin      { color: #82aaff !important; font-weight: 600; border-bottom: 1.5px dotted #82aaff88; }
.rf-hl-run           { color: #c3e88d !important; font-weight: 700; border-bottom: 1.5px dotted #c3e88d88; }
.rf-hl-ctx-type      { color: #89ddff !important; border-bottom: 1.5px dotted #89ddff66; }
.rf-hl-ctx-call      { color: #f78c6c !important; border-bottom: 1.5px dotted #f78c6c88; }
`

let styleInjected = false
function ensureStyle() {
  if (styleInjected) return
  styleInjected = true
  const el = document.createElement('style')
  el.textContent = STYLE
  document.head.appendChild(el)
}

// ── Caché de decoraciones por versión de documento ───────────────────────────

function buildDecorations(view: EditorView): DecorationSet {
  ensureStyle()
  const builder = new RangeSetBuilder<Decoration>()
  const doc = view.state.doc
  const text = doc.toString()

  // Recolectar todos los matches con su posición absoluta
  const marks: { from: number; to: number; cls: string }[] = []

  for (const tok of TOKENS) {
    tok.pattern.lastIndex = 0
    let m: RegExpExecArray | null
    while ((m = tok.pattern.exec(text)) !== null) {
      marks.push({ from: m.index, to: m.index + m[0].length, cls: tok.cls })
    }
  }

  // Ordenar por posición para que RangeSetBuilder sea feliz
  marks.sort((a, b) => a.from - b.from || a.to - b.to)

  // Eliminar solapamientos (el primer match gana)
  const deduped: typeof marks = []
  let lastTo = -1
  for (const m of marks) {
    if (m.from >= lastTo) {
      deduped.push(m)
      lastTo = m.to
    }
  }

  for (const { from, to, cls } of deduped) {
    builder.add(from, to, Decoration.mark({ class: cls }))
  }

  return builder.finish()
}

// ── ViewPlugin ───────────────────────────────────────────────────────────────

export const rayflowHighlight = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet
    constructor(view: EditorView) {
      this.decorations = buildDecorations(view)
    }
    update(update: ViewUpdate) {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = buildDecorations(update.view)
      }
    }
  },
  { decorations: v => v.decorations }
)

// ── Tooltip en hover ─────────────────────────────────────────────────────────

export const rayflowTooltip = hoverTooltip((view, pos) => {
  const text = view.state.doc.toString()

  for (const tok of TOKENS) {
    tok.pattern.lastIndex = 0
    let m: RegExpExecArray | null
    while ((m = tok.pattern.exec(text)) !== null) {
      const matchStart = m.index
      const matchEnd = m.index + m[0].length
      if (pos >= matchStart && pos <= matchEnd) {
        return {
          pos: matchStart,
          end: matchEnd,
          above: true,
          create() {
            const dom = document.createElement('div')
            dom.style.cssText = `
              background: #1e1e2e;
              border: 1px solid #383854;
              border-radius: 6px;
              padding: 8px 12px;
              max-width: 340px;
              font-family: system-ui, sans-serif;
              font-size: 12px;
              line-height: 1.5;
              color: #e2e8f0;
            `
            const title = document.createElement('div')
            title.style.cssText = 'font-weight: 600; margin-bottom: 4px; color: #94a3b8; text-transform: uppercase; font-size: 10px; letter-spacing: 0.05em;'
            title.textContent = tok.label

            const body = document.createElement('div')
            body.style.cssText = 'color: #e2e8f0;'
            body.textContent = tok.detail

            dom.appendChild(title)
            dom.appendChild(body)
            return { dom }
          },
        }
      }
    }
  }
  return null
})
