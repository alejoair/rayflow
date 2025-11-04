# RayFlow - Editor Visual de Flujos con Ray

## Concepto

Sistema de ejecución de flujos visuales basado en nodos, inspirado en Blueprints de Unreal Engine, utilizando Ray como backend para ejecución distribuida de actores.

## Arquitectura General

```
┌─────────────────┐         ┌─────────────────┐
│  Editor Visual  │         │   Orquestador   │
│  (React + Vite) │────────▶│   (Ray Core)    │
└─────────────────┘         └─────────────────┘
        │                            │
        │                            ▼
        ▼                    ┌───────────────┐
┌─────────────┐             │  Ray Actors   │
│ miflujo.json│             │  (Nodos)      │
└─────────────┘             └───────────────┘
        ▲                            ▲
        │                            │
        └────────────────┬───────────┘
                   ┌─────▼─────┐
                   │  nodes/   │
                   │  *.py     │
                   └───────────┘
```

### Componentes Principales

1. **Editor Visual** (Frontend - React + Vite)
   - Interface gráfica para construir flujos
   - Lee nodos disponibles desde `nodes/*.py`
   - Permite instanciar múltiples veces el mismo nodo
   - Editor de código integrado (Monaco/Ace) para modificar nodos
   - Genera/guarda `miflujo.json`

2. **Orquestador** (Backend - Ray)
   - Lee el grafo desde JSON
   - Coordina la ejecución de nodos
   - Gestiona señales de activación y flujo de datos
   - Llama `.remote()` en actores según dependencias

3. **Nodos** (Ray Actors - Python)
   - Actores Ray completamente independientes
   - Templates reutilizables definidos en `nodes/*.py`
   - Cada instancia tiene ID único en el grafo

## Librería Python: RayflowNode

### Clase Base

```python
from rayflow import RayflowNode

@ray.remote
class MyCustomNode(RayflowNode):
    inputs = {
        "x": int,
        "y": int
    }
    
    outputs = {
        "result": int,
        "message": str
    }
    
    def process(self, **inputs):
        """
        Método que el usuario DEBE implementar.
        Recibe los inputs como kwargs.
        Retorna un dict con las claves definidas en outputs.
        """
        result = inputs["x"] + inputs["y"]
        return {
            "result": result,
            "message": f"Sum is {result}"
        }
```

### Responsabilidades del Usuario

- Definir `inputs` (dict de nombre: tipo)
- Definir `outputs` (dict de nombre: tipo)
- Implementar método `process(**inputs)` que retorna dict de outputs
- **NO** gestionar `.remote()` (lo hace el orquestador)
- **NO** llamar otros nodos directamente

### Responsabilidades del Sistema

- Manejar `.remote()` automáticamente
- Pasar datos entre nodos
- Emitir señales de finalización
- Mantener IDs únicos por instancia

## Sistema de Señales y Datos

### Separación: Activación vs Datos (Inspirado en Unreal)

```
┌────────────┐ exec ┌────────────┐ exec ┌────────────┐
│   Node A   │─────▶│   Node B   │─────▶│   Node C   │
└────────────┘      └────────────┘      └────────────┘
      │                    ▲
      │ data(result: int)  │
      └────────────────────┘
```

- **Señales de Activación (exec):** Controlan CUÁNDO se ejecuta un nodo
- **Flujo de Datos:** Definen QUÉ datos se pasan entre nodos

### Comportamiento del Orquestador

1. Un nodo se ejecuta cuando:
   - Recibe la(s) señal(es) de activación requerida(s)
   - Tiene todos los datos de input disponibles

2. Al terminar, el nodo:
   - Retorna sus outputs
   - Emite señal `nodeXXXX.finish`

3. El orquestador:
   - Actualiza el estado (datos disponibles)
   - Consulta el grafo JSON para ver qué nodos dependen de esta señal
   - Llama `.remote(data)` en los siguientes nodos

### Casos Especiales

**Múltiples salidas (Branching):**
```python
# Si node1.finish activa AMBOS node2 y node3:
# → Ejecución en paralelo gracias a Ray
node1 ──┬──> node2.remote(data)
        └──> node3.remote(data)
```

