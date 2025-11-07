# RayFlow Orchestrator Architecture

## Overview

Este documento describe la arquitectura modular del orquestador de RayFlow, explicando cómo los diferentes módulos se conectan, interactúan y coordinan para ejecutar workflows distribuidos.

## Visión General

El orquestador de RayFlow es el **motor de ejecución** que toma un workflow (representado como JSON) y lo ejecuta de manera distribuida usando Ray. El sistema está diseñado con una arquitectura modular donde cada componente tiene una responsabilidad única y bien definida.

```
┌─────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR                            │
│                    (Coordinador Principal)                  │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Validator │  │  Graph   │  │  Node    │  │Variable  │  │
│  │          │  │ Builder  │  │ Loader   │  │  Store   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Actor   │  │Execution │  │   Data   │  │   Node   │  │
│  │ Manager  │  │ Planner  │  │ Gatherer │  │ Executor │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
│  ┌──────────┐  ┌──────────┐                                │
│  │  State   │  │  Error   │                                │
│  │ Tracker  │  │ Handler  │                                │
│  └──────────┘  └──────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

---

## Módulos del Sistema

### 1. FlowValidator (Validador de Flujo)

**Propósito**: Verificar que el workflow JSON sea válido antes de intentar ejecutarlo.

**Responsabilidad**:
- Validar estructura del JSON (campos obligatorios presentes)
- Verificar exactamente UN nodo START
- Verificar al menos UN nodo RETURN
- Validar que todos los IDs de nodos sean únicos
- Verificar que todas las conexiones referencien nodos existentes
- Validar compatibilidad de tipos en las conexiones de datos
- Detectar ciclos en el grafo (opcional)

**Cuándo se usa**: PRIMERO, antes de cualquier otra operación.

**Input**: Flow JSON completo
**Output**: Resultado de validación (válido/inválido + lista de errores)

**Razón de ser**: Fallar rápido y temprano. Si el JSON es inválido, no tiene sentido continuar con la inicialización.

---

### 2. GraphBuilder (Constructor de Grafo)

**Propósito**: Transformar el JSON del workflow en estructuras de datos optimizadas para la ejecución.

**Responsabilidad**:
- Crear un mapa de todos los nodos (ID → información del nodo)
- Construir el grafo de dependencias (qué nodos dependen de cuáles)
- Construir el mapa de flujo de datos (de dónde vienen los datos de cada input)
- Ordenar nodos topológicamente (orden de ejecución potencial)
- Identificar el nodo START
- Identificar todos los nodos RETURN

**Cuándo se usa**: SEGUNDO, inmediatamente después de la validación.

**Input**: Flow JSON validado
**Output**: FlowGraph (estructura de datos completa y optimizada)

**Estructuras que produce**:
```
FlowGraph {
    nodes: Map<ID, NodeInfo>           // Información de cada nodo
    dependencies: Map<ID, [IDs]>       // ID → lista de predecesores
    data_flow: Map<ID, Map<input, source>>  // Ruteo de datos
    start_node_id: ID                  // ID del START
    return_node_ids: [IDs]             // IDs de todos los RETURN
    topological_order: [IDs]           // Orden sugerido de ejecución
}
```

**Razón de ser**: El JSON es legible para humanos, pero no eficiente para ejecución. Este módulo crea las estructuras de datos que el resto del sistema necesita.

---

### 3. NodeLoader (Cargador de Nodos)

**Propósito**: Cargar dinámicamente las clases Python de los nodos.

**Responsabilidad**:
- Convertir el "type" del nodo a una ruta de archivo ("math_add" → "rayflow/nodes/math/add.py")
- Importar el módulo Python dinámicamente
- Encontrar la clase que hereda de RayflowNode
- Cachear las clases cargadas para no reimportarlas

**Cuándo se usa**: Durante la fase de inicialización, cuando se necesita instanciar actors.

**Input**: Tipo de nodo (string, ej: "math_add")
**Output**: Clase Python (Type[RayflowNode])

**Razón de ser**: Los nodos pueden ser built-in o definidos por el usuario. Este módulo maneja la carga dinámica de ambos tipos.

---

### 4. VariableStoreManager (Gestor de Variables)

**Propósito**: Crear y gestionar el GlobalVariableStore compartido.

**Responsabilidad**:
- Crear una instancia de GlobalVariableStore como Ray actor
- Inicializar variables con valores por defecto (si existen)
- Proporcionar la referencia del store a todos los nodos
- Limpiar el store al finalizar la ejecución

**Cuándo se usa**: TEMPRANO en la inicialización, antes de crear los actors de los nodos.

**Input**: Variables iniciales (opcional)
**Output**: Referencia de Ray actor al GlobalVariableStore

**Razón de ser**: Las variables deben ser compartidas entre TODOS los nodos. Ray actors proporcionan un mecanismo thread-safe para esto.

**Importante**: Solo se crea UNA instancia del store por ejecución de workflow. Esta referencia se pasa a TODOS los nodos al crearlos.

---

### 5. ActorManager (Gestor de Actores)

**Propósito**: Instanciar y gestionar los Ray actors de todos los nodos del workflow.

**Responsabilidad**:
- Recibir la referencia del GlobalVariableStore
- Para cada nodo en el grafo:
  - Obtener la clase del nodo (vía NodeLoader)
  - Instanciar el nodo como Ray actor
  - Pasar el store_ref y config al constructor
  - Almacenar la referencia del actor
- Proporcionar acceso a los actors por su ID
- Limpiar todos los actors al finalizar

**Cuándo se usa**: Después de crear el GlobalVariableStore y tener el grafo construido.

**Input**:
- FlowGraph (para saber qué nodos crear)
- GlobalVariableStore reference (para pasarla a los nodos)
- NodeLoader (para obtener las clases)

**Output**: Map de ID → Ray actor reference

**Razón de ser**: Los nodos son Ray actors (procesos distribuidos). Este módulo centraliza su creación y gestión.

**Interacción con otros módulos**:
- Usa **NodeLoader** para obtener las clases
- Recibe **VariableStoreManager.store_ref** para pasarla a todos los nodos
- Usa información del **GraphBuilder** para saber qué nodos crear

---

### 6. ExecutionPlanner (Planificador de Ejecución)

**Propósito**: Determinar qué nodos pueden ejecutarse en cada momento.

**Responsabilidad**:
- Mantener el estado de qué nodos están completados
- Identificar qué nodos están listos para ejecutar (todas sus dependencias satisfechas)
- Proporcionar el nodo inicial (START)
- Detectar cuándo el workflow ha terminado (RETURN ejecutado)

**Cuándo se usa**: Durante TODO el loop de ejecución, en cada iteración.

**Input**:
- FlowGraph (grafo de dependencias)
- Estado actual (qué nodos han completado)

**Output**: Lista de IDs de nodos listos para ejecutar

**Lógica**:
```
Para cada nodo en el grafo:
    Si el nodo NO está completado
    Y TODAS sus dependencias (exec) están completadas
    Y NO está actualmente en ejecución
    → El nodo está LISTO
