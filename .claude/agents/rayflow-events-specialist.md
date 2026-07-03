---
name: rayflow-events-specialist
description: "Especialista en el sistema `events` de rayflow. The EventBroker pub/sub bus: fire-and-forget publish/subscribe connecting EmitEvent nodes, OnEvent/OnVariableChange entry points, and cross-flow event-triggered execution. Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
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

# Especialista: sistema `events`

The EventBroker pub/sub bus: fire-and-forget publish/subscribe connecting EmitEvent nodes, OnEvent/OnVariableChange entry points, and cross-flow event-triggered execution.

## Archivos (`rayflow_file_map.json` → `systems.events.files`)

| archivo | descripción |
|---|---|
| `rayflow/events/__init__.py` | Re-exports EventBroker and get_event_broker. |
| `rayflow/events/bus.py` | The global EventBroker Ray actor: namespaced fire-and-forget pub/sub that lets one flow's EmitEvent trigger another flow's OnEvent/OnVariableChange. |

## Dependencias entre sistemas

Depende de: `server`

Es dependencia de: `cli`, `nodes`, `server`, `state`, `tests`

## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)

### Sistema de eventos

- **sistema-de-eventos#serve-events-flow-json-igual-load**: serve_events(flow_json): igual que load() + suscripción al broker vía EventBroker.subscribe(event_name, flow_name, graph_id). — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-eventos#emitevent-node-ctx-emit-event-name**: EmitEvent node -> ctx.emit_event(name, payload) -> EventBroker.publish(name, payload) (fire-and-forget) -> _run_event_flow.remote(flow_name, name, payload) (Ray task que corre en un worker) -> ray.get_actor("engine_{flow_name}") + ray.get_actor("queue_{flow_name}") por nombre -> engine.execute.remote({"payload": payload}, queue, run_id). — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-eventos#stop-graph-id-event-names-eventbroker**: stop(graph_id, event_names): EventBroker.unsubscribe() + unload(). — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-eventos#run-event-flow-corre-task-ray**: _run_event_flow corre como task @ray.remote en un worker distinto del proceso driver, donde el registry (rayflow.registry) está vacío. Por eso resuelve el flow receptor por sus actores detached con nombre (engine_{flow}/queue_{flow}), no con get_served(). — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-eventos#dispara-engine-execute-directamente-varios-eventos**: Como dispara engine.execute directamente, varios eventos sobre el mismo flow generan ejecuciones concurrentes — aisladas por el RunContext de cada una (sin lock). — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-eventos#matching-eventbroker-exacto-string-incluyendo-namespace**: El matching del EventBroker es exacto por string (incluyendo namespace, p.ej. "ventas/order_created"). — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`
- **sistema-de-eventos#nadie-esta-suscrito-evento-pierde-hay**: Si nadie está suscrito al evento, se pierde — no hay persistencia. — evidencia: `rayflow/events/bus.py`, `rayflow/api.py`, `rayflow/nodes/builtin/events.py`

### Archivos clave del backend

- **archivos-clave-del-backend#rayflow-events-bus-py-eventbroker-pub**: rayflow/events/bus.py: EventBroker — pub/sub fire-and-forget entre flows. — evidencia: `rayflow/events/bus.py`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `0b1bd0e`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
