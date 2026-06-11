"""Carga el grafo desde examples/suma.json y lo ejecuta con Ray."""
from pathlib import Path

import rayflow

flow_path = Path(__file__).parent / "suma.json"

result = rayflow.run(str(flow_path), a=7, b=35)
print("Resultado del flow:", result)
assert result == {"result": 42}, f"Esperaba 42, obtuve {result}"
print("OK: 7 + 35 = 42")