```

**Razón de ser**: La ejecución debe respetar las dependencias (topología del grafo). Este módulo es el que decide QUÉ ejecutar y CUÁNDO.

---

### 7. DataGatherer (Recolector de Datos)

**Propósito**: Recolectar los inputs necesarios para ejecutar cada nodo.

**Responsabilidad**:
- Almacenar los resultados de todos los nodos ejecutados
- Cuando un nodo va a ejecutar, recolectar sus inputs desde:
  - Resultados de nodos predecesores (para inputs de datos)
  - Inputs externos (para el START node)
- Proporcionar los inputs en el formato correcto (dict)

**Cuándo se usa**: Justo ANTES de ejecutar cada nodo.

**Input**:
- ID del nodo que va a ejecutar
- FlowGraph (para saber de dónde vienen los datos)
- Resultados almacenados de nodos anteriores

**Output**: Dict de inputs listos para pasar a node.process()

**Lógica**:
```
Para cada input del nodo:
    Buscar en data_flow de dónde viene este input
    Si viene de otro nodo:
        Obtener el resultado almacenado de ese nodo
        Extraer el output específico
        Agregarlo al dict de inputs
    Si no tiene fuente (input sin conexión):
        Puede usar valor por defecto o ser omitido
```

**Razón de ser**: Los nodos necesitan datos de sus predecesores. Este módulo maneja el ruteo de datos entre nodos.

**Interacción clave**: Trabaja muy cerca con **ExecutionPlanner**. ExecutionPlanner dice QUÉ ejecutar, DataGatherer dice CON QUÉ DATOS.

---

### 8. NodeExecutor (Ejecutor de Nodos)

**Propósito**: Ejecutar nodos individuales y gestionar sus resultados.

**Responsabilidad**:
- Tomar un ID de nodo + sus inputs
- Obtener el actor correspondiente (vía ActorManager)
- Llamar a actor.process() con los inputs
- Esperar el resultado (ray.get() para obtener el valor)
- Manejar errores de ejecución
- Retornar el resultado o error

**Puede ejecutar**:
- UN nodo individual (síncrono)
- MÚLTIPLES nodos en paralelo (asíncrono)

**Cuándo se usa**: En cada iteración del loop de ejecución.

**Input**:
- ID del nodo
- Dict de inputs (del DataGatherer)

**Output**: Resultado de la ejecución (éxito + datos, o error)

**Razón de ser**: Ray maneja la distribución automáticamente. Este módulo solo necesita llamar .remote() y esperar resultados.

**Ejecución en paralelo**:
```
Si hay 3 nodos listos [A, B, C]:
    1. Llamar actor_A.process.remote(inputs_A) → obtener future_A
    2. Llamar actor_B.process.remote(inputs_B) → obtener future_B
    3. Llamar actor_C.process.remote(inputs_C) → obtener future_C
    4. ray.get([future_A, future_B, future_C]) → esperar TODOS

