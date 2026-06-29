# Propuesta de refactor: reificar el "run" (`RunContext`)

> Documento de diseño para ejecutar en una sesión nueva. Es autocontenido: no
> asume contexto de la conversación donde se originó. Describe el problema, su
> razón, el diseño y un plan incremental verificable.

## 1. Contexto y problema

Rayflow es un runtime que **fabrica sistemas residentes**: `load()` levanta un
sistema de actores (engine, GraphState, RunQueue, un actor por `@ray_node`) que
quedan vivos hasta `unload()`. Una invocación de ese sistema es un **run**.

El problema de fondo: **Rayflow tiene la palabra "run" pero no el concepto de
run como frontera de aislamiento.**

- En la capa de observabilidad el run **sí** es de primera clase: hay `run_id`,
  la `RunQueue` mantiene una sub-cola por `run_id`, los eventos van bracketeados
  (`run_start` … `flow_done`/`flow_error`), y se puede reconectar por `run_id`.
- En la capa de ejecución y estado el run **no** existe como objeto:
  - El estado por-run vive como **campos sueltos en el actor `FlowEngine`**:
    `self._run_id`, `self._run_queue`, `self._output_refs`, `self._exec_arrivals`
    (`rayflow/engine/executor.py`, en `FlowEngine.__init__` y `execute`). Son
    singulares → solo cabe un run a la vez.
  - Los **outputs de nodos** (`GraphState._node_outputs`,
    `rayflow/state/actor.py`) **no están scopeados por run**: persisten entre
    ejecuciones mezclados con la memoria persistente.

### Síntomas (todos la misma causa)

Esta media-reificación es la raíz de una familia de bugs. Tres ya se arreglaron
con parches; uno sigue latente:

| Síntoma | Estado | Parche actual |
|---|---|---|
| Dos `execute()` concurrentes se pisaban (compartían `self._run_id`/`_output_refs`) | Arreglado (parche) | `asyncio.Lock` `self._exec_lock` serializa `execute()` |
| Un join AND dentro de un loop se re-disparaba | Arreglado | reset de `exec_arrivals` en `_is_ready` |
| Un evento no disparaba al receptor (cross-process) | Arreglado | resolver por actores con nombre en `_run_event_flow` |
| **Outputs de nodos stale entre runs** | **NO arreglado** | — (lo resuelve este refactor) |

El `_exec_lock` es el ejemplo más claro de parche: **serializamos todos los runs
porque el engine solo tiene un juego de registros de trabajo.** Con un run
reificado, los runs serían aislados y el lock sobraría (recuperando la
concurrencia real que el actor async puede dar).

### El bug latente: outputs stale entre runs

`execute()` resetea `self._output_refs` y `self._exec_arrivals`, pero **nada
limpia `GraphState._node_outputs`** entre runs (no hay método ni llamada de
reset; verificado por grep — `_node_outputs` solo lo usa el engine, nadie en
`editor/`, `api.py` ni `server.py`). Consecuencia:

```
Run 1: Branch → true  → X se dispara, X.result = 100  (queda en GraphState)
Run 2: Branch → false → X NO se dispara
        un nodo Y que lee X.result se ejecuta igual
        → lee 100 (stale del run 1) en vez de su default
```

