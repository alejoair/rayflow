# RayFlow como API Server

## Concepto: Cada Flujo es un Microservicio

Cuando ejecutas un flujo con `--port`, RayFlow levanta un **servidor HTTP** que expone el flujo como una API REST auto-documentada.

```bash
# Modo API: Levanta servidor HTTP
rayflow run miflujo.json --port 8090

# Output:
# 🚀 RayFlow API Server running on http://localhost:8090
# 📋 API Schema: http://localhost:8090/schema
# 📝 Docs: http://localhost:8090/docs
```

## Arquitectura del Servidor

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

## El Nodo START Define el Esquema de la API

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

## El Nodo RETURN Define la Respuesta HTTP

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

## Implementación del Servidor

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

## Ejemplo de Uso Completo

### 1. Definir flujo (user_processor.json):
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

### 2. Levantar servidor:
```bash
rayflow run user_processor.json --port 8090

# Output:
# 🚀 RayFlow API Server running on http://localhost:8090
# 📋 API Schema: http://localhost:8090/schema
# 📝 Docs: http://localhost:8090/docs
```

### 3. Consumir la API:
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

## Comunicación Entre Flujos

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

## Ventajas del Diseño API

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

## Casos de Uso

- **Webhooks:** Flujos que responden a eventos externos
- **Pipelines de datos:** ETL como microservicios
- **Automatizaciones:** Workflows complejos expuestos como APIs
- **Integraciones:** Conectar sistemas mediante flujos visuales
- **Orquestación:** Componer múltiples flujos en arquitecturas de microservicios
