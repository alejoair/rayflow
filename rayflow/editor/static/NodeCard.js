import { html } from 'htm/react';
import { Handle, Position } from '@xyflow/react';
import { typeColor } from './translator.js';

function DataPin({ name, type, isOutput }) {
  const color = typeColor(type);
  const side = isOutput ? Position.Right : Position.Left;
  return html`
    <div class=${`rf-pin-row ${isOutput ? 'output' : ''}`} style=${{ position: 'relative', paddingLeft: isOutput ? 8 : 24, paddingRight: isOutput ? 24 : 8 }}>
      ${!isOutput && html`
        <${Handle} type="target" position=${side} id=${`data-in-${name}`}
          style=${{ background: 'var(--surface)', borderColor: color, left: 6 }} />
      `}
      <span class="rf-pin-label">${name}</span>
      <span class="rf-pin-type" style=${{ color }}>${type}</span>
      ${isOutput && html`
        <${Handle} type="source" position=${side} id=${`data-out-${name}`}
          style=${{ background: 'var(--surface)', borderColor: color, right: 6 }} />
      `}
    </div>
  `;
}

export default function NodeCard({ data, selected }) {
  const { nodeType, meta, dynamicOutputs, dynamicInputs, hasError } = data;

  const classes = ['rf-node', selected && 'selected', hasError && 'has-error'].filter(Boolean).join(' ');

  if (!meta && !dynamicOutputs && !dynamicInputs) {
    return html`
      <div class=${classes + ' has-error'} style=${{ minWidth: 140 }}>
        <div class="rf-node-header"><span>${nodeType}</span></div>
        <div class="rf-pin-row" style=${{ color: 'var(--error-color)', fontSize: 11, padding: '4px 10px' }}>Tipo desconocido</div>
      </div>
    `;
  }

  const hasExecIn = meta?.has_exec_in ?? (nodeType === 'FlowOutput');
  const execOutputs = meta?.exec_outputs ?? (nodeType === 'FlowInput' || nodeType === 'OnStart' ? ['exec_out'] : []);
  const staticInputs = meta?.inputs ?? [];
  const staticOutputs = meta?.outputs ?? [];

  // Dynamic pins override static ones for boundary nodes
  const dynOuts = dynamicOutputs || [];   // [[name, type], ...]
  const dynIns  = dynamicInputs  || [];   // [[name, type], ...]
  const showStaticIns  = dynIns.length  === 0 ? staticInputs  : [];
  const showStaticOuts = dynOuts.length === 0 ? staticOutputs : [];

  return html`
    <div class=${classes}>
      <div class="rf-node-header" style=${{ position: 'relative',
        paddingLeft: hasExecIn ? 24 : 10,
        paddingRight: execOutputs.length > 0 ? 24 : 10 }}>
        ${hasExecIn && html`
          <${Handle} type="target" position=${Position.Left} id="exec-in"
            style=${{ background: 'var(--exec-color)', borderColor: 'var(--exec-color)', width: 12, height: 12, left: 6 }} />
        `}
        ${execOutputs.length > 0 && html`
          <${Handle} type="source" position=${Position.Right} id=${`exec-out-${execOutputs[0]}`}
            style=${{ background: 'var(--exec-color)', borderColor: 'var(--exec-color)', width: 12, height: 12, right: 6 }} />
        `}
        ${hasExecIn && html`<span class="rf-node-header-dot"></span>`}
        <span>${nodeType}</span>
      </div>

      ${execOutputs.length > 1 && execOutputs.slice(1).map(pin => html`
        <div key=${pin} class="rf-pin-row output" style=${{ paddingRight: 28, position: 'relative' }}>
          <span class="rf-pin-label" style=${{ color: 'var(--exec-color)', fontSize: 11 }}>${pin}</span>
          <${Handle} type="source" position=${Position.Right} id=${`exec-out-${pin}`}
            style=${{ background: 'var(--exec-color)', borderColor: 'var(--exec-color)', width: 12, height: 12, right: 6 }} />
        </div>
      `)}

      <div class="rf-node-body">
        ${showStaticIns.map(p => html`<${DataPin} key=${p.name} name=${p.name} type=${p.type} isOutput=${false} />`)}
        ${dynIns.map(([name, type]) => html`<${DataPin} key=${name} name=${name} type=${type} isOutput=${false} />`)}
        ${showStaticOuts.map(p => html`<${DataPin} key=${p.name} name=${p.name} type=${p.type} isOutput=${true} />`)}
        ${dynOuts.map(([name, type]) => html`<${DataPin} key=${name} name=${name} type=${type} isOutput=${true} />`)}

        ${showStaticIns.length === 0 && dynIns.length === 0
          && showStaticOuts.length === 0 && dynOuts.length === 0
          && !hasExecIn && execOutputs.length === 0 && html`
          <div class="rf-pin-row" style=${{ color: 'var(--text-muted)', fontSize: 11, fontStyle: 'italic', padding: '4px 10px' }}>sin pines</div>
        `}
      </div>
    </div>
  `;
}