Esto contradice la semántica documentada ("default si el productor no se disparó
*en esta ejecución*").

## 2. Objetivo

Reificar el run como un objeto con frontera: **`RunContext`**, que posee todo el
scratch transitorio de un run. El engine pasa de "el run actual en `self`" a "un
diccionario de runs vivos".

Modelo conceptual a dejar limpio:

- **Persistente y compartido entre runs** (a propósito): variables del
  `GraphState` y el `self` de los actores `@ray_node`.
- **Efímero y aislado por run**: `run_id`, outputs de nodos, `exec_arrivals`,
  acumulador del resultado, handle de la cola.

## 3. Diseño

### 3.1 El objeto

```python
@dataclass
class RunContext:
    run_id: str
    queue: Any                                # handle a la RunQueue
    node_outputs: dict[str, dict[str, Any]]   # node_id → {pin → valor} (scratch por-run)
    exec_arrivals: dict[str, set[str]]        # readiness de joins
    output_refs: dict[str, Any]               # acumulador del resultado del flow
```

En `FlowEngine`:

```python
self._runs: dict[str, RunContext] = {}   # reemplaza _run_id/_run_queue/_output_refs/_exec_arrivals
```

### 3.2 El run se crea y se threadea (no se guarda en `self`)

```python
async def execute(self, flow_inputs, queue_ref, run_id):
    run = RunContext(run_id, queue_ref, {}, {}, {})
    for node_id, rnode in self._built.nodes.items():
        if rnode.exec_join == "and" and len(rnode.exec_sources) > 1:
            run.exec_arrivals[node_id] = set()
    self._runs[run_id] = run
    try:
        await self._write_node_outputs(run, self._built.entry_node_id, dict(flow_inputs))
        await self._run_loop(run, self._built.entry_node_id)
        result = _resolve_refs(run.output_refs)
        await queue_ref.push.remote(run_id, {"event": "flow_done", "result": result, "ts": time.time()})
        return result
    except Exception as e:
        await queue_ref.push.remote(run_id, {"event": "flow_error", "error": str(e), "ts": time.time()})
        raise
    finally:
        self._runs.pop(run_id, None)
```

Todos los métodos internos del engine reciben `run` como primer parámetro:
`_run_loop`, `_is_ready`, `_fire_node`, `_fire_engine_node`, `_fire_ray_node`,
`_fire_callflow_node`, `_local_fire`, `_resolve_inputs`, `_resolve_pin`,
`_eval_pure_engine_node`, `_emit_node_start`, `_emit_node_done`,
`_write_node_outputs`. Refactor amplio pero mecánico.

### 3.3 Los outputs de nodos viven en el `RunContext`

- `_write_node_outputs(run, node_id, outs)` escribe en `run.node_outputs` —
  **local y síncrono** (ya no `await self._state.set_node_outputs.remote(...)`).
- `_resolve_pin` lee de `run.node_outputs[src_id][src_pin]` — también local.
  Bonus: hoy cada data pin hace un round-trip remoto al `GraphState`
  (`await self._state.get_node_output.remote(...)`); pasa a ser acceso a dict.
- El "default si no se disparó en este run" sale gratis: `run.node_outputs`
  arranca vacío. La staleness desaparece por construcción.

### 3.4 El `ExecContext` lleva el `run_id` hasta los `ray_node`

`rayflow/nodes/decorators.py`. El `ExecContext` viaja serializado al worker;
hay que añadir `_run_id` y conservarlo en `__getstate__` (hoy excluye handles y
callbacks, pero `_run_id` es un string serializable y debe sobrevivir).

Las dos llamadas que un `ray_node` hace de vuelta al engine pasan a estar
scopeadas por run:

- `ctx.fire(pin)` → `engine.fire.remote(run_id, node_id, pin)`
- `ctx.set_output(pin, val)` → `engine.set_output.remote(run_id, node_id, pin, val)`

Para `engine_node`, los atajos locales (`_fire_handler` / `_output_writer`)
**capturan el `RunContext`** directamente (mismo mecanismo de hoy; ver
`_fire_engine_node`).

Métodos públicos del actor que cambian de firma (son internos, los llama el
`ExecContext`):

```python
async def fire(self, run_id, source_node_id, pin_name): run = self._runs[run_id]; ...
async def set_output(self, run_id, node_id, pin_name, value): self._runs[run_id].node_outputs...
# get_exec_outputs(node_id, exclude) NO necesita run: lee meta del BuiltFlow. Sin cambios.
```

### 3.5 El `GraphState` queda limpio: solo memoria persistente

`rayflow/state/actor.py`. Quitar `_node_outputs`, `set_node_outputs`,
`get_node_output`, `node_has_fired`. Conservar `_variables`, `get/set_variable`,
`get_all_variables`, y `watch_variable`/`unwatch_variable`/`_publish_change`
(la feature `OnVariableChange` vive del lado de variables y **no se toca**).

### 3.6 Eliminar el `_exec_lock`

Con el scratch aislado por run, dos `execute()` concurrentes no se pisan. Quitar
`self._exec_lock` y el `async with self._exec_lock:` de `execute()`. Esto
restaura la concurrencia real (el actor async puede intercalar runs). Lo único
compartido entre runs concurrentes pasa a ser lo que debe serlo: variables y el
`self` de los `ray_node`.

## 4. Plan incremental (cada paso = un commit verificable)

1. **Introducir `RunContext` y threadearlo**, manteniendo `node_outputs` todavía
   en `GraphState`. Es decir: sacar de `self` solo `_run_id`/`_run_queue`/
   `_output_refs`/`_exec_arrivals` → al `RunContext`. Quitar el `_exec_lock`.
   Correr la suite completa (debe seguir verde, incluida
   `test_ejecuciones_concurrentes_aisladas`).
2. **Mover `node_outputs` al `RunContext`** y volver local la resolución de
   datos. Adelgazar `GraphState`. Correr la suite.
3. **Añadir tests**: (a) outputs no-stale entre runs (el caso Branch del §1);
   (b) concurrencia sin lock (ya existe `test_ejecuciones_concurrentes_aisladas`
   en `tests/test_editor.py`, debe seguir pasando sin el lock).

Si un paso rompe algo, queda acotado a ese paso.

## 5. Verificación

- Suite completa: `python -m pytest tests/` (en este entorno usar
  `python -m pytest`, no el binario `pytest`, porque Ray vive en el intérprete
  del sistema; ver nota de entorno abajo).
- Test de no-staleness (nuevo): un flow con `Branch` donde el run 1 toma una
  rama y el run 2 la otra; un nodo que lee el output de la rama no tomada debe
  recibir su **default**, no el valor del run 1.
- Test de concurrencia (existente): N `execute_async` simultáneos con inputs
  distintos devuelven resultados correctos y aislados — debe pasar **sin** el
  `_exec_lock`.

## 6. Riesgos y cuidados

- Refactor del núcleo: cambia la firma de ~12 métodos internos del engine.
  Mecánico, pero cuidado con `_fire_callflow_node` (subflows) y con los atajos
  de `engine_node` (`_fire_handler`/`_output_writer`), que deben capturar el
  `RunContext` correcto.
- `ExecContext.__getstate__` **debe** incluir `_run_id`, o los `ray_node` no
  sabrían a qué run escribir.
- Revisar si algún test llama métodos del engine directamente (cambian de
  firma). Buscar usos de `.fire(` / `.set_output(` / `.execute(` en `tests/`.
- Un `@ray_node` stateful servido por dos runs concurrentes intercala sus
  mutaciones de `self`. Es el contrato existente de "estado compartido entre
  invocaciones", no una regresión — pero conviene **documentarlo** al quitar el
  lock (en `CLAUDE.md`, sección de serialización de `execute()`).

## 7. Qué NO tocar (invariantes a preservar)

- Variables persistentes entre runs (memoria del sistema).
- Estado en `self` de los `@ray_node` (memoria del actor).
- La feature `OnVariableChange` y `watch_variable` en `GraphState`.
- El contrato de `run()` de los nodos (`ctx.set_output` + `await ctx.fire`).
- La semántica de la `RunQueue` y los eventos SSE.

## 8. Estado del repo al escribir esto

- Rama de trabajo: `claude/rayflow-conceptual-analysis-8e07ju` (PR #6).
- Ya arreglados en esa rama: evento cross-process (`_run_event_flow` por actor
  con nombre), serialización de `execute()` (`_exec_lock` — que **este refactor
  elimina**), reset de readiness del join AND, y la feature `OnVariableChange`.
- Pendiente (lo que cubre este documento): la staleness de `node_outputs` y la
  reificación del run que la resuelve de raíz.
- Recomendación: hacer este refactor en **rama/PR aparte** (es del núcleo, merece
  su propia revisión; no mezclar con el PR #6 que ya acumula varios cambios).

### Nota de entorno (tests con Ray)

En el entorno de desarrollo, `pytest` puede estar instalado en un venv aislado
(de `uv`) que no ve `ray`. Correr los tests con el intérprete que sí tiene Ray:

```bash
python -m pip install ray fastapi uvicorn httpx pytest pytest-asyncio --ignore-installed packaging
python -m pytest tests/ -q
```