**Múltiples entradas (Join):**
```python
# node3 espera a que AMBOS terminen antes de ejecutarse
node1 ──┐
        ├──> node3.remote(data_from_1_and_2)
node2 ──┘
```
El orquestador puede configurarse para esperar todas las señales necesarias.

## Variables Globales (Inspirado en Unreal Blueprints)

### Concepto

Siguiendo el patrón de Unreal Engine, las variables globales se manejan mediante **nodos GET y SET** que leen/escriben en un almacén centralizado de estado compartido.

```
┌─────────────┐ exec  ┌─────────────┐ exec  ┌─────────────┐
│ SET Variable│──────►│ Math Add    │──────►│ GET Variable│
│ name:counter│       │ x: counter  │       │ name:counter│
│ value: 0    │       │ y: 1        │       │ output: 0   │
└─────────────┘       └─────────────┘       └─────────────┘
```

### Arquitectura: GlobalVariableStore

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

### Nodo GET Variable

**Lee** el valor de una variable global:

```python
@ray.remote
class GetVariableNode(RayflowNode):
    """
    Nodo que lee una variable del store global.
    No requiere inputs de datos, solo señal exec.
    """
    
    # Configuración (desde JSON)
    config = {
        "variable_name": "my_variable"  # Qué variable leer
    }
    
    inputs = {}  # Sin inputs, solo espera exec
    
    outputs = {
        "value": Any  # Valor leído (tipo dinámico)
    }
    
    def process(self, **inputs):
        # Usa self.store inyectado en __init__
        value = ray.get(
            self.store.get.remote(self.config["variable_name"])
        )
        return {"value": value}
```

### Nodo SET Variable

**Escribe** un valor en una variable global:

```python
@ray.remote
class SetVariableNode(RayflowNode):
    """
    Nodo que escribe una variable al store global.
    Requiere el valor a escribir como input.
    """
    
    config = {
        "variable_name": "my_variable"  # Qué variable escribir
    }
    
    inputs = {
        "value": Any  # Valor a guardar
    }
    
    outputs = {
        "value": Any  # Opcional: retorna el valor para encadenar
    }
    
    def process(self, **inputs):
        # Escribe en el store
        ray.get(
            self.store.set.remote(
                self.config["variable_name"],
                inputs["value"]
            )
        )
        return {"value": inputs["value"]}
```

### Integración con el Orquestador

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

### Clase Base Actualizada

Todos los nodos heredan de `RayflowNode` que recibe el store:

```python
@ray.remote
class RayflowNode:
    def __init__(self, store_ref=None, config=None):
        """
        Constructor base.
        store_ref: Referencia al GlobalVariableStore (todos lo reciben)
        config: Configuración específica del nodo (desde JSON)
        """
        self.store = store_ref
        self.config = config or {}
    
    def process(self, **inputs):
        """Usuario implementa esto"""
        raise NotImplementedError
```

**Los nodos regulares** simplemente ignoran `self.store`:

```python
@ray.remote
class MathAddNode(RayflowNode):
    inputs = {"x": int, "y": int}
    outputs = {"result": int}
    
    def process(self, **inputs):
        # No usa self.store, solo hace su trabajo
        return {"result": inputs["x"] + inputs["y"]}
```

### Lógica de Ejecución (Sin Casos Especiales)

El orquestador usa reglas simples que aplican a TODOS los nodos:

```python
def should_execute_node(node_id):
    """
    Un nodo se ejecuta si:
    1. Tiene señal exec
    2. Tiene todos los inputs disponibles
    """
    required_inputs = get_node_definition(node_id).inputs
    available_data = get_current_state(node_id)
    
    # Si inputs = {}, entonces no requiere datos
    # GET Variable: inputs = {} → siempre listo después de exec
    # SET Variable: inputs = {"value": Any} → espera dato + exec
    return all(inp in available_data for inp in required_inputs)
```

### Ejemplo Visual Completo

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

### Formato JSON

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

### Ventajas del Diseño

1. **Orquestador genérico:** No necesita casos especiales, trata variables como cualquier nodo
2. **Centralización:** Un solo actor evita race conditions
3. **Simplicidad:** Usuarios crean nodos sin preocuparse del store
4. **Ray-native:** Usa referencias y `.remote()` de forma natural
5. **Escalabilidad:** El store puede estar en cualquier máquina del cluster
6. **Extensibilidad:** Agregar nodos de "Debug Variables" o "List All Variables" es trivial

