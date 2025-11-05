# Formato JSON del Grafo

## Estructura General

```json
{
  "name": "My Flow",
  "nodes": [
    {
      "id": "node_001",
      "type": "math_add",
      "position": {"x": 100, "y": 200},
      "label": "Add Numbers",
      "config": {}
    }
  ],
  "connections": [
    {
      "from": "node_001",
      "fromOutput": "result",
      "to": "node_002",
      "toInput": "x"
    },
    {
      "from": "node_001",
      "fromExec": "finish",
      "to": "node_002",
      "toExec": "exec"
    }
  ]
}
```

## Nodos

### Campos Obligatorios

- **id:** String único identificador del nodo (ej: `"node_001"`, `"node_042"`)
- **type:** String tipo del nodo, corresponde al archivo en `nodes/` (ej: `"math_add"`, `"get_variable"`)
- **position:** Objeto con coordenadas `x` e `y` para el editor visual

### Campos Opcionales

- **label:** String nombre visible del nodo en el editor (por defecto: mismo que `type`)
- **config:** Object configuración específica del nodo

### Ejemplos de Nodos

#### Nodo Simple (Math Add)
```json
{
  "id": "node_001",
  "type": "math_add",
  "position": {"x": 100, "y": 200},
  "label": "Sum A + B"
}
```

#### Nodo con Configuración (GET Variable)
```json
{
  "id": "node_002",
  "type": "get_variable",
  "position": {"x": 300, "y": 200},
  "label": "Get Counter",
  "config": {
    "variable_name": "counter"
  }
}
```

#### Nodo START
```json
{
  "id": "start",
  "type": "start",
  "position": {"x": 50, "y": 100},
  "label": "Start",
  "config": {
    "api_schema": {
      "user_id": {
        "type": "int",
        "required": true,
        "description": "ID del usuario"
      },
      "action": {
        "type": "str",
        "required": true
      }
    }
  }
}
```

#### Nodo RETURN
```json
{
  "id": "return_success",
  "type": "return",
  "position": {"x": 800, "y": 100},
  "label": "Success",
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

## Conexiones

Hay dos tipos de conexiones:

### 1. Conexiones de Activación (Exec)

Controlan el flujo de ejecución entre nodos.

```json
{
  "from": "node_001",
  "fromExec": "finish",    // Señal que emite el nodo origen
  "to": "node_002",
  "toExec": "exec"         // Señal que recibe el nodo destino
}
```

**Campos:**
- **from:** ID del nodo origen
- **fromExec:** Nombre de la señal de salida (generalmente `"finish"`)
- **to:** ID del nodo destino
- **toExec:** Nombre de la señal de entrada (generalmente `"exec"`)

### 2. Conexiones de Datos

Pasan datos entre nodos.

```json
{
  "from": "node_001",
  "fromOutput": "result",   // Output del nodo origen
  "to": "node_002",
  "toInput": "x"            // Input del nodo destino
}
```

**Campos:**
- **from:** ID del nodo origen
- **fromOutput:** Nombre del output del nodo origen
- **to:** ID del nodo destino
- **toInput:** Nombre del input del nodo destino

## Ejemplo Completo

```json
{
  "name": "Counter Flow",
  "nodes": [
    {
      "id": "start",
      "type": "start",
      "position": {"x": 50, "y": 100},
      "config": {
        "api_schema": {
          "initial_value": {"type": "int", "required": true}
        }
      }
    },
    {
      "id": "node_001",
      "type": "set_variable",
      "position": {"x": 250, "y": 100},
      "label": "Initialize Counter",
      "config": {
        "variable_name": "counter"
      }
    },
    {
      "id": "node_002",
      "type": "get_variable",
      "position": {"x": 450, "y": 100},
      "label": "Read Counter",
      "config": {
        "variable_name": "counter"
      }
    },
    {
      "id": "node_003",
      "type": "math_add",
      "position": {"x": 650, "y": 100},
      "label": "Increment"
    },
    {
      "id": "node_004",
      "type": "set_variable",
      "position": {"x": 850, "y": 100},
      "label": "Update Counter",
      "config": {
        "variable_name": "counter"
      }
    },
    {
      "id": "return_success",
      "type": "return",
      "position": {"x": 1050, "y": 100},
      "config": {
        "name": "success",
        "status_code": 200,
        "response_schema": {
          "counter": {"type": "int"}
        }
      }
    }
  ],
  "connections": [
    {
      "from": "start",
      "fromExec": "finish",
      "to": "node_001",
      "toExec": "exec"
    },
    {
      "from": "start",
      "fromOutput": "initial_value",
      "to": "node_001",
      "toInput": "value"
    },
    {
      "from": "node_001",
      "fromExec": "finish",
      "to": "node_002",
      "toExec": "exec"
    },
    {
      "from": "node_002",
      "fromExec": "finish",
      "to": "node_003",
      "toExec": "exec"
    },
    {
      "from": "node_002",
      "fromOutput": "value",
      "to": "node_003",
      "toInput": "x"
    },
    {
      "from": "node_003",
      "fromExec": "finish",
      "to": "node_004",
      "toExec": "exec"
    },
    {
      "from": "node_003",
      "fromOutput": "result",
      "to": "node_004",
      "toInput": "value"
    },
    {
      "from": "node_004",
      "fromExec": "finish",
      "to": "return_success",
      "toExec": "exec"
    },
    {
      "from": "node_004",
      "fromOutput": "value",
      "to": "return_success",
      "toInput": "counter"
    }
  ]
}
```

## Validación del JSON

### Reglas Obligatorias

1. **Exactamente UN nodo START**
2. **Al menos UN nodo RETURN**
3. **IDs únicos** para todos los nodos
4. **Conexiones válidas:**
   - `from` y `to` deben existir en `nodes`
   - `fromOutput` debe existir en outputs del nodo origen
   - `toInput` debe existir en inputs del nodo destino
5. **No ciclos infinitos** (opcional, según diseño de loops)

### Validador Ejemplo

```python
def validate_graph(graph_json):
    """Valida estructura del grafo"""

    # Validar nodos START
    start_nodes = [n for n in graph_json["nodes"] if n["type"] == "start"]
    assert len(start_nodes) == 1, "Debe haber exactamente UN nodo START"

    # Validar nodos RETURN
    return_nodes = [n for n in graph_json["nodes"] if n["type"] == "return"]
    assert len(return_nodes) >= 1, "Debe haber al menos UN nodo RETURN"

    # Validar IDs únicos
    node_ids = [n["id"] for n in graph_json["nodes"]]
    assert len(node_ids) == len(set(node_ids)), "Los IDs deben ser únicos"

    # Validar conexiones
    for conn in graph_json["connections"]:
        assert conn["from"] in node_ids, f"Nodo {conn['from']} no existe"
        assert conn["to"] in node_ids, f"Nodo {conn['to']} no existe"

    return True
```

## Conversión Node Type → Archivo

El orquestador convierte el `type` del nodo en la ruta del archivo:

```python
def type_to_path(node_type):
    """
    Ejemplos:
    "math_add" → "nodes/math/add.py"
    "get_variable" → "nodes/variables/get_variable.py"
    "start" → "nodes/base/start.py"
    """
    parts = node_type.split("_")
    if len(parts) == 1:
        # Nodo base
        return f"nodes/base/{parts[0]}.py"
    else:
        # Nodo categorizado
        category = parts[0]
        name = "_".join(parts[1:])
        return f"nodes/{category}/{name}.py"
```
