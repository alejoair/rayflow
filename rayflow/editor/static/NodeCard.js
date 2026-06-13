import { html } from 'htm/react';
import { Handle, Position } from '@xyflow/react';
import { typeColor } from './translator.js';

export default function NodeCard({ data, selected }) {
  const { nodeType, meta } = data;

  if (!meta) {
    return html`
      <div class=${`rf-node ${selected ? 'selected' : ''} has-error`} style=${{ minWidth: 140 }}>
        <div class="rf-node-header"><span>${nodeType}</span></div>
        <div class="rf-node-body">
          <div class="rf-pin-row" style=${{ color: 'var(--error-color)', fontSize: 11, padding: '4px 10px' }}>
            Tipo desconocido
          </div>
        </div>
      </div>
    `;
  }

  const hasExecIn = meta.has_exec_in;
  const execOutputs = meta.exec_outputs || [];
  const inputs = meta.inputs || [];
  const outputs = meta.outputs || [];

  return html`
    <div class=${`rf-node ${selected ? 'selected' : ''}`}>
      <div class="rf-node-header" style=${{ position: 'relative', paddingLeft: hasExecIn ? 24 : 10, paddingRight: execOutputs.length > 0 ? 24 : 10 }}>
        ${hasExecIn && html`
          <${Handle}
            type="target"
            position=${Position.Left}
            id="exec-in"
            style=${{ background: 'var(--exec-color)', borderColor: 'var(--exec-color)', width: 12, height: 12, left: 6 }}
          />
        `}
        ${execOutputs.length > 0 && html`
          <${Handle}
            type="source"
            position=${Position.Right}
            id=${`exec-out-${execOutputs[0]}`}
            style=${{ background: 'var(--exec-color)', borderColor: 'var(--exec-color)', width: 12, height: 12, right: 6 }}
          />
        `}
        ${hasExecIn && html`<span class="rf-node-header-dot"></span>`}
        <span>${nodeType}</span>
      </div>

      ${execOutputs.length > 1 && execOutputs.slice(1).map(pin => html`
        <div key=${pin} class="rf-pin-row output" style=${{ paddingRight: 28, position: 'relative' }}>
          <span class="rf-pin-label" style=${{ color: 'var(--exec-color)', fontSize: 11 }}>${pin}</span>
          <${Handle}
            type="source"
            position=${Position.Right}
            id=${`exec-out-${pin}`}
            style=${{ background: 'var(--exec-color)', borderColor: 'var(--exec-color)', width: 12, height: 12, right: 6 }}
          />
        </div>
      `)}

      <div class="rf-node-body">
        ${inputs.map(p => {
          const color = typeColor(p.type);
          return html`
            <div key=${p.name} class="rf-pin-row" style=${{ paddingLeft: 24, position: 'relative' }}>
              <${Handle}
                type="target"
                position=${Position.Left}
                id=${`data-in-${p.name}`}
                style=${{ background: 'var(--surface)', borderColor: color, left: 6 }}
              />
              <span class="rf-pin-label">${p.name}</span>
              <span class="rf-pin-type" style=${{ color }}>${p.type}</span>
            </div>
          `;
        })}

        ${outputs.map(p => {
          const color = typeColor(p.type);
          return html`
            <div key=${p.name} class="rf-pin-row output" style=${{ paddingRight: 24, position: 'relative' }}>
              <span class="rf-pin-type" style=${{ color }}>${p.type}</span>
              <span class="rf-pin-label">${p.name}</span>
              <${Handle}
                type="source"
                position=${Position.Right}
                id=${`data-out-${p.name}`}
                style=${{ background: 'var(--surface)', borderColor: color, right: 6 }}
              />
            </div>
          `;
        })}

        ${inputs.length === 0 && outputs.length === 0 && !hasExecIn && execOutputs.length === 0 && html`
          <div class="rf-pin-row" style=${{ color: 'var(--text-muted)', fontSize: 11, fontStyle: 'italic', padding: '4px 10px' }}>sin pines</div>
        `}
      </div>
    </div>
  `;
}
