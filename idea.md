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
