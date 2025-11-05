# Sistema de Nodos

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

## Clase Base Actualizada con GlobalVariableStore

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

## Lógica de Ejecución

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