### Consideraciones

- **Serialización:** Solo tipos serializables por Ray (int, str, dict, etc.)
- **Performance:** Cada get/set es una llamada remota (pero Ray es rápido)
- **Tipos:** Variables son dinámicas (`Any`) - validación opcional en el store
- **Persistencia:** Se puede extender el store para guardar a disco
- **Scope:** Variables son globales al flujo, no entre flujos diferentes

## Nodos START y RETURN - Entrada y Salida Obligatorios

### Diseño: Una Sola Forma Explícita

Cada flujo RayFlow tiene **exactamente UN nodo START** y **al menos UN nodo RETURN**. Esto hace que el flujo sea explícito y validable.

### Nodo START - Punto de Entrada Único

**Solo puede haber UNO por flujo**. Define dónde comienza la ejecución:

```python
@ray.remote
class StartNode(RayflowNode):
    """
    Nodo obligatorio que inicia el flujo.
    Define el esquema de entrada (inputs externos).
    """
    
    inputs = {}  # NO recibe conexiones de otros nodos
    
    # Configuración define qué espera recibir desde CLI/API
    config = {
        "api_schema": {
            "user_id": {"type": "int", "required": True},
            "action": {"type": "str", "required": True}
        }
    }
    
    outputs = {
        "user_id": int,
        "action": str
    }
    
    def process(self, **external_inputs):
        """
        external_inputs: Datos desde CLI o API request
        """
        return external_inputs
```

**Visual:**
```
┌──────────────────────┐
│ START                │  ← Único punto de inicio
│                      │
│ External inputs:     │
│  - user_id: int      │
│  - action: str       │
│                      │
│ Outputs:             │
│  - user_id ──────────┼─────▶ [siguiente nodo]
│  - action ───────────┼─────▶
└──────────┬───────────┘
           │ exec
           ▼
```

### Nodo RETURN - Punto de Salida

**Puede haber MÚLTIPLES** (para diferentes caminos de salida):

```python
@ray.remote
class ReturnNode(RayflowNode):
    """
    Nodo que marca el final del flujo.
    Retorna resultados al llamador (CLI o HTTP).
    """
    
    inputs = {
        # Configurables según lo que se quiera retornar
    }
    
    outputs = {}  # NO tiene outputs (es el final)
    
    config = {
        "name": "success",  # Identificador del return
        "status_code": 200,  # Para modo API
        "response_schema": {
            "result": {"type": "int"},
            "message": {"type": "str"}
        }
    }
    
    def process(self, **inputs):
        """
        Los inputs se retornan como resultado final
        """
        return {
            "status_code": self.config.get("status_code", 200),
            "body": inputs
        }
```

**Visual:**
```
[nodos anteriores...]
         │ exec
         ▼
┌──────────────────────┐
│ RETURN               │  ← Marca el final
│ name: "success"      │
│                      │
│ Inputs:              │
│  - result: int ◀─────┤
│  - message: str ◀────┤
│                      │
│ Returns to caller    │
└──────────────────────┘
```

### Múltiples Salidas - Diferentes Resultados

Puedes tener varios RETURN para manejar diferentes casos:

```
┌──────────────┐
│ START        │
└──────┬───────┘
       │ exec
       ▼
┌──────────────┐
│ Validate     │
└───┬──────┬───┘
    │      │
    │      └─ error ──▶ ┌─────────────────┐
    │                   │ RETURN          │
    │                   │ name: "error"   │
    │                   │ status: 400     │
    │                   └─────────────────┘
    │
    └── success ───▶ ┌─────────────────┐
                     │ RETURN          │
                     │ name: "success" │
                     │ status: 200     │
                     └─────────────────┘
```

### Validaciones del Orquestador

```python
class RayFlowOrchestrator:
    
    def __init__(self, graph_json):
        # Validar exactamente UN nodo START
        start_nodes = [n for n in graph_json["nodes"] if n["type"] == "start"]
        if len(start_nodes) != 1:
            raise ValueError("El flujo debe tener EXACTAMENTE un nodo START")
        
        self.start_node_id = start_nodes[0]["id"]
        
        # Validar al menos UN nodo RETURN
        return_nodes = [n for n in graph_json["nodes"] if n["type"] == "return"]
        if len(return_nodes) == 0:
            raise ValueError("El flujo debe tener al menos un nodo RETURN")
        
        self.return_node_ids = [n["id"] for n in return_nodes]
        
        # ... resto del setup
    
    def run(self, external_inputs=None):
        """
        Ejecuta el flujo desde START hasta algún RETURN.
        Retorna el resultado del RETURN alcanzado.
        """
        # Ejecutar desde START
        self.execute_node(self.start_node_id, external_inputs or {})
        
        # El flujo continúa hasta alcanzar un RETURN
        # Retornar el resultado
        return self.results
```

