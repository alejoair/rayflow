import { html } from 'htm/react';
import { useState, useMemo, useEffect } from 'react';
import { listCustomNodeFiles } from './api.js';

const BUILTIN_TYPES = new Set([
  'OnStart','FlowInput','FlowOutput','Branch','Sequence','Parallel','ForEach','Map',
  'Get','Set','CallFlow','OnEvent','EmitEvent',
  'Add','GreaterThan','ToInt','ToFloat','ToStr','ToBool',
]);

export default function NodePalette({ catalog, onOpenFile }) {
  const [search, setSearch] = useState('');
  const [files, setFiles] = useState([]);

  useEffect(() => {
    listCustomNodeFiles().then(data => setFiles(data.files || [])).catch(() => {});
  }, []);

  // Allow parent to trigger file list refresh
  NodePalette._refresh = () => {
    listCustomNodeFiles().then(data => setFiles(data.files || [])).catch(() => {});
  };

  const { builtin, custom } = useMemo(() => {
    const q = search.toLowerCase();
    const all = Object.values(catalog).filter(n =>
      !q || n.type.toLowerCase().includes(q)
    );
    return {
      builtin: all.filter(n => BUILTIN_TYPES.has(n.type)),
      custom: all.filter(n => !BUILTIN_TYPES.has(n.type)),
    };
  }, [catalog, search]);

  function onDragStart(e, nodeType) {
    e.dataTransfer.setData('application/rayflow-node', nodeType);
    e.dataTransfer.effectAllowed = 'copy';
  }

  function renderItem(node) {
    const decorator = node.decorator || 'engine_node';
    return html`
      <div
        key=${node.type}
        class="palette-item"
        draggable
        onDragStart=${e => onDragStart(e, node.type)}
        title="Arrastra al canvas"
      >
        <span class="palette-item-name">${node.type}</span>
        <div class="palette-item-tags">
          ${node.is_exec_node
            ? html`<span class="tag tag-exec">exec</span>`
            : html`<span class="tag" style=${{ background:'#1c1917', color:'#a8a29e' }}>pure</span>`}
          ${decorator === 'engine_node' && html`<span class="tag tag-engine">engine</span>`}
          ${decorator === 'ray_node' && html`<span class="tag tag-ray">ray</span>`}
          ${decorator === 'parallel_node' && html`<span class="tag tag-parallel">parallel</span>`}
        </div>
      </div>
    `;
  }

  async function handleNewFile() {
    const name = prompt('Nombre del archivo (sin .py):');
    if (!name) return;
    const filename = name.endsWith('.py') ? name : `${name}.py`;
    onOpenFile(filename, null); // null content → editor starts with template
    setFiles(prev => prev.find(f => f.name === filename) ? prev : [...prev, { name: filename, size: 0 }]);
  }

  return html`
    <div class="sidebar">
      <div class="sidebar-header">Nodos</div>
      <div class="sidebar-body">
        <input
          class="search-input"
          placeholder="Buscar..."
          value=${search}
          onInput=${e => setSearch(e.target.value)}
        />
        ${builtin.length > 0 && html`
          <div class="palette-group-label">Builtin</div>
          ${builtin.map(renderItem)}
        `}
        ${custom.length > 0 && html`
          <div class="palette-group-label">Custom</div>
          ${custom.map(renderItem)}
        `}
        ${builtin.length === 0 && custom.length === 0 && html`
          <div style=${{ color: 'var(--text-muted)', fontSize: 12, padding: '16px 10px', textAlign: 'center' }}>Sin resultados</div>
        `}
      </div>

      <!-- Custom node files section -->
      <div style=${{ borderTop: '1px solid var(--border)', flexShrink: 0 }}>
        <div class="sidebar-header" style=${{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <span>Archivos custom</span>
          <button
            class="btn btn-sm"
            style=${{ fontSize: 11, padding: '2px 7px', marginLeft: 4 }}
            onClick=${handleNewFile}
            title="Nuevo archivo de nodos"
          >+ Nuevo</button>
        </div>
        <div style=${{ padding: '4px 6px', maxHeight: 160, overflowY: 'auto' }}>
          ${files.length === 0 && html`
            <div style=${{ fontSize: 11, color: 'var(--text-muted)', padding: '6px 4px' }}>
              Sin archivos custom
            </div>
          `}
          ${files.map(f => html`
            <div
              key=${f.name}
              class="palette-item"
              style=${{ cursor: 'pointer' }}
              onClick=${() => onOpenFile(f.name, undefined)}
            >
              <span style=${{ fontSize: 11, color: 'var(--type-str)' }}>🐍</span>
              <span class="palette-item-name" style=${{ fontSize: 11 }}>${f.name}</span>
            </div>
          `)}
        </div>
      </div>
    </div>
  `;
}