Ray ejecuta A, B, C en PARALELO automáticamente
```

---

### 9. StateTracker (Rastreador de Estado)

**Propósito**: Mantener el estado completo de la ejecución del workflow.

**Responsabilidad**:
- Rastrear el estado de cada nodo (pending, in_progress, completed, failed)
- Registrar tiempos de ejecución de cada nodo
- Registrar errores que ocurran
- Mantener estadísticas globales (tiempo total, nodos ejecutados, etc.)
- Proporcionar información para debugging y monitoreo

**Cuándo se usa**: Durante TODO el ciclo de ejecución, cada vez que cambia el estado.

**Input**: Eventos del orquestador (nodo empezó, nodo terminó, nodo falló, etc.)

**Output**: Estado actual del workflow + estadísticas

**Razón de ser**: Para debugging, monitoreo y reportes. También útil para implementar features futuras como visualización en vivo.

---

### 10. ErrorHandler (Manejador de Errores)

**Propósito**: Decidir qué hacer cuando un nodo falla.

**Responsabilidad**:
- Capturar errores de ejecución
- Aplicar la estrategia de error configurada (abort, retry, continue, skip)
- Loggear errores con contexto
- Decidir si el workflow debe terminar o continuar

**Estrategias soportadas**:
- **ABORT**: Detener todo al primer error
- **RETRY**: Reintentar el nodo (con backoff exponencial)
- **CONTINUE**: Continuar con otros nodos, marcar este como fallido
- **SKIP**: Ignorar el nodo y continuar el flujo

**Cuándo se usa**: Cuando NodeExecutor reporta un error.

**Input**:
- ID del nodo que falló
- Exception capturada
- Contexto (cuántos intentos, qué estaba haciendo)

**Output**: Decisión de qué hacer (abort, retry, continue)

**Razón de ser**: Los workflows pueden fallar. Este módulo hace el sistema resiliente.

---

## Flujo de Ejecución Completo

### FASE 1: INICIALIZACIÓN

Esta fase prepara todo lo necesario antes de ejecutar el primer nodo.

```
1. VALIDACIÓN
   ┌──────────────────┐
   │  FlowValidator   │ ← Flow JSON
   └────────┬─────────┘
            │
            ↓ ¿Válido?
            │
    ┌───────┴────────┐
    │ NO             │ SI
    │                │
    ↓                ↓
   ERROR          Continuar


2. CONSTRUCCIÓN DEL GRAFO
   ┌──────────────────┐
   │   GraphBuilder   │ ← Flow JSON
   └────────┬─────────┘
            │
            ↓
      FlowGraph
      (estructura optimizada)


3. CREACIÓN DE VARIABLE STORE
   ┌───────────────────────┐
   │ VariableStoreManager  │ ← Variables iniciales
   └────────┬──────────────┘
            │
            ↓
   GlobalVariableStore (Ray Actor)
   (una instancia compartida)


4. CARGA DE CLASES DE NODOS
   Para cada nodo en FlowGraph:
   ┌──────────────────┐
   │   NodeLoader     │ ← node.type ("math_add")
   └────────┬─────────┘
            │
            ↓
      NodeClass (Python Class)


