import { html } from 'htm/react';

export default function TabBar({ tabs, activeTabId, onActivate, onClose }) {
  if (tabs.length === 0) return null;

  return html`
    <div class="tab-bar">
      ${tabs.map(tab => html`
        <div
          key=${tab.id}
          class=${'tab' + (tab.id === activeTabId ? ' active' : '')}
          onClick=${() => onActivate(tab.id)}
          title=${tab.label}
        >
          <span style=${{ marginRight: 4, opacity: 0.7 }}>
            ${tab.type === 'code' ? '🐍' : '⬡'}
          </span>
          <span class="tab-name">${tab.label}</span>
          ${tab.dirty && html`<span class="tab-dirty" title="Cambios sin guardar">●</span>`}
          <button
            class="tab-close"
            onClick=${e => { e.stopPropagation(); onClose(tab.id); }}
            title="Cerrar"
          >×</button>
        </div>
      `)}
    </div>
  `;
}
