"""Verifica el sistema de tipos estricto + casteo explícito, con Ray real."""
from pathlib import Path

import rayflow
from rayflow.build.validator import BuildError

HERE = Path(__file__).parent

# 1) El grafo de suma sigue funcionando (int + int -> int).
suma = rayflow.run(str(HERE / "suma.json"), a=7, b=35)
assert suma == {"result": 42}, suma
print("OK suma:", suma)

# 2) Casteo explícito int -> str vía nodo ToStr (nodo de datos = task de Ray).
cast = rayflow.run(str(HERE / "cast_demo.json"), n=42)
assert cast == {"texto": "42"}, cast
print("OK casteo explícito ToStr:", cast)

# 3) Conexión int -> float SIN casteo debe ser rechazada por el build.
bad_flow = {
    "name": "bad",
    "inputs": {"x": "int"},
    "outputs": {"y": "float"},
    "nodes": [
        {"id": "entry", "type": "FlowInput"},
        {"id": "exit", "type": "FlowOutput", "exec_in": "entry",
         "inputs": {"y": "entry.x"}},
    ],
}
try:
    rayflow.run(bad_flow, x=1)
    raise SystemExit("FALLO: se esperaba BuildError por int->float sin casteo")
except BuildError as e:
    print("OK rechazo int->float sin casteo:")
    print("   ", e)

# 4) Tipo desconocido debe ser rechazado por el registro cerrado.
unknown = {
    "name": "unknown_type",
    "inputs": {"x": "int32"},
    "outputs": {},
    "nodes": [{"id": "entry", "type": "FlowInput"}],
}
try:
    rayflow.run(unknown, x=1)
    raise SystemExit("FALLO: se esperaba BuildError por tipo desconocido")
except BuildError as e:
    print("OK rechazo tipo desconocido:")
    print("   ", e)

print("\nTodos los checks de tipos pasaron.")
