"""Prueba los nodos de control: Branch, ForEach, Sequence, Get/Set."""
from pathlib import Path
import rayflow

HERE = Path(__file__).parent

# --------------------------------------------------------------------------
# 1. Branch — rama true: x + 100, rama false: x - 100
# --------------------------------------------------------------------------
result = rayflow.run(str(HERE / "branch_demo.json"), x=10, use_positive=True)
assert result == {"result": 110}, result
print("OK Branch (true):  10 + 100 =", result["result"])

result = rayflow.run(str(HERE / "branch_demo.json"), x=10, use_positive=False)
assert result == {"result": -90}, result
print("OK Branch (false): 10 - 100 =", result["result"])

# --------------------------------------------------------------------------
# 2. ForEach — cuenta los elementos de una lista usando Get/Set
# --------------------------------------------------------------------------
result = rayflow.run(str(HERE / "foreach_demo.json"), items=["a", "b", "c", "d"])
assert result == {"count": 4}, result
print("OK ForEach: len(['a','b','c','d']) =", result["count"])

result = rayflow.run(str(HERE / "foreach_demo.json"), items=[])
assert result == {"count": 0}, result
print("OK ForEach: len([]) =", result["count"])

# --------------------------------------------------------------------------
# 3. Sequence — suma a, b, c en orden usando Get/Set entre pasos
# --------------------------------------------------------------------------
result = rayflow.run(str(HERE / "sequence_demo.json"), a=1, b=2, c=3)
assert result == {"total": 6}, result
print("OK Sequence: 1 + 2 + 3 =", result["total"])

print("\nTodos los nodos de control pasaron.")
