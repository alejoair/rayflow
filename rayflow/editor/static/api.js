const json = body => ({
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

async function apiFetch(url, opts = {}) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || r.statusText);
  }
  if (r.status === 204) return null;
  return r.json();
}

// Flows
export const getNodes = () => apiFetch('/editor/nodes');
export const getFlows = () => apiFetch('/editor/flows');
export const getFlow = name => apiFetch(`/editor/flows/${encodeURIComponent(name)}`);
export const createFlow = body => apiFetch('/editor/flows', { method: 'POST', ...json(body) });
export const updateFlow = (name, body) => apiFetch(`/editor/flows/${encodeURIComponent(name)}`, { method: 'PUT', ...json(body) });
export const deleteFlow = name => apiFetch(`/editor/flows/${encodeURIComponent(name)}`, { method: 'DELETE' });
export const validateFlow = body => apiFetch('/editor/validate', { method: 'POST', ...json(body) });
export const typeCheck = (from_type, to_type) => apiFetch('/editor/type-check', { method: 'POST', ...json({ from_type, to_type }) });
export const runFlow = (name, inputs) => apiFetch(`/editor/flows/${encodeURIComponent(name)}/run`, { method: 'POST', ...json(inputs) });

// Custom nodes
export const listCustomNodeFiles = () => apiFetch('/editor/custom-nodes/files');
export const getCustomNodeFile = filename => apiFetch(`/editor/custom-nodes/files/${encodeURIComponent(filename)}`);
export const saveCustomNodeFile = (filename, content) => apiFetch(`/editor/custom-nodes/files/${encodeURIComponent(filename)}`, { method: 'PUT', ...json({ content }) });
export const deleteCustomNodeFile = filename => apiFetch(`/editor/custom-nodes/files/${encodeURIComponent(filename)}`, { method: 'DELETE' });
export const reloadCatalog = () => apiFetch('/editor/custom-nodes/reload', { method: 'POST' });
