---
name: rayflow-build-specialist
description: "Especialista en el sistema `build` de rayflow. Validates a parsed FlowDef against the node catalog and produces an executable BuiltFlow: flattens CallFlow subflows into one namespace, checks type/wiring/cycle correctness, and either raises on first error or... Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
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

# Especialista: sistema `build`

Validates a parsed FlowDef against the node catalog and produces an executable BuiltFlow: flattens CallFlow subflows into one namespace, checks type/wiring/cycle correctness, and either raises on first error or collects every error in one pass for editor/MCP clients.

## Archivos (`rayflow_file_map.json` → `systems.build.files`)

| archivo | descripción |
|---|---|
| `rayflow/build/__init__.py` | Re-exports build() as the package's public symbol. |
| `rayflow/build/validator.py` | Validates a parsed FlowDef against the node catalog and produces an executable BuiltFlow: flattens CallFlow subflows into one namespace, checks type/wiring/cycle correctness, and either raises on first error (build()) or collects every error in one pass (validate_all()) for editor/MCP clients. _find_entry() picks the flow's sole @entry_node (meta.is_entry). _with_dynamic_pins() no longer injects flow.inputs as outputs — entries declare their own Input/Output; for entries without run() it mirrors each Input as a same-named Output (passthrough). _splice_subflow identifies the subflow's entry generically via catalog meta.is_entry (not by name) and re-exposes the entry's declared Inputs as the subflow boundary. |

## Dependencias entre sistemas

Depende de: `nodes`, `schema`

Es dependencia de: `editor-api`, `engine`, `mcp`, `server`, `tests`

## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)

### Sistema de nodos > Nodos de entrada (@entry_node)

- **sistema-de-nodos-entrada#flow-necesita-exactamente-nodo-entrada-punto**: Un flow necesita exactamente un nodo de entrada — el punto donde el engine arranca la ejecución. — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#red-seguridad-run-entry-dispara-ningun**: Red de seguridad: si el run() de un entry no dispara ningún exec output, el engine dispara exec_out automáticamente al terminar, para no dejar el flow trabado. — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#frontend-str-opcional-nombre-directorio-assets**: frontend (str, opcional): nombre de un directorio de assets estáticos (HTML/JS/CSS) hermano del archivo .py del nodo. Si el entry de un flow servido lo declara, create_app monta ese directorio en GET /flows/{name}/ui con StaticFiles(html=True). — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#hay-sumo-frontend-flow-garantizado-exactly**: Hay a lo sumo un frontend por flow (garantizado por exactly-one-entry). — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#directorio-resuelve-via-inspect-getfile-cls**: El directorio se resuelve vía inspect.getfile(cls).parent / frontend; para built-ins vive en rayflow/nodes/builtin/<bundle>/ y para custom en custom_nodes/<bundle>/. — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#directorio-declarado-existe-loguea-warning-ruta**: Si el directorio declarado no existe, se loguea un warning y la ruta /ui no se monta (no rompe el startup). — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#restricciones-validadas-decorar-valueerror-inmediato-entry**: Restricciones validadas al decorar (ValueError inmediato): @entry_node no puede declarar exec_in y debe declarar al menos un ExecOutput. — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-nodos-entrada#ray-node-rechaza-clase-ya-decorada**: @ray_node rechaza una clase ya decorada con @entry_node. — evidencia: `rayflow/nodes/decorators.py#entry_node`, `rayflow/build/validator.py#_find_entry`, `rayflow/nodes/builtin/control.py`, `rayflow/nodes/builtin/events.py`

### Sistema de eventos > Triggers por cambio de variable (OnVariableChange)

- **triggers-por-cambio-de-variable#entry-generico-mas-reconocido-find-entry**: Es un entry genérico más, reconocido por _find_entry vía meta.is_entry (no por nombre) igual que OnStart/OnEvent/ChatTrigger. — evidencia: `rayflow/build/validator.py#_find_entry`

### Archivos clave del backend

- **archivos-clave-del-backend#rayflow-build-validator-py-flatten-build**: rayflow/build/validator.py: flatten(), build(), validación de tipos. — evidencia: `rayflow/build/validator.py`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `c7fb55c`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
