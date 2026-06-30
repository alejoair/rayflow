"""Guía curada del modelo de Rayflow, servida por `GET /editor/guide`.

Es el "contrato semántico" que un agente LLM necesita para construir flows y que
hoy solo vivía en CLAUDE.md / docstrings del código. Texto plano en markdown.
"""

GUIDE = """\
# Guía para construir flows de Rayflow

Un flow es un grafo de nodos conectados por dos tipos de cable:
- **exec** (orden de ejecución): secuencial.
- **data** (valores): se evalúan en paralelo bajo demanda.

## Estructura de un flow (JSON)

```json
{
  "name": "mi_flow",
  "version": "1",
  "inputs":  { "x": "int" },
  "outputs": { "result": "int" },
  "variables": [{ "name": "contador", "type": "int", "default": 0 }],
  "events": [],
  "nodes": [
    { "id": "entry", "type": "OnStart" },
    { "id": "add", "type": "Add", "exec_in": "entry", "inputs": { "a": "entry.x", "b": 10 } },
    { "id": "exit", "type": "FlowOutput", "exec_in": "add", "inputs": { "result": "add.result" } }
  ]
}
```

## Reglas de cableado

- **Cada flow necesita un nodo de entrada**: `OnStart` (ejecución directa),
  `OnEvent` (disparado por evento) u `OnVariableChange` (cambio de variable).
- **Aristas exec**: se declaran DESDE el consumidor con `exec_in`:
  - `"exec_in": "node_id"` -> el exec output por defecto del nodo fuente.
  - `"exec_in": "node_id.pin"` -> un exec output concreto (`branch.true`, `seq.then_0`).
  - `"exec_in": ["a", "b"]` -> espera a ambos (join "and").
  - `"exec_in": {"or": ["a", "b"]}` -> el primero que llegue (join "or").
- **Aristas data**: en `inputs`, el valor es:
  - un literal del tipo correcto: `"b": 10`, `"flag": true`, `"name": "hola"`.
  - una referencia `"node_id.pin"`: `"a": "entry.x"`, `"result": "add.result"`.

## Pins dinámicos (no aparecen en /editor/nodes estático)

- `OnStart`/`FlowInput`/`OnEvent`: exponen un **data output por cada input del
  flow**. Si el flow declara `inputs: {x: int}`, puedes leer `entry.x`.
- `FlowOutput`: tiene un **data input requerido por cada output del flow**.
- `Parallel`: sus ramas `branch_0`, `branch_1`, … se descubren del wiring
  (nodos cuyo `exec_in` es `parallel_id.branch_N`); `joined` dispara al unir.
- `CallFlow`: acepta inputs arbitrarios mapeados al subflow.

Consulta `GET /editor/flows/{name}/catalog` para ver los pins ya resueltos de un
flow concreto.

## Sistema de tipos

Tipos canónicos (strings): `int`, `float`, `str`, `bool`, `list`, `dict`, `Any`,
más genéricos `list[T]` y `dict[str, V]`. Compatibilidad ESTRICTA: mismo tipo o
uno es `Any`. **int y float son incompatibles**: castea con `ToInt`/`ToFloat`/
`ToStr`/`ToBool`. Consulta `GET /editor/types`.

## Flujo de trabajo recomendado para un agente

1. `GET /editor/guide` y `GET /editor/nodes` para conocer el catálogo.
2. (Opcional) `GET /editor/examples/{name}` como plantilla.
3. Construir el flow JSON.
4. `POST /editor/validate` -> devuelve TODOS los errores y warnings de una vez.
5. Corregir hasta `valid: true`.
6. `POST /editor/flows` (crear) o `PUT /editor/flows/{name}` (actualizar).
7. `POST /editor/flows/{name}/test` con `{inputs, expected_outputs}` para
   verificar que hace lo esperado, o `POST /editor/flows/{name}/run` para ejecutar.
"""