5. INSTANCIACIÓN DE ACTORS
   ┌──────────────────┐
   │  ActorManager    │ ← {NodeClass, config, store_ref}
   └────────┬─────────┘
            │
            ↓
   Para cada nodo, crear:
   actor = NodeClass.remote(store_ref, config)

   Resultado: Map<node_id, actor_ref>


6. INICIALIZACIÓN DE AUXILIARES
   ┌──────────────────┐     ┌──────────────────┐
   │ExecutionPlanner  │     │  DataGatherer    │
   └──────────────────┘     └──────────────────┘

   ┌──────────────────┐     ┌──────────────────┐
   │  StateTracker    │     │  ErrorHandler    │
   └──────────────────┘     └──────────────────┘

   Todos inicializados y listos
```

**Estado al final de esta fase**:
- ✓ Workflow validado
- ✓ Grafo construido
- ✓ GlobalVariableStore creado
- ✓ Todos los node actors instanciados
- ✓ Todos los módulos auxiliares listos

---

### FASE 2: EJECUCIÓN

Esta fase es un LOOP que se repite hasta que el workflow termina.

```
┌─────────────────────────────────────────────────┐
│         LOOP DE EJECUCIÓN                       │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │ 1. IDENTIFICAR NODOS LISTOS              │  │
│  │                                          │  │
│  │    ExecutionPlanner.get_ready_nodes()   │  │
│  │         ↓                                │  │
│  │    [node_A, node_B, node_C]             │  │
│  │                                          │  │
│  │    (Estos nodos tienen todas sus        │  │
│  │     dependencias satisfechas)           │  │
│  └──────────────────────────────────────────┘  │
│              ↓                                  │
│  ┌──────────────────────────────────────────┐  │
│  │ 2. RECOLECTAR INPUTS                     │  │
│  │                                          │  │
│  │    Para cada nodo listo:                │  │
│  │    inputs = DataGatherer.gather(node_id)│  │
│  │                                          │  │
│  │    (Obtiene datos de nodos anteriores)  │  │
│  └──────────────────────────────────────────┘  │
│              ↓                                  │
│  ┌──────────────────────────────────────────┐  │
│  │ 3. EJECUTAR EN PARALELO                  │  │
│  │                                          │  │
│  │    futures = []                         │  │
│  │    Para cada nodo:                      │  │
│  │      future = NodeExecutor.execute(     │  │
│  │                 node_id, inputs)        │  │
│  │      futures.append(future)             │  │
│  │                                          │  │
│  │    Ray ejecuta TODOS en paralelo        │  │
│  └──────────────────────────────────────────┘  │
│              ↓                                  │
│  ┌──────────────────────────────────────────┐  │
│  │ 4. ESPERAR RESULTADOS                    │  │
│  │                                          │  │
│  │    results = ray.get(futures)           │  │
│  │                                          │  │
│  │    (Bloquea hasta que TODOS completen)  │  │
│  └──────────────────────────────────────────┘  │
│              ↓                                  │
│  ┌──────────────────────────────────────────┐  │
│  │ 5. PROCESAR RESULTADOS                   │  │
│  │                                          │  │
│  │    Para cada resultado:                 │  │
│  │      Si exitoso:                        │  │
│  │        DataGatherer.store_result()      │  │
│  │        StateTracker.mark_completed()    │  │
│  │      Si error:                          │  │
│  │        ErrorHandler.handle_error()      │  │
│  │        ¿Abortar? ¿Reintentar?           │  │
│  └──────────────────────────────────────────┘  │
│              ↓                                  │
│  ┌──────────────────────────────────────────┐  │
│  │ 6. VERIFICAR TERMINACIÓN                 │  │
│  │                                          │  │
│  │    ¿Algún RETURN node ejecutó?          │  │
│  │         ↓                                │  │
│  │    SI → TERMINAR                        │  │
│  │    NO → Volver al paso 1                │  │
│  └──────────────────────────────────────────┘  │
│              ↓                                  │
│         Repetir loop                           │
└─────────────────────────────────────────────────┘
```

**Importante**: El loop continúa hasta que:
- Un nodo RETURN se ejecuta (terminación exitosa), O
- Ocurre un error fatal (terminación por error), O
- No quedan más nodos por ejecutar (estado inválido, posible deadlock)

---

### FASE 3: FINALIZACIÓN

```
1. EXTRAER RESULTADO FINAL
   ┌──────────────────────────────────┐
   │  DataGatherer                    │
   │    .get_node_result(return_node) │
   └──────────┬───────────────────────┘
              │
              ↓
         Resultado del RETURN node


