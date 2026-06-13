import { html } from 'htm/react';
import { useState, useEffect, useRef, useCallback } from 'react';
import { basicSetup, EditorView } from 'codemirror';
import { EditorState } from '@codemirror/state';
import { python } from '@codemirror/lang-python';
import { oneDark } from '@codemirror/theme-one-dark';
import { saveCustomNodeFile, deleteCustomNodeFile, reloadCatalog } from './api.js';

const TEMPLATE = `from rayflow.nodes.decorators import engine_node, ray_node, ExecContext, ExecInput, ExecOutput, Input, Output


@engine_node
class MyNode:
    """Descripción del nodo."""
    exec_in = ExecInput()
    value = Input("int", default=0)
    result = Output("int")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, value: int) -> None:
        ctx.set_output("result", value)
        await ctx.fire("exec_out")
`;

function CodeMirrorEditor({ value, onChange, isActive }) {
  const containerRef = useRef(null);
  const viewRef = useRef(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    if (!containerRef.current) return;

    const updateListener = EditorView.updateListener.of(update => {
      if (update.docChanged) onChangeRef.current(update.state.doc.toString());
    });

    const state = EditorState.create({
      doc: value,
      extensions: [
        basicSetup,
        python(),
        oneDark,
        updateListener,
        EditorView.theme({
          '&': { height: '100%', fontSize: '13px' },
          '.cm-scroller': { overflow: 'auto', fontFamily: "'JetBrains Mono', 'Fira Code', monospace" },
          '.cm-content': { padding: '8px 0' },
        }),
      ],
    });

    const view = new EditorView({ state, parent: containerRef.current });
    viewRef.current = view;
    return () => { view.destroy(); viewRef.current = null; };
  }, []); // create once

  // Sync external value (e.g. file switched)
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const current = view.state.doc.toString();
    if (current !== value) {
      view.dispatch({ changes: { from: 0, to: current.length, insert: value } });
    }
  }, [value]);

  return html`<div ref=${containerRef} class="cm-wrap" style=${{ flex: 1, overflow: 'hidden', minHeight: 0 }} />`;
}

export default function NodeEditorTab({ filename, initialContent, isActive, onDirtyChange, onFileDeleted, onCatalogReloaded, onToast }) {
  const [content, setContent] = useState(initialContent ?? TEMPLATE);
  const [saving, setSaving] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const initialRef = useRef(initialContent ?? TEMPLATE);

  function handleChange(val) {
    setContent(val);
    onDirtyChange(val !== initialRef.current);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await saveCustomNodeFile(filename, content);
      initialRef.current = content;
      onDirtyChange(false);
      onToast(`${filename} guardado`, 'success');
    } catch (e) {
      onToast(`Error guardando: ${e.message}`, 'error');
    } finally {
      setSaving(false);
    }
  }

  async function handleReload() {
    setReloading(true);
    try {
      const catalog = await reloadCatalog();
      onCatalogReloaded(catalog);
      onToast('Catálogo recargado ✓', 'success');
    } catch (e) {
      onToast(`Error recargando: ${e.message}`, 'error');
    } finally {
      setReloading(false);
    }
  }

  async function handleDelete() {
    try {
      await deleteCustomNodeFile(filename);
      onFileDeleted(filename);
    } catch (e) {
      onToast(`Error borrando: ${e.message}`, 'error');
    }
  }

  const saveAndReload = useCallback(async () => {
    await handleSave();
    await handleReload();
  }, [content, filename]);

  return html`
    <div class="flow-tab" style=${{ display: isActive ? 'flex' : 'none' }}>

      <!-- Toolbar -->
      <div class="tab-toolbar">
        <span style=${{ color: 'var(--type-str)', fontWeight: 600, fontSize: 12 }}>🐍</span>
        <span class="tab-toolbar-name">${filename}</span>
        <div style=${{ flex: 1 }} />
        <button class="btn btn-sm" onClick=${handleSave} disabled=${saving}>
          ${saving ? 'Guardando…' : '💾 Guardar'}
        </button>
        <button class="btn btn-sm btn-primary" onClick=${saveAndReload} disabled=${saving || reloading} title="Guardar y recargar el catálogo de nodos">
          ${reloading ? '↺ Recargando…' : '↺ Guardar y recargar'}
        </button>
        <button class="btn btn-sm btn-danger" onClick=${() => setConfirmDelete(true)}>🗑</button>
      </div>

      <!-- Editor -->
      <div style=${{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>
        <${CodeMirrorEditor}
          value=${content}
          onChange=${handleChange}
          isActive=${isActive}
        />
      </div>

      ${confirmDelete && html`
        <div class="modal-overlay" onClick=${e => e.target===e.currentTarget && setConfirmDelete(false)}>
          <div class="modal">
            <div class="modal-title">¿Borrar "${filename}"?</div>
            <p style=${{ fontSize:13, color:'var(--text-muted)', marginTop:8 }}>Los nodos definidos en este archivo dejarán de estar disponibles.</p>
            <div class="modal-footer">
              <button class="btn" onClick=${() => setConfirmDelete(false)}>Cancelar</button>
              <button class="btn btn-danger" onClick=${handleDelete}>Borrar</button>
            </div>
          </div>
        </div>
      `}
    </div>
  `;
}
