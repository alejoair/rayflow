import { useState, useEffect } from 'react';
import { fetchNodes } from '../services/api';
import type { NodeFile } from '../types/node';

export function NodeEditor() {
  const [nodes, setNodes] = useState<NodeFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadNodes();
  }, []);

  async function loadNodes() {
    try {
      setLoading(true);
      const data = await fetchNodes();
      setNodes(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load nodes');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1>RayFlow Editor</h1>

      <div>
        <h2>Available Nodes</h2>
        {loading && <p>Loading nodes...</p>}
        {error && <p style={{ color: 'red' }}>Error: {error}</p>}

        {!loading && !error && (
          <ul>
            {nodes.length === 0 ? (
              <li>No nodes found. Create .py files in the nodes/ directory.</li>
            ) : (
              nodes.map(node => (
                <li key={node.path}>
                  <strong>{node.name}</strong> - {node.path}
                </li>
              ))
            )}
          </ul>
        )}
      </div>
    </div>
  );
}