2. RECOLECTAR ESTADÍSTICAS
   ┌──────────────────────────────────┐
   │  StateTracker                    │
   │    .get_statistics()             │
   └──────────┬───────────────────────┘
              │
              ↓
         Métricas de ejecución


3. LIMPIEZA
   ┌──────────────────────────────────┐
   │  ActorManager.shutdown_all()     │
   │  (Matar todos los Ray actors)    │
   └──────────────────────────────────┘

   ┌──────────────────────────────────┐
   │  VariableStoreManager.shutdown() │
   │  (Matar GlobalVariableStore)     │
   └──────────────────────────────────┘


4. RETORNAR RESULTADO
   {
     success: true/false,
     result: {...},
     statistics: {...},
     errors: [...]
   }
```

---

## Interacciones Clave Entre Módulos

### Interacción 1: GraphBuilder → ExecutionPlanner

```
GraphBuilder construye:
    dependencies = {
        "node_003": ["node_001", "node_002"]
    }

ExecutionPlanner usa esto para:
    def get_ready_nodes():
        Para cada nodo:
            Si TODAS las entradas en dependencies[node]
               están en completed_set
            → node está listo
```

**Flujo de datos**: FlowGraph.dependencies → ExecutionPlanner

---

### Interacción 2: GraphBuilder → DataGatherer

```
GraphBuilder construye:
    data_flow = {
        "node_003": {
            "input_x": {"from": "node_001", "output": "result"}
        }
    }

DataGatherer usa esto para:
    def gather_inputs(node_003):
        input_x = results["node_001"]["result"]
        return {"input_x": input_x}
```

**Flujo de datos**: FlowGraph.data_flow → DataGatherer

---

### Interacción 3: NodeLoader → ActorManager

```
Para cada nodo:
    1. ActorManager pide: "Dame la clase para 'math_add'"
    2. NodeLoader responde: AddNode (Python Class)
    3. ActorManager instancia: actor = AddNode.remote(...)
```

**Flujo**: ActorManager solicita → NodeLoader carga → ActorManager instancia

---

### Interacción 4: ActorManager ↔ NodeExecutor

```
NodeExecutor necesita ejecutar un nodo:
    1. Pide a ActorManager: "Dame el actor para 'node_003'"
    2. ActorManager responde: actor_ref
    3. NodeExecutor llama: result = actor_ref.process.remote(**inputs)
```

**Flujo**: NodeExecutor solicita actor → ActorManager provee → NodeExecutor ejecuta

---

### Interacción 5: VariableStoreManager → ActorManager → Nodos

```
1. VariableStoreManager crea GlobalVariableStore
   store_ref = GlobalVariableStore.remote()

2. ActorManager recibe store_ref

3. Para cada nodo que crea:
   actor = NodeClass.remote(
       store_ref=store_ref,  ← Pasa la referencia
       config=...
   )

4. Los nodos pueden ahora:
   value = ray.get(self.store_ref.get.remote("variable_name"))
```

**Flujo**: VariableStoreManager crea → ActorManager distribuye → Nodos usan

---

### Interacción 6: ExecutionPlanner + DataGatherer + NodeExecutor (El Loop)

```
Loop de ejecución:

1. ExecutionPlanner:
   ready = get_ready_nodes()
   → ["node_A", "node_B"]

2. Para cada nodo listo:
   DataGatherer:
   inputs_A = gather_inputs("node_A")
   inputs_B = gather_inputs("node_B")

3. NodeExecutor:
   future_A = execute_async("node_A", inputs_A)
   future_B = execute_async("node_B", inputs_B)

   [result_A, result_B] = wait_all([future_A, future_B])

4. Almacenar resultados:
   DataGatherer.store_result("node_A", result_A)
   DataGatherer.store_result("node_B", result_B)

5. Actualizar estado:
   ExecutionPlanner.mark_completed("node_A")
   ExecutionPlanner.mark_completed("node_B")

6. Volver al paso 1
```

**Este es el corazón del sistema**: Estos 3 módulos trabajan en sincronía en cada iteración del loop.

---

## Flujo de Datos a Través del Sistema

```
                         INICIALIZACIÓN
                              │
                              ↓
┌────────────────────────────────────────────────────────┐
│                      Flow JSON                          │
└───────────┬────────────────────────────────────────────┘
            │
            ↓
┌───────────────────────┐
│   FlowValidator       │ → ValidationResult
└───────────┬───────────┘
            │
            ↓
