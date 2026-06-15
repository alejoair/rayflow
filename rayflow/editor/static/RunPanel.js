import { html } from 'htm/react';
import { useState } from 'react';
import { runFlow } from './api.js';

export default function RunPanel({ activeFlow, validationErrors, isDirty, onSaveFirst }) {
  const [inputs, setInputs] = useState({});
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  if (!activeFlow) {
    return html`
      <div class="app-footer">
        <div class="run-panel" style=${{ color: 'var(--text-muted)', fontSize: 12 }}>Abre un flow para ejecutarlo</div>
      </div>
    `;
  }

  const flowInputs = activeFlow.inputs || {};

  function setInput(name, val) { setInputs(prev => ({ ...prev, [name]: val })); }

  async function handleRun() {
    // Auto-save if canvas has unsaved changes
    if (isDirty && onSaveFirst) {
      const ok = await onSaveFirst();
      if (!ok) return; // save failed, don't run
    }

    setRunning(true); setResult(null); setError(null);
    try {
      const coerced = {};
      Object.entries(flowInputs).forEach(([name, type]) => {
        const raw = inputs[name];
        if (raw === undefined || raw === '') return;
        const t = type.toLowerCase();
        if (t === 'int') coerced[name] = parseInt(raw, 10);
        else if (t === 'float') coerced[name] = parseFloat(raw);
        else if (t === 'bool') coerced[name] = raw === 'true' || raw === true;
        else if (t === 'list' || t === 'dict') { try { coerced[name] = JSON.parse(raw); } catch { coerced[name] = raw; } }
        else coerced[name] = raw;
      });
      const out = await runFlow(activeFlow.name, coerced);
      setResult(out);
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  const hasErrors = validationErrors.length > 0;

  return html`
    <div class="app-footer">
      <div class="run-panel">
        ${Object.keys(flowInputs).length > 0 && html`
          <div class="run-section">
            <div class="run-label">Inputs</div>
            ${Object.entries(flowInputs).map(([name, type]) => html`
              <div key=${name} style=${{ marginBottom: 6 }}>
                <label style=${{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 3, display:'block' }}>
                  ${name} <span style=${{ color: 'var(--type-any)' }}>(${type})</span>
                </label>
                <input
                  type=${type === 'int' || type === 'float' ? 'number' : 'text'}
                  class="prop-input"
                  style=${{ width: 140 }}
                  placeholder="${name}..."
                  value=${inputs[name] ?? ''}
                  onInput=${e => setInput(name, e.target.value)}
                />
              </div>
            `)}
          </div>
        `}

        <div class="run-section">
          ${isDirty && html`
            <div style=${{ fontSize: 11, color: 'var(--exec-color)', marginBottom: 4 }}>
              ⚠ Se guardará antes de ejecutar
            </div>
          `}
          <button class="btn btn-primary" onClick=${handleRun} disabled=${running || hasErrors}>
            ${running ? '⏳ Ejecutando...' : '▶ Ejecutar'}
          </button>
          ${hasErrors && html`
            <div style=${{ fontSize: 11, color: 'var(--error-color)', marginTop: 4 }}>
              ${validationErrors.length} error(es) de validación
            </div>
          `}
        </div>

        ${result !== null && html`
          <div class="run-section" style=${{ flex: 1 }}>
            <div class="run-label">Resultado</div>
            <pre class="run-output success">${JSON.stringify(result, null, 2)}</pre>
          </div>
        `}

        ${error !== null && html`
          <div class="run-section" style=${{ flex: 1 }}>
            <div class="run-label">Error</div>
            <pre class="run-output error">${error}</pre>
          </div>
        `}
      </div>
    </div>
  `;
}
