"""Flow showcase — usa todas las capacidades de rayflow:
  FlowInput, Parallel (fork/join), ForEach x2, Branch, Sequence,
  Set/Get (variables), Add, GreaterThan, ToStr, fan-out exec, pin meta, FlowOutput.

Escenario:
  Dado un array de enteros y un umbral:
  - Rama 0: suma todos los elementos (ForEach + Get + Add + Set)
  - Rama 1: cuenta cuántos superan el umbral (ForEach + GreaterThan + Branch + Get + Add + Set)
  Tras el fork/join (Parallel.joined):
  - Sequence dispara en orden: ToStr(total), ToStr(count), FlowOutput
  FlowOutput incluye el pin meta del nodo Parallel.
"""
import ray
import rayflow

ray.init(ignore_reinit_error=True)

FLOW = {
    "name": "showcase",
    "version": "1",
    "inputs":  {"numbers": "list", "threshold": "int"},
    "outputs": {"total": "int", "above_count": "int", "parallel_meta": "dict"},
    "variables": [
        {"name": "running_total", "type": "int", "default": 0},
        {"name": "above_count",   "type": "int", "default": 0},
    ],
    "nodes": [
        {"id": "entry", "type": "FlowInput"},

        # ── fork/join ──────────────────────────────────────────────────
        # Cada rama escribe en su propia variable — sin carrera de datos
        {"id": "par", "type": "Parallel", "exec_in": "entry"},

        # ── Rama 0: sumar todos los elementos ─────────────────────────
        # Get es pure (sin exec) — se evalúa bajo demanda al resolver inputs de Add
        {"id": "foreach_sum", "type": "ForEach",
         "exec_in": "par.branch_0",
         "inputs": {"array": "entry.numbers"}},

        {"id": "get_total", "type": "Get",
         "inputs": {"variable_name": "running_total"}},

        {"id": "add_elem", "type": "Add",
         "exec_in": "foreach_sum.loop_body",
         "inputs": {"a": "get_total.value", "b": "foreach_sum.element"}},

        {"id": "set_total", "type": "Set",
         "exec_in": "add_elem",
         "inputs": {"variable_name": "running_total", "value": "add_elem.result"}},

        # ── Rama 1: contar elementos > threshold ──────────────────────
        {"id": "foreach_count", "type": "ForEach",
         "exec_in": "par.branch_1",
         "inputs": {"array": "entry.numbers"}},

        {"id": "gt", "type": "GreaterThan",
         "exec_in": "foreach_count.loop_body",
         "inputs": {"a": "foreach_count.element", "b": "entry.threshold"}},

        {"id": "branch_above", "type": "Branch",
         "exec_in": "gt",
         "inputs": {"condition": "gt.result"}},

        {"id": "get_count", "type": "Get",
         "inputs": {"variable_name": "above_count"}},

        {"id": "add_count", "type": "Add",
         "exec_in": "branch_above.true",
         "inputs": {"a": "get_count.value", "b": 1}},

        {"id": "set_count", "type": "Set",
         "exec_in": "add_count",
         "inputs": {"variable_name": "above_count", "value": "add_count.result"}},

        # ── joined: Sequence dispara 3 nodos en orden ─────────────────
        {"id": "seq", "type": "Sequence", "exec_in": "par.joined"},

        {"id": "get_final_total", "type": "Get",
         "inputs": {"variable_name": "running_total"}},

        {"id": "get_final_count", "type": "Get",
         "inputs": {"variable_name": "above_count"}},

        {"id": "total_str",  "type": "ToStr", "exec_in": "seq.then_0",
         "inputs": {"value": "get_final_total.value"}},

        {"id": "count_str",  "type": "ToStr", "exec_in": "seq.then_1",
         "inputs": {"value": "get_final_count.value"}},

        {"id": "exit", "type": "FlowOutput", "exec_in": "seq.then_2",
         "inputs": {
             "total":         "get_final_total.value",
             "above_count":   "get_final_count.value",
             "parallel_meta": "par.meta",
         }},
    ],
}

NUMBERS   = [3, 7, 1, 15, 4, 9, 2, 11]
THRESHOLD = 6

expected_total = sum(NUMBERS)
expected_above = sum(1 for n in NUMBERS if n > THRESHOLD)

print(f"Input : numbers={NUMBERS}, threshold={THRESHOLD}")
print(f"Esperado: total={expected_total}, above_count={expected_above}")
print()

result = rayflow.run(FLOW, numbers=NUMBERS, threshold=THRESHOLD)

total       = result["total"]
above_count = result["above_count"]
pmeta       = result["parallel_meta"]

print(f"total       = {total}  {'OK' if total == expected_total else f'FAIL esperado {expected_total}'}")
print(f"above_count = {above_count}  {'OK' if above_count == expected_above else f'FAIL esperado {expected_above}'}")
print()
print("parallel_meta:")
for k, v in pmeta.items():
    print(f"  {k}: {v}")