┌───────────────────────┐
│   GraphBuilder        │ → FlowGraph
└───────────┬───────────┘
            │
            ├───────────────┬────────────────┐
            │               │                │
            ↓               ↓                ↓
┌─────────────────┐ ┌─────────────┐ ┌──────────────┐
│ExecutionPlanner │ │DataGatherer │ │StateTracker  │
└─────────────────┘ └─────────────┘ └──────────────┘
    (dependencies)     (data_flow)      (nodes info)


                         EJECUCIÓN
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
        ↓                                           ↓
┌──────────────────┐                    ┌──────────────────┐
│VariableStore     │───────────────────→│  ActorManager    │
│Manager           │    store_ref       │                  │
└──────────────────┘                    └────────┬─────────┘
                                                 │
                                                 ↓
                                        Todos los Node Actors
                                        (con store_ref inyectado)
                                                 │
                    ┌────────────────────────────┤
                    │                            │
                    ↓                            ↓
        ┌──────────────────┐        ┌──────────────────┐
        │ NodeExecutor     │◄───────│ ExecutionPlanner │
        │                  │        │  (¿qué ejecutar?)│
        └────────┬─────────┘        └──────────────────┘
                 │                            ↑
                 ↓                            │
        ┌──────────────────┐                 │
        │ DataGatherer     │─────────────────┘
        │  (inputs)        │    (resultados)
        └──────────────────┘


                         RESULTADO
                              │
                              ↓
        ┌──────────────────────────────────┐
        │  DataGatherer.get_final_result() │
        └──────────────────┬───────────────┘
                           │
                           ↓
                    ExecutionResult
                    (retornado al caller)
```

---

## Orden de Creación e Inicialización

**Orden estricto que debe seguirse**:

```
1. FlowValidator
   - No depende de nada
   - Puede crearse primero

2. GraphBuilder
   - Solo necesita el JSON
   - Debe ejecutarse DESPUÉS de validar

3. VariableStoreManager
   - No depende de otros módulos
   - Debe crearse ANTES de ActorManager

4. NodeLoader
   - Independiente
   - Necesario ANTES de ActorManager

5. ActorManager
   - DEPENDE de: VariableStoreManager (store_ref)
   - DEPENDE de: NodeLoader (para obtener clases)
   - DEPENDE de: GraphBuilder (para saber qué nodos crear)

6. ExecutionPlanner
   - DEPENDE de: GraphBuilder (dependencies)
   - Puede crearse en paralelo con DataGatherer

7. DataGatherer
   - DEPENDE de: GraphBuilder (data_flow)
   - Puede crearse en paralelo con ExecutionPlanner

8. StateTracker
   - DEPENDE de: GraphBuilder (lista de nodos)
   - Independiente de otros módulos

9. ErrorHandler
   - Independiente
   - Puede crearse en cualquier momento

10. NodeExecutor
    - DEPENDE de: ActorManager (para obtener actors)
    - Debe crearse DESPUÉS de ActorManager
```

**Resumen de dependencias**:
```
FlowValidator (independiente)
    ↓
GraphBuilder (depende de validación)
    ↓
    ├→ ExecutionPlanner (usa dependencies)
    ├→ DataGatherer (usa data_flow)
    └→ StateTracker (usa nodes info)

VariableStoreManager (independiente)
    ↓
    ├→ ActorManager (necesita store_ref)

NodeLoader (independiente)
    ↓
    └→ ActorManager (necesita clases)

ActorManager (depende de store + loader + graph)
    ↓
    └→ NodeExecutor (necesita actors)

