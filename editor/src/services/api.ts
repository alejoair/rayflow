import type { NodeFile } from '../types/node';

const API_BASE = '/api';

export async function fetchNodes(): Promise<NodeFile[]> {
  const response = await fetch(`${API_BASE}/nodes`);
  if (!response.ok) {
    throw new Error('Failed to fetch nodes');
  }
  return response.json();
}