## RayFlow como API Server - Microservicios Visuales

### Concepto: Cada Flujo es un Microservicio

Cuando ejecutas un flujo con `--port`, RayFlow levanta un **servidor HTTP** que expone el flujo como una API REST auto-documentada.

```bash
# Modo API: Levanta servidor HTTP
rayflow run miflujo.json --port 8090

# Output:
# 🚀 RayFlow API Server running on http://localhost:8090
# 📋 API Schema: http://localhost:8090/schema
# 📝 Docs: http://localhost:8090/docs
```

### Arquitectura del Servidor

```
┌─────────────────────────────────────────────────┐
│         FastAPI Server (Puerto 8090)            │
│                                                 │
│  GET  /schema  → Retorna esquema del START     │
│  POST /execute → Ejecuta el flujo              │
│  GET  /docs    → Swagger UI interactivo        │
│  GET  /health  → Health check                  │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│      RayFlowOrchestrator (por request)          │
│                                                 │
│  ┌──────┐      ┌──────┐      ┌────────┐       │
│  │START │─────▶│Node1 │─────▶│ RETURN │       │
│  └──────┘      └──────┘      └────────┘       │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
          Ray Cluster (Ejecución distribuida)
```

### El Nodo START Define el Esquema de la API

La configuración del nodo START se convierte automáticamente en el esquema de la API:

```json
{
  "id": "start",
  "type": "start",
  "config": {
    "api_schema": {
      "user_id": {
        "type": "int",
        "required": true,
        "description": "ID del usuario"
      },
      "action": {
        "type": "str",
        "required": true,
        "description": "Acción a realizar"
      },
      "metadata": {
        "type": "dict",
        "required": false,
        "default": {}
      }
    }
  }
}
```

Esto genera automáticamente:
- **Modelo Pydantic** para validación
- **Esquema OpenAPI** para documentación
- **Swagger UI** interactivo

### El Nodo RETURN Define la Respuesta HTTP

```json
{
  "id": "return_success",
  "type": "return",
  "config": {
    "name": "success",
    "status_code": 200,
    "response_schema": {
      "result": {"type": "int"},
      "message": {"type": "str"}
    }
  }
}
```

### Implementación del Servidor

```python
# rayflow/server.py

from fastapi import FastAPI, HTTPException
from pydantic import create_model
import ray

class RayFlowAPIServer:
    
    def __init__(self, graph_json_path: str, port: int):
        self.port = port
        
        # Cargar grafo
        with open(graph_json_path) as f:
            self.graph = json.load(f)
        
        # Inicializar Ray
        ray.init()
        
        # Crear FastAPI app
        self.app = FastAPI(
            title=f"RayFlow API: {self.graph.get('name', 'Unnamed Flow')}",
            description="Auto-generated API from RayFlow graph"
        )
        
        self.setup_routes()
    
    def setup_routes(self):
        """Genera rutas dinámicas desde el grafo"""
        
        # Obtener nodo START y generar modelo Pydantic
        start_node = self._get_start_node()
        api_schema = start_node.get("config", {}).get("api_schema", {})
        RequestModel = self._create_pydantic_model(api_schema)
        
        @self.app.post("/execute")
        async def execute_flow(request: RequestModel):
            """
            Ejecuta el flujo RayFlow.
            Retorna cuando alcanza un nodo RETURN.
            """
            try:
                # Crear orquestador (una instancia por request)
                orchestrator = RayFlowOrchestrator(self.graph)
                
                # Ejecutar flujo (bloqueante hasta RETURN)
                result = orchestrator.run(request.dict())
                
                return result
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/schema")
        async def get_schema():
            """Retorna el esquema de entrada/salida"""
            return_nodes = self._get_return_nodes()
            return {
                "input": api_schema,
                "outputs": {
                    node["config"].get("name", node["id"]): 
                        node["config"].get("response_schema", {})
                    for node in return_nodes
                }
            }
        
        @self.app.get("/health")
        async def health():
            return {"status": "ok", "flow": self.graph.get("name")}
    
    def _create_pydantic_model(self, schema: dict):
        """Crea modelo Pydantic dinámicamente desde schema"""
        fields = {}
        for field_name, field_def in schema.items():
            field_type = self._python_type(field_def["type"])
            required = field_def.get("required", True)
            default = field_def.get("default", ... if required else None)
            fields[field_name] = (field_type, default)
        
        return create_model("DynamicModel", **fields)
    
    def run(self):
        """Inicia el servidor"""
        import uvicorn
        uvicorn.run(self.app, host="0.0.0.0", port=self.port)
```