ErrorHandler (independiente)
```

---

## Decisiones de Diseño Clave

### 1. ¿Por qué separar ExecutionPlanner y DataGatherer?

**Razón**: Separación de responsabilidades.

- **ExecutionPlanner**: Se preocupa del ORDEN (topología, dependencias exec)
- **DataGatherer**: Se preocupa de los DATOS (valores, ruteo de datos)

Son dos problemas diferentes:
- "¿Qué nodos puedo ejecutar ahora?" (Planner)
- "¿Con qué datos ejecuto este nodo?" (Gatherer)

**Beneficio**: Cada módulo es más simple y testeable.

---

### 2. ¿Por qué ActorManager es separado del NodeExecutor?

**Razón**: Ciclo de vida diferente.

- **ActorManager**: Se crea UNA VEZ al inicio, dura toda la ejecución
- **NodeExecutor**: Se usa MUCHAS VECES durante el loop

**Beneficio**: Reutilización. Los actors se crean una vez, se usan muchas veces.

---

### 3. ¿Por qué StateTracker como módulo separado?

**Razón**: No es esencial para la ejecución básica.

- El workflow puede ejecutarse SIN StateTracker
- Es principalmente para debugging y métricas

**Beneficio**: Feature opcional. En producción con alta performance, podría deshabilitarse.

---

### 4. ¿Por qué GraphBuilder crea múltiples estructuras?

**Razón**: Optimización de acceso.

- Durante ejecución, se necesita:
  - Acceso rápido a nodos por ID → Map
  - Consulta rápida de dependencias → Map
  - Ruteo eficiente de datos → Map anidado

**Beneficio**: O(1) lookups en lugar de recorrer el JSON cada vez.

---

### 5. ¿Por qué GlobalVariableStore es un Ray actor separado?

**Razón**: Concurrencia segura.

- Múltiples nodos pueden acceder variables simultáneamente
- Ray actors son thread-safe por diseño
- Evita race conditions sin locks manuales

**Beneficio**: Simplicidad + corrección concurrente.

---

## Casos Especiales

### Caso 1: Nodo sin inputs de datos

```
Ejemplo: GET Variable node

GraphBuilder.data_flow["get_var_node"] = {}  (vacío)

DataGatherer.gather_inputs("get_var_node"):
    → return {}  (dict vacío)

NodeExecutor ejecuta con inputs vacíos:
    actor.process.remote()  (sin kwargs)
```

**Resultado**: El nodo ejecuta sin datos de entrada, solo con su configuración interna.

---

### Caso 2: Múltiples RETURN nodes

```
Flow:
    START → IF(condition)
              ├─ true  → RETURN_SUCCESS
              └─ false → RETURN_ERROR

Ejecución:
    1. START ejecuta
    2. IF ejecuta, evalúa condición
    3. Basado en resultado, solo UNO de los RETURN ejecuta
    4. ExecutionPlanner detecta que UN RETURN completó
    5. Workflow termina, otros RETURN no ejecutan
```

**Resultado**: Solo el RETURN alcanzado retorna su resultado.

---

### Caso 3: Branching paralelo

```
Flow:
         ┌→ MATH_1
    START┤
         └→ MATH_2

Ejecución:
    1. START completa
    2. ExecutionPlanner.get_ready_nodes() → ["MATH_1", "MATH_2"]
    3. NodeExecutor ejecuta AMBOS en paralelo:
       future_1 = actor_1.process.remote(...)
       future_2 = actor_2.process.remote(...)
       ray.get([future_1, future_2])
```

**Resultado**: MATH_1 y MATH_2 ejecutan simultáneamente (si hay recursos).

---

### Caso 4: Join (espera múltiple)

```
Flow:
    MATH_1 ┐
           ├→ ADD (x=MATH_1, y=MATH_2)
    MATH_2 ┘

GraphBuilder construye:
    dependencies["ADD"] = ["MATH_1", "MATH_2"]

Ejecución:
    1. MATH_1 completa
    2. ExecutionPlanner verifica ADD:
       - MATH_1 completó ✓
       - MATH_2 no completó ✗
       → ADD NO está listo

    3. MATH_2 completa
    4. ExecutionPlanner verifica ADD:
       - MATH_1 completó ✓
       - MATH_2 completó ✓
       → ADD está LISTO

    5. ADD ejecuta con ambos inputs
```

**Resultado**: ADD espera a que AMBOS predecesores completen.

---

## Ejemplo Completo: Flujo Simple

**Workflow**:
```
START → SET(counter=0) → GET(counter) → ADD(x=counter, y=1) → RETURN(result)
```

**Paso a Paso**:

### Inicialización:
```
1. FlowValidator valida el JSON ✓
2. GraphBuilder construye:
   - nodes: {START, SET, GET, ADD, RETURN}
   - dependencies: {
       SET: [START],
       GET: [SET],
       ADD: [GET],
       RETURN: [ADD]
     }
   - data_flow: {
       SET: {value: {from: START, output: "value"}},
       ADD: {x: {from: GET, output: "value"}, y: {from: START, output: "y"}},
       RETURN: {result: {from: ADD, output: "result"}}
     }

3. VariableStoreManager crea GlobalVariableStore
4. NodeLoader carga 5 clases
5. ActorManager crea 5 actors (con store_ref)
```

### Ejecución:
```
ITERACIÓN 1:
- ExecutionPlanner: ready = [START]
- DataGatherer: inputs = {external inputs}
- NodeExecutor: ejecuta START
- Resultado: {}
- Estado: START completado

