const { useState, useEffect } = React;

function NodeList() {
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadNodes();
  }, []);

  async function loadNodes() {
    try {
      setLoading(true);
      const response = await fetch('/api/nodes');
      if (!response.ok) throw new Error('Failed to fetch nodes');
      const data = await response.json();
      setNodes(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold mb-4">Available Nodes</h2>
      
      {loading && (
        <p className="text-gray-500">Loading nodes...</p>
      )}
      
      {error && (
        <p className="text-red-500">Error: {error}</p>
      )}

      {!loading && !error && (
        <ul className="space-y-2">
          {nodes.length === 0 ? (
            <li className="text-gray-500 italic">
              No nodes found. Create .py files in the nodes/ directory.
            </li>
          ) : (
            nodes.map(node => (
              <li 
                key={node.path}
                className="p-3 border border-gray-200 rounded hover:bg-gray-50 cursor-pointer transition"
              >
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-gray-800">{node.name}</span>
                  <span className={`px-2 py-1 text-xs rounded ${
                    node.type === 'builtin' 
                      ? 'bg-blue-100 text-blue-800' 
                      : 'bg-green-100 text-green-800'
                  }`}>
                    {node.type}
                  </span>
                </div>
                <div className="text-sm text-gray-500 mt-1">{node.path}</div>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