### CLI con Modo API

```python
# rayflow/cli.py

@click.command()
@click.argument('flow_path')
@click.option('--port', type=int, help='Puerto para servidor API')
@click.option('--input', type=str, help='JSON con inputs (modo CLI)')
def run(flow_path, port, input):
    """
    Ejecutar flujo RayFlow.
    
    Modo API:  rayflow run miflujo.json --port 8090
    Modo CLI:  rayflow run miflujo.json --input '{"user_id": 123}'
    """
    
    if port:
        # Modo API Server
        server = RayFlowAPIServer(flow_path, port)
        server.run()
    
    elif input:
        # Modo CLI tradicional
        input_data = json.loads(input)
        with open(flow_path) as f:
            graph = json.load(f)
        
        orchestrator = RayFlowOrchestrator(graph)
        result = orchestrator.run(input_data)
        print(json.dumps(result, indent=2))
    
    else:
        raise click.UsageError("Use --port or --input")
```

### Ejemplo de Uso Completo

**1. Definir flujo (user_processor.json):**
```json
{
  "name": "User Processor API",
  "nodes": [
    {
      "id": "start",
      "type": "start",
      "config": {
        "api_schema": {
          "user_id": {"type": "int", "required": true},
          "action": {"type": "str", "required": true}
        }
      }
    },
    {
      "id": "validate",
      "type": "validate_user"
    },
    {
      "id": "process",
      "type": "process_action"
    },
    {
      "id": "return_success",
      "type": "return",
      "config": {
        "name": "success",
        "status_code": 200,
        "response_schema": {
          "result": {"type": "int"},
          "message": {"type": "str"}
        }
      }
    }
  ],
  "connections": [...]
}
```

**2. Levantar servidor:**
```bash
rayflow run user_processor.json --port 8090

# Output:
# 🚀 RayFlow API Server running on http://localhost:8090
# 📋 API Schema: http://localhost:8090/schema
# 📝 Docs: http://localhost:8090/docs
```

**3. Consumir la API:**
```bash
# Ver esquema
curl http://localhost:8090/schema

# Ejecutar flujo
curl -X POST http://localhost:8090/execute \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123, "action": "process"}'

# Response:
# {
#   "result": 42,
#   "message": "Processed successfully"
# }

# Swagger UI interactivo
open http://localhost:8090/docs
```

### Comunicación Entre Flujos

**Nodo HTTPRequest** para llamar otros flujos:

```python
@ray.remote
class HTTPRequestNode(RayflowNode):
    """
    Realiza peticiones HTTP a otros servicios.
    Permite comunicación entre flujos RayFlow.
    """
    
    config = {
        "url": "http://localhost:8091/execute",
        "method": "POST"
    }
    
    inputs = {
        "body": dict
    }
    
    outputs = {
        "response": dict,
        "status_code": int
    }
    
    def process(self, **inputs):
        import requests
        
        response = requests.post(
            self.config["url"],
            json=inputs["body"]
        )
        
        return {
            "response": response.json(),
            "status_code": response.status_code
        }
```

**Ejemplo: Flujos comunicándose**

```bash
# Terminal 1: Flujo validador
rayflow run validate_user.json --port 8091

# Terminal 2: Flujo principal
rayflow run main_processor.json --port 8090
```

