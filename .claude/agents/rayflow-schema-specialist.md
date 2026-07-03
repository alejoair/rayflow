---
name: rayflow-schema-specialist
description: "Especialista en el sistema `schema` de rayflow. Flow JSON schema (FlowDef/NodeDef plain stdlib @dataclass models, not Pydantic — no pydantic dependency exists in this project) and the canonical data-pin type system (int/str/list[T]/dict[str,V]/Any) with... Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
tools: Read, Grep, Glob, Edit, Agent, SendMessage
model: inherit
---

<!--
  ARCHIVO GENERADO — no editar a mano, se sobreescribe en cada commit.
  Fuente: rayflow_file_map.json (archivos, descripciones, dependencias entre
  sistemas) + RAYFLOW_SOURCE_OF_TRUTH.json (claims cuya evidencia cae en
  este sistema) + rayflow_issues.json (issues abiertos que lo mencionan).
  Regenerado por scripts/generate_specialist_agents.py, wireado como hook
  `agents-generate` en .pre-commit-config.yaml (stage pre-commit). Ver
  rayflow_agents_system.md.
-->

# Especialista: sistema `schema`

Flow JSON schema (FlowDef/NodeDef plain stdlib @dataclass models, not Pydantic — no pydantic dependency exists in this project) and the canonical data-pin type system (int/str/list[T]/dict[str,V]/Any) with compatibility rules. Foundational — almost every other backend system imports from here.

## Archivos (`rayflow_file_map.json` → `systems.schema.files`)

| archivo | descripción |
|---|---|
| `rayflow/schema/__init__.py` | Re-exports the schema dataclasses (PinKind, PinDef, NodeDef, FlowDef, VariableDef) and load_flow. |
| `rayflow/schema/loader.py` | Parses a flow JSON (file, path, or dict) into a FlowDef (no `inputs` field — entries declare their own Input pins), and detects unknown/typo'd schema keys to surface as validation warnings. `inputs` is no longer a recognized top-level key. |
| `rayflow/schema/models.py` | The flow JSON schema's dataclasses: NodeDef, FlowDef (no longer has an `inputs` field — inputs live on the entry node's declared Input pins), VariableDef, PinDef/PinKind, including the internal fields flatten() uses to track CallFlow splicing. |
| `rayflow/types.py` | The data-pin type system: closed registry of primitives (int/float/str/bool/list/dict/Any), generics (list[T], dict[str,V]), and strict compatibility checking with no implicit coercion. |

## Dependencias entre sistemas

Depende de: _(ningún otro sistema)_

Es dependencia de: `build`, `editor-api`, `mcp`, `nodes`, `server`, `tests`

## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)

### Sistema de nodos > Nodos de entrada (@entry_node)

- **sistema-de-nodos-entrada#campo-inputs-flow-flowdef-ya-existe**: El campo inputs del flow (FlowDef) ya no existe en el schema (rayflow/schema/models.py) — los inputs de un flow viven exclusivamente en los Input que su entry declara, poblados por nombre desde el body HTTP. — evidencia: `rayflow/schema/models.py#FlowDef`, `rayflow/schema/loader.py#_FLOW_KEYS`

### Schema de un flow (JSON)

- **schema-de-un-flow#ejemplo-schema-name-version-outputs-variables**: Ejemplo de schema: name, version, outputs, variables, events, nodes — sin campo inputs. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#hay-campo-inputs-nivel-flow-inputs**: No hay campo inputs a nivel de flow — los inputs viven en los Input que el propio nodo de entrada declara; para leerlos downstream se wirea entry.<nombre_del_pin> igual que cualquier otro pin. — evidencia: `rayflow/schema/models.py#FlowDef`, `rayflow/schema/loader.py#_FLOW_KEYS`
- **schema-de-un-flow#flowinput-existe-alias-onstart-compatibilidad-hacia**: FlowInput existe como alias de OnStart por compatibilidad hacia atrás, pero el nombre canónico es OnStart. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#flows-guardan-flows-dentro-directorio-trabajo**: Los flows se guardan en flows/ dentro del directorio de trabajo. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#todo-flow-disparado-via-post-flows**: Todo flow disparado vía POST /flows/{name}/run — sea servido o del editor — se dispara por una request HTTP real. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#onstart-declara-body-headers-query-method**: OnStart declara body/headers/query/method como sus propios Input pins (defaults vacíos), así que cualquier flow con OnStart como entry los tiene disponibles gratis; un entry custom que los quiera debe declararlos él mismo. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#downstream-cualquier-nodo-lee-wireando-entry**: Downstream, cualquier nodo los lee wireando entry.headers, etc., como cualquier otro pin. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#flow-corre-via-http-mcp-execute**: Si el flow no corre vía HTTP (MCP, execute() directo), esos pines caen al default del Input que los consume (llegan vacíos). — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#ctx-set-response-status-code-ctx**: ctx.set_response_status(code) / ctx.set_response_header(name, value) (en ExecContext) fijan el status/headers HTTP reales de la respuesta — viven en el RunContext de la ejecución (no en flow.outputs), así que no aparecen en el resultado que ve un caller no-HTTP. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#sin-llamarlos-default-200-sin-headers**: Sin llamarlos, el default es 200 sin headers extra. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#cuidado-parallel-dos-ramas-verdaderamente-paralelas**: Cuidado con Parallel: si dos ramas verdaderamente paralelas llaman set_response_status a la vez, gana la última escritura — solo una rama de un fork debería fijarlos. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`
- **schema-de-un-flow#ejemplo-codigo-nodo-checkapikey-engine-node**: Ejemplo de código: nodo CheckApiKey (@engine_node normal) que compara headers.get("x-api-key") contra una env var y usa set_response_status(401) en el camino denegado. — evidencia: `rayflow/schema/models.py`, `rayflow/schema/loader.py`, `rayflow/nodes/builtin/control.py`, `rayflow/server.py`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `0b1bd0e`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
