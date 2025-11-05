# Sistema de Variables Globales

## Concepto

Siguiendo el patrón de Unreal Engine Blueprints, las variables globales se manejan mediante **nodos GET y SET** que leen/escriben en un almacén centralizado de estado compartido.

```
┌─────────────┐ exec  ┌─────────────┐ exec  ┌─────────────┐
│ SET Variable│──────►│ Math Add    │──────►│ GET Variable│
│ name:counter│       │ x: counter  │       │ name:counter│
│ value: 0    │       │ y: 1        │       │ output: 0   │
└─────────────┘       └─────────────┘       └─────────────┘
```

## Arquitectura: GlobalVariableStore

**Actor Ray centralizado** que mantiene el estado global del flujo:

```python
@ray.remote
class GlobalVariableStore:
    """
    Actor único que almacena todas las variables globales.
    Compartido por todos los nodos del flujo.
    """
    def __init__(self):
        self.variables = {}  # {"variable_name": value}

    def get(self, variable_name):
        """Lee una variable"""
        return self.variables.get(variable_name, None)

    def set(self, variable_name, value):
        """Escribe una variable"""
        self.variables[variable_name] = value
        return True
```

## Integración con el Orquestador

**Diseño genérico:** El orquestador NO necesita saber qué nodos usan variables. Todos los nodos reciben la referencia al store en su constructor:

```python
class RayFlowOrchestrator:

    def __init__(self, graph_json):
        # 1. Crear store global único
        self.variable_store = GlobalVariableStore.remote()

        # 2. Crear todos los nodos pasándoles el store
        self.actors = {}
        for node in graph_json["nodes"]:
            actor_class = load_node_class(node["type"])

            # TODOS los nodos reciben el store
            self.actors[node["id"]] = actor_class.remote(
                store_ref=self.variable_store,
                config=node.get("config", {})
            )

    def execute_node(self, node_id, inputs):
        """
        Ejecución genérica - trata TODOS los nodos igual.
        El orquestador NO sabe qué tipo de nodo es.
        """
        actor = self.actors[node_id]
        result = ray.get(actor.process.remote(**inputs))
        return result
```

## Ejemplo Visual Completo

**Flujo: Contador incremental**

```
┌──────────────┐
│ Start Event  │
└──────┬───────┘
       │ exec
       ▼
┌──────────────────────┐
│ SET Variable         │  config: {"variable_name": "counter"}
│ value: 0             │  inputs: {"value": int}
└──────┬───────────────┘
       │ exec
       ▼
┌──────────────────────┐
│ GET Variable         │  config: {"variable_name": "counter"}
│                      │  outputs: {"value": int}
└──────┬───────────────┘
       │ exec + data(value)
       ▼
┌──────────────────────┐
│ Math Add             │  inputs: {"x": int, "y": int}
│ x: ◄── value         │  outputs: {"result": int}
│ y: 1                 │
└──────┬───────────────┘
       │ exec + data(result)
       ▼
┌──────────────────────┐
│ SET Variable         │  config: {"variable_name": "counter"}
│ value: ◄── result    │  inputs: {"value": int}
└──────┬───────────────┘
       │ exec
       ▼
┌──────────────────────┐
│ Print                │
│ msg: "Updated"       │
└──────────────────────┘
```

## Formato JSON

```json
{
  "nodes": [
    {
      "id": "node_001",
      "type": "set_variable",
      "config": {
        "variable_name": "counter"
      },
      "position": {"x": 100, "y": 100}
    },
    {
      "id": "node_002",
      "type": "get_variable",
      "config": {
        "variable_name": "counter"
      },
      "position": {"x": 100, "y": 200}
    },
    {
      "id": "node_003",
      "type": "math_add",
      "position": {"x": 100, "y": 300}
    }
  ],
  "connections": [
    {
      "from": "node_001",
      "fromExec": "finish",
      "to": "node_002",
      "toExec": "exec"
    },
    {
      "from": "node_002",
      "fromOutput": "value",
      "to": "node_003",
      "toInput": "x"
    },
    {
      "from": "node_002",
      "fromExec": "finish",
      "to": "node_003",
      "toExec": "exec"
    }
  ]
}
```

## Ventajas del Diseño

1. **Orquestador genérico:** No necesita casos especiales, trata variables como cualquier nodo
2. **Centralización:** Un solo actor evita race conditions
3. **Simplicidad:** Usuarios crean nodos sin preocuparse del store
4. **Ray-native:** Usa referencias y `.remote()` de forma natural
5. **Escalabilidad:** El store puede estar en cualquier máquina del cluster
6. **Extensibilidad:** Agregar nodos de "Debug Variables" o "List All Variables" es trivial

## Consideraciones

- **Serialización:** Solo tipos serializables por Ray (int, str, dict, etc.)
- **Performance:** Cada get/set es una llamada remota (pero Ray es rápido)
- **Tipos:** Variables son dinámicas (`Any`) - validación opcional en el store
- **Persistencia:** Se puede extender el store para guardar a disco
- **Scope:** Variables son globales al flujo, no entre flujos diferentes

## Nodos Adicionales (Futuros)

### List Variables
```python
@ray.remote
class ListVariablesNode(RayflowNode):
    """Lista todas las variables disponibles"""
    inputs = {}
    outputs = {"variables": dict}

    def process(self, **inputs):
        variables = ray.get(self.store.list_all.remote())
        return {"variables": variables}
```

### Clear Variable
```python
@ray.remote
class ClearVariableNode(RayflowNode):
    """Elimina una variable del store"""
    config = {"variable_name": "my_variable"}
    inputs = {}
    outputs = {"success": bool}

    def process(self, **inputs):
        success = ray.get(
            self.store.delete.remote(self.config["variable_name"])
        )
        return {"success": success}
```