**Flujo principal llama al validador:**
```
Flujo Principal (puerto 8090):
┌──────┐   ┌──────────────┐   ┌────────┐
│START │──▶│ HTTP Request │──▶│ RETURN │
│      │   │ url: :8091   │   │        │
└──────┘   └──────┬───────┘   └────────┘
                  │
                  │ POST {"user_id": 123}
                  ▼
         Flujo Validador (puerto 8091):
         ┌──────┐   ┌──────────┐   ┌────────┐
         │START │──▶│ Validate │──▶│ RETURN │
         └──────┘   └──────────┘   └────────┘
```

### Ventajas del Diseño API

1. **Cada flujo = Un microservicio** con API auto-documentada
2. **Paralelismo real:** Ray maneja múltiples requests simultáneos
3. **Composición:** Flujos pueden llamarse entre sí vía HTTP
4. **Auto-documentación:** Swagger UI automático
5. **Type-safe:** Pydantic valida inputs/outputs
6. **Distribuible:** Ray ejecuta en cluster
7. **Visual + Código:** Diseñas visualmente, ejecutas como API
8. **Escalable:** Múltiples instancias del mismo flujo en diferentes puertos
9. **Monitoreable:** Endpoints de health check y métricas
10. **Compatible:** APIs REST estándar, cualquier cliente puede consumirlas

### Casos de Uso

- **Webhooks:** Flujos que responden a eventos externos
- **Pipelines de datos:** ETL como microservicios
- **Automatizaciones:** Workflows complejos expuestos como APIs
- **Integraciones:** Conectar sistemas mediante flujos visuales
- **Orquestación:** Componer múltiples flujos en arquitecturas de microservicios

## Estructura del Proyecto

```
rayflow/
├── rayflow/                    # Librería Python
│   ├── __init__.py
│   ├── node.py                 # Clase RayflowNode
│   ├── orchestrator.py         # Orquestador Ray
│   ├── graph.py                # Parser del JSON
│   └── cli.py                  # CLI (create, run)
│
├── editor/                     # Frontend React + Vite
│   ├── src/
│   │   ├── components/
│   │   │   ├── NodeEditor.jsx  # Canvas de nodos
│   │   │   ├── NodeLibrary.jsx # Lista de nodos disponibles
│   │   │   └── CodeEditor.jsx  # Monaco/Ace para editar .py
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
│
├── nodes/                      # Nodos del usuario
│   ├── math_add.py
│   ├── http_request.py
│   └── ...
│
├── flows/                      # Grafos guardados
│   └── miflujo.json
│
├── setup.py
└── README.md
```

## Formato del JSON del Grafo

```json
{
  "nodes": [
    {
      "id": "node_001",
      "type": "math_add",          // Nombre del archivo en nodes/
      "position": {"x": 100, "y": 200},
      "label": "Add Numbers"
    },
    {
      "id": "node_002", 
      "type": "http_request",
      "position": {"x": 400, "y": 200},
      "label": "Send Result"
    }
  ],
  "connections": [
    {
      "from": "node_001",
      "fromOutput": "result",      // Nombre del output
      "to": "node_002",
      "toInput": "body"            // Nombre del input
    },
    {
      "from": "node_001",
      "fromExec": "finish",        // Señal de activación
      "to": "node_002",
      "toExec": "exec"
    }
  ]
}
```

## CLI

### Comandos

```bash
# Iniciar editor visual
rayflow create

# Ejecutar un flujo
rayflow run miflujo.json

# Listar nodos disponibles
rayflow list-nodes

# Crear template de nodo nuevo
rayflow new-node my_custom_node
```

## Editor Visual - Features

### Vista Principal
- **Canvas:** Área de trabajo con zoom/pan
- **Librería de Nodos:** Sidebar izquierdo con nodos de `nodes/`
- **Inspector:** Sidebar derecho con propiedades del nodo seleccionado

### Instanciación de Nodos
1. Usuario ve lista de archivos `.py` en `nodes/`
2. Drag & drop o click para instanciar en canvas
3. Cada instancia recibe ID único: `node_001`, `node_002`, etc.
4. Se pueden crear múltiples instancias del mismo template

### Edición de Nodos
- **Doble click** en nodo → Abre sidebar con editor de código
- **Editor:** Monaco o Ace mostrando el archivo `.py` completo
- **Guardar:** Modifica el archivo original en `nodes/`
- **Efecto:** Todas las instancias usan el código actualizado

