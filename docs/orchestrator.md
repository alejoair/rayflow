# Orquestador RayFlow

## Concepto

El orquestador coordina la ejecución de nodos basándose en el grafo JSON. Gestiona:
- Señales de activación (exec)
- Flujo de datos entre nodos
- Paralelismo automático con Ray
- Estado del flujo

## Validaciones del Orquestador

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

        # Crear GlobalVariableStore
        self.variable_store = GlobalVariableStore.remote()

        # Crear actores para todos los nodos
        self.setup_actors(graph_json)

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

## Proceso de Ejecución

### 1. Carga del Grafo

```python
def load_graph(json_path):
    """Lee el JSON y valida estructura"""
    with open(json_path) as f:
        graph = json.load(f)

    # Validar nodos requeridos
    validate_graph(graph)

    return graph
```

### 2. Creación de Actores

```python
def setup_actors(self, graph_json):
    """
    Importa dinámicamente clases y crea actores Ray.
    """
    self.actors = {}

    for node in graph_json["nodes"]:
        # Importar clase dinámicamente
        actor_class = self.load_node_class(node["type"])

        # Crear actor con store y config
        self.actors[node["id"]] = actor_class.remote(
            store_ref=self.variable_store,
            config=node.get("config", {})
        )

def load_node_class(self, node_type):
    """
    Carga la clase del nodo desde nodes/
    Ejemplo: "math_add" → nodes/math/add.py → MathAddNode
    """
    # Convertir node_type a ruta de archivo
    # "math_add" → "nodes/math/add.py"
    module_path = self.type_to_module_path(node_type)

    # Importar dinámicamente
    spec = importlib.util.spec_from_file_location("node_module", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Obtener clase (convención: primera clase que hereda de RayflowNode)
    return self.find_node_class(module)
```

### 3. Construcción del Grafo de Dependencias

```python
def build_dependency_graph(self, connections):
    """
    Construye grafo dirigido de dependencias.
    """
    self.dependencies = defaultdict(list)
    self.data_flow = defaultdict(dict)

    for conn in connections:
        if "fromExec" in conn:
            # Conexión de activación
            self.dependencies[conn["to"]].append(conn["from"])

        if "fromOutput" in conn:
            # Conexión de datos
            self.data_flow[conn["to"]][conn["toInput"]] = {
                "from": conn["from"],
                "output": conn["fromOutput"]
            }
```

### 4. Ejecución Ordenada

```python
def execute_flow(self):
    """
    Ejecuta nodos en orden topológico respetando dependencias.
    """
    # Identificar nodos listos (sin dependencias pendientes)
    ready_nodes = self.get_ready_nodes()

    while ready_nodes:
        # Ejecutar nodos en paralelo (Ray lo maneja)
        futures = []
        for node_id in ready_nodes:
            # Recolectar inputs
            inputs = self.gather_node_inputs(node_id)

            # Llamar .remote() (no bloqueante)
            future = self.actors[node_id].process.remote(**inputs)
            futures.append((node_id, future))

        # Esperar resultados
        for node_id, future in futures:
            result = ray.get(future)
            self.store_results(node_id, result)

            # Actualizar estado
            self.mark_completed(node_id)

        # Encontrar siguientes nodos listos
        ready_nodes = self.get_ready_nodes()

    return self.final_results
```

## Reglas de Ejecución

### Cuándo se Ejecuta un Nodo

Un nodo se ejecuta cuando:
1. **Tiene señal exec** (todos sus nodos predecesores terminaron)
2. **Tiene todos los inputs disponibles** (datos de otros nodos)

```python
def should_execute_node(self, node_id):
    """
    Verifica si un nodo está listo para ejecutarse.
    """
    # 1. Verificar señales exec
    for predecessor in self.dependencies[node_id]:
        if not self.is_completed(predecessor):
            return False

    # 2. Verificar inputs de datos
    required_inputs = self.get_node_definition(node_id).inputs
    available_data = self.get_available_data(node_id)

    return all(inp in available_data for inp in required_inputs)
```

## Casos Especiales

### Branching (Múltiples Salidas)

```python
# Si node1 activa AMBOS node2 y node3:
# Ray ejecuta en paralelo automáticamente

node1.finish → [node2, node3]

# Ambos se ejecutan simultáneamente
futures = [
    actors["node2"].process.remote(data),
    actors["node3"].process.remote(data)
]
```

### Join (Múltiples Entradas)

```python
# node3 espera a que AMBOS terminen

node1 ─┐
       ├─> node3
node2 ─┘

# El orquestador espera ambos resultados antes de ejecutar node3
if all(pred in completed for pred in ["node1", "node2"]):
    execute_node("node3")
```

### Loops (Futuros)

Para implementar loops, necesitamos:
- Nodos especiales de control (`ForEach`, `While`)
- Detección de ciclos en el grafo
- Límite de iteraciones

## Manejo de Errores

```python
def execute_node_safe(self, node_id, inputs):
    """
    Ejecuta nodo con manejo de errores.
    """
    try:
        actor = self.actors[node_id]
        result = ray.get(actor.process.remote(**inputs))
        return {"success": True, "result": result}

    except Exception as e:
        # Log error
        logger.error(f"Node {node_id} failed: {str(e)}")

        # Opciones:
        # 1. Abortar flujo
        # 2. Reintentar
        # 3. Saltar a nodo de error
        return {"success": False, "error": str(e)}
```

## Optimizaciones

### Paralelismo Máximo

Ray ejecuta automáticamente nodos independientes en paralelo:

```python
# Estos se ejecutan simultáneamente
┌────┐     ┌────┐
│ N1 │─────│ N3 │
└────┘  ┌─►└────┘
        │
┌────┐  │  ┌────┐
│ N2 │──┴─►│ N4 │
└────┘     └────┘

# N1 y N2 en paralelo
# Cuando ambos terminen, N3 y N4 en paralelo
```

### Caching de Resultados

```python
def execute_node(self, node_id, inputs):
    """Cache resultados para evitar recálculo"""

    # Verificar cache
    cache_key = (node_id, frozenset(inputs.items()))
    if cache_key in self.result_cache:
        return self.result_cache[cache_key]

    # Ejecutar
    result = ray.get(self.actors[node_id].process.remote(**inputs))

    # Guardar en cache
    self.result_cache[cache_key] = result
    return result
```

## Modo Debug

```python
class DebugOrchestrator(RayFlowOrchestrator):
    """
    Orquestador con capacidades de debugging.
    """

    def execute_node(self, node_id, inputs):
        print(f"[DEBUG] Executing {node_id}")
        print(f"[DEBUG] Inputs: {inputs}")

        result = super().execute_node(node_id, inputs)

        print(f"[DEBUG] Result: {result}")
        print(f"[DEBUG] Time: {time.time() - start}")

        return result
```

## Métricas y Monitoreo

```python
class MonitoredOrchestrator(RayFlowOrchestrator):
    """
    Orquestador con métricas de ejecución.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics = {
            "node_times": {},
            "total_time": 0,
            "nodes_executed": 0,
            "errors": []
        }

    def execute_node(self, node_id, inputs):
        start = time.time()

        result = super().execute_node(node_id, inputs)

        elapsed = time.time() - start
        self.metrics["node_times"][node_id] = elapsed
        self.metrics["nodes_executed"] += 1

        return result
```