ITERACIÓN 2:
- ExecutionPlanner: ready = [SET]
  (START completó, SET está listo)
- DataGatherer: inputs = {value: 0}
- NodeExecutor: ejecuta SET
  - SET llama: store.set.remote("counter", 0)
- Resultado: {value: 0}
- Estado: SET completado

ITERACIÓN 3:
- ExecutionPlanner: ready = [GET]
- DataGatherer: inputs = {}
- NodeExecutor: ejecuta GET
  - GET llama: store.get.remote("counter")
  - Retorna: 0
- Resultado: {value: 0}
- Estado: GET completado

ITERACIÓN 4:
- ExecutionPlanner: ready = [ADD]
- DataGatherer: inputs = {x: 0, y: 1}
  (x viene de GET, y es constante)
- NodeExecutor: ejecuta ADD
- Resultado: {result: 1}
- Estado: ADD completado

ITERACIÓN 5:
- ExecutionPlanner: ready = [RETURN]
- DataGatherer: inputs = {result: 1}
- NodeExecutor: ejecuta RETURN
- Resultado: {result: 1, status: 200}
- Estado: RETURN completado

ExecutionPlanner detecta RETURN ejecutado → TERMINAR
```

### Finalización:
```
- DataGatherer extrae resultado de RETURN: {result: 1}
- StateTracker proporciona estadísticas
- ActorManager limpia todos los actors
- VariableStoreManager limpia store
- Retornar ExecutionResult
```

---

## Consideraciones de Performance

### Paralelismo Automático

Ray maneja el paralelismo:
```
Si hay 10 nodos independientes listos:
    NodeExecutor crea 10 futures
    Ray distribuye automáticamente en workers disponibles
    Esperamos a que TODOS completen
```

**No necesitamos código de threading/multiprocessing manual**.

---

### Overhead de Comunicación

**Llamadas Remote**:
- Cada `actor.process.remote()` tiene overhead de serialización
- Para nodos muy pequeños (microsegundos), overhead puede dominar

**Mitigación**:
- Nodos deben ser "suficientemente pesados" (milisegundos+)
- Evitar nodos triviales (mejor fusionarlos)

---

### Caching de Resultados

**Opcional**: DataGatherer podría implementar cache:
```
Si un nodo es determinístico (mismos inputs → mismo output):
    Cache por (node_id, frozenset(inputs))
    En retry o replay, reutilizar resultado
```

---

## Extensiones Futuras

### 1. Ejecución Condicional

**IfElse Node** con dos exec-outputs:
```
GraphBuilder necesitaría:
    exec_connections = [
        {from: "IF", from_exec: "true", to: "NODE_A"},
        {from: "IF", from_exec: "false", to: "NODE_B"}
    ]

ExecutionPlanner necesitaría:
    Consultar qué exec-output se activó
    Solo marcar el camino correspondiente como ejecutable
```

---

### 2. Loops

**While/ForEach Node**:
```
StateTracker necesitaría:
    Rastrear contador de iteraciones
    Prevenir loops infinitos (max_iterations)

ExecutionPlanner necesitaría:
    Permitir ciclos en el grafo
    Detectar terminación de loop
```

---

### 3. Subflows

**Subflow Node** que ejecuta otro workflow:
```
Orchestrator necesitaría:
    Crear sub-orchestrator
    Pasar inputs al subflow
    Esperar resultado del subflow
    Continuar con flujo principal
```

---

### 4. Live Monitoring

**StateTracker + UI**:
```
StateTracker podría:
    Publicar eventos a un stream
    UI subscribe y muestra progreso en tiempo real
    Highlighting de nodo actualmente ejecutando
```

---

## Conclusión

Esta arquitectura modular proporciona:

✅ **Separación clara de responsabilidades**: Cada módulo tiene un propósito único

✅ **Flujo de datos bien definido**: Se entiende cómo la información fluye entre módulos

✅ **Testabilidad**: Cada módulo puede testearse independientemente

✅ **Mantenibilidad**: Cambios en un módulo no rompen otros

✅ **Extensibilidad**: Nuevas features se agregan sin reestructurar todo

✅ **Debuggability**: Problemas se aíslan a módulos específicos

La clave es entender que **el Orchestrator es solo el coordinador** - delega toda la lógica real a módulos especializados.