### Conexiones
- **Tipos de conectores:**
  - Exec (blanco/gris): Señales de activación
  - Data (colores según tipo): int, str, dict, etc.

## Ejecución del Flujo

### Proceso

1. **Carga:**
   ```python
   rayflow run miflujo.json
   ```

2. **Orquestador:**
   - Lee JSON
   - Importa dinámicamente clases de `nodes/`
   - Crea actores Ray para cada instancia
   - Construye grafo de dependencias

3. **Ejecución:**
   - Identifica nodos de entrada (sin dependencias previas)
   - Llama `.remote()` en orden topológico
   - Gestiona paralelismo automáticamente con Ray
   - Propaga datos según conexiones

4. **Finalización:**
   - Retorna outputs finales
   - Cierra actores Ray
   - Genera logs/métricas

## Ventajas de Ray

1. **Paralelismo transparente:** Nodos independientes se ejecutan en paralelo
2. **Distribución:** Puede escalar a múltiples máquinas
3. **Aislamiento:** Cada nodo es un actor independiente
4. **Manejo de estado:** Ray gestiona el ciclo de vida de actores
5. **Fault tolerance:** Ray puede reintentar nodos fallidos

## Principios de Diseño

### Simplicidad Pytónica
- Un nodo = un archivo `.py`
- Un flujo = un archivo `.json`
- Herencia simple de `RayflowNode`
- No magia, solo convención

### Separación de Responsabilidades
- **Nodos:** Solo procesan datos
- **Orquestador:** Solo coordina ejecución
- **Editor:** Solo construye/guarda JSON

### Extensibilidad
- Agregar nodo nuevo: crear archivo en `nodes/`
- Personalizar orquestador: subclasear y override
- Integrar con sistemas externos: crear nodos de I/O

## Próximos Pasos (Implementación)

### MVP (Minimum Viable Product)

1. **Librería Core:**
   - [ ] Clase `RayflowNode` base
   - [ ] Orquestador simple (ejecución secuencial)
   - [ ] Parser de JSON

2. **CLI Básico:**
   - [ ] `rayflow run` funcional
   - [ ] Carga dinámica de nodos

3. **Editor Visual:**
   - [ ] Canvas básico con react-flow o similar
   - [ ] Instanciar nodos desde `nodes/`
   - [ ] Guardar/cargar JSON

4. **Nodos Ejemplo:**
   - [ ] Math (add, multiply, etc.)
   - [ ] String operations
   - [ ] Print/Debug

### Fase 2

- [ ] Editor de código integrado (Monaco)
- [ ] Validación de tipos en conexiones
- [ ] Ejecución en tiempo real desde editor
- [ ] Hot reload de nodos modificados

### Fase 3

- [ ] Sistema exec + data separado (como UE Blueprint)
- [ ] Nodos de control de flujo (if/else, loops)
- [ ] Debugging visual (breakpoints, inspección de datos)
- [ ] Exportar flujo a Python ejecutable standalone

## Tecnologías

- **Backend:** Python 3.10+, Ray 2.x
- **Frontend:** React 18, Vite, TypeScript
- **Editor de Nodos:** react-flow, reactflow o xyflow
- **Editor de Código:** Monaco Editor (VSCode engine)
- **Serialización:** JSON estándar
- **CLI:** Click o Typer

## Consideraciones Técnicas

### Performance
- Ray maneja el pooling de actores
- Nodos pueden cachear resultados si es stateful
- Orquestador puede optimizar orden de ejecución

### Seguridad
- Nodos personalizados ejecutan código arbitrario
- Considerar sandbox para producción
- Validar tipos antes de `.remote()`

### Debugging
- Logs estructurados con IDs de nodo
- Visualización de estado en editor
- Replay de ejecuciones desde JSON + logs

---

## Resumen Ejecutivo

**RayFlow** es un editor visual de flujos de datos basado en nodos, donde:

- Los nodos son **actores Ray independientes** definidos en archivos Python simples
- El **orquestador coordina** la ejecución basándose en señales y dependencias de datos
- El **editor visual** es solo una interfaz para construir el grafo JSON
- El sistema es **pytónico, simple y extensible**
- Escala naturalmente gracias a Ray

La arquitectura separa claramente la **definición** (archivos .py), la **composición** (JSON), y la **ejecución** (orquestador Ray).
