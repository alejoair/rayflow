# Catálogo de Tipos de Nodos

## 1. Control Flow (Obligatorios)

### START Node
**Archivo:** `base/start.py`

**Único por flujo.** Define el punto de entrada y esquema de la API.

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

**Características:**
- Solo tiene `exec out`
- NO recibe conexiones de entrada
- Define `api_schema` para validación
- Solo puede haber UNO por flujo

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
│  - user_id ──────────┼─────▶
│  - action ───────────┼─────▶
└──────────┬───────────┘
           │ exec
           ▼
```

---

### RETURN Node
**Archivo:** `base/return_node.py`

**Pueden haber múltiples.** Marca el final del flujo y define la respuesta.

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

**Características:**
- Solo tiene `exec in` + data inputs
- NO tiene outputs
- Define `status_code` para API mode
- Puede haber MÚLTIPLES (diferentes salidas)

**Visual:**
```
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

---

### Debug/Print Node
**Archivo:** `base/debug.py`

Imprime valores para debugging durante desarrollo.

```python
@ray.remote
class DebugNode(RayflowNode):
    inputs = {"value": Any}
    outputs = {"value": Any}  # Pass-through

    def process(self, **inputs):
        print(f"[DEBUG] {self.config.get('label', 'Debug')}: {inputs['value']}")
        return inputs
```

---

## 2. Variables Globales

### GET Variable
**Archivo:** `variables/get_variable.py`

Lee una variable del GlobalVariableStore.

```python
@ray.remote
class GetVariableNode(RayflowNode):
    """
    Nodo que lee una variable del store global.
    No requiere inputs de datos, solo señal exec.
    """

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

**Características:**
- NO requiere data inputs
- Lee del GlobalVariableStore
- Outputs: `value: Any`

---

### SET Variable
**Archivo:** `variables/set_variable.py`

Escribe una variable en el GlobalVariableStore.

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

**Características:**
- Requiere input: `value`
- Escribe al GlobalVariableStore
- Pass-through output para encadenar

---

## 3. Math Operations

### Add
**Archivo:** `math/add.py`
```python
inputs = {"x": int|float, "y": int|float}
outputs = {"result": int|float}
```

### Subtract
**Archivo:** `math/subtract.py`
```python
inputs = {"x": int|float, "y": int|float}
outputs = {"result": int|float}
```

### Multiply
**Archivo:** `math/multiply.py`
```python
inputs = {"x": int|float, "y": int|float}
outputs = {"result": int|float}
```

### Divide
**Archivo:** `math/divide.py`
```python
inputs = {"x": int|float, "y": int|float}
outputs = {"result": int|float, "error": str}  # error si división por cero
```

---

## 4. Logic Operations

### If/Else (Branch)
**Archivo:** `logic/if_else.py`
```python
inputs = {"condition": bool, "true_value": Any, "false_value": Any}
outputs = {"result": Any}
config = {"exec_branches": True}  # Si true, tiene exec_true y exec_false outputs
```

### Compare
**Archivo:** `logic/compare.py`
```python
inputs = {"a": Any, "b": Any}
outputs = {"result": bool}
config = {"operator": "=="}  # ==, !=, <, >, <=, >=
```

### And/Or/Not
**Archivos:** `logic/and.py`, `logic/or.py`, `logic/not.py`
```python
# And/Or
inputs = {"a": bool, "b": bool}
outputs = {"result": bool}

# Not
inputs = {"value": bool}
outputs = {"result": bool}
```

---

## 5. String Operations

### Concat
**Archivo:** `string/concat.py`
```python
inputs = {"a": str, "b": str}
outputs = {"result": str}
```

### Format
**Archivo:** `string/format.py`
```python
inputs = {"template": str, "values": dict}
outputs = {"result": str}
# Ejemplo: template="{name} is {age}", values={"name": "John", "age": 30}
```

### Split
**Archivo:** `string/split.py`
```python
inputs = {"text": str, "delimiter": str}
outputs = {"parts": list}
```

---

## 6. I/O Operations

### HTTP Request
**Archivo:** `io/http_request.py`
```python
inputs = {"body": dict}
outputs = {"response": dict, "status_code": int}
config = {
    "url": "http://localhost:8091/execute",
    "method": "POST"
}
```

### File Read
**Archivo:** `io/file_read.py`
```python
inputs = {"path": str}
outputs = {"content": str}
config = {"encoding": "utf-8"}
```

### File Write
**Archivo:** `io/file_write.py`
```python
inputs = {"path": str, "content": str}
outputs = {"success": bool}
config = {"encoding": "utf-8", "mode": "w"}
```

---

## 7. Data Operations

### JSON Parse
**Archivo:** `data/json_parse.py`
```python
inputs = {"json_string": str}
outputs = {"data": dict}
```

### JSON Stringify
**Archivo:** `data/json_stringify.py`
```python
inputs = {"data": dict}
outputs = {"json_string": str}
```

### Dict Get
**Archivo:** `data/dict_get.py`
```python
inputs = {"dict": dict, "key": str}
outputs = {"value": Any}
config = {"default": None}  # Valor por defecto si key no existe
```

### List Operations
**Archivos:** `data/list_append.py`, `data/list_get.py`, `data/list_length.py`
```python
# Append
inputs = {"list": list, "item": Any}
outputs = {"list": list}

# Get
inputs = {"list": list, "index": int}
outputs = {"item": Any}

# Length
inputs = {"list": list}
outputs = {"length": int}
```

---

## Resumen por Categoría

```
nodes/
├── base/                   # Control flow obligatorio
│   ├── start.py           # ⚠️ Único por flujo
│   ├── return_node.py     # Puede haber múltiples
│   └── debug.py
│
├── variables/             # Estado global
│   ├── get_variable.py
│   └── set_variable.py
│
├── math/                  # Operaciones matemáticas
│   ├── add.py
│   ├── subtract.py
│   ├── multiply.py
│   └── divide.py
│
├── logic/                 # Lógica y branching
│   ├── if_else.py
│   ├── compare.py
│   ├── and.py
│   ├── or.py
│   └── not.py
│
├── string/                # Manipulación de texto
│   ├── concat.py
│   ├── format.py
│   └── split.py
│
├── io/                    # Input/Output
│   ├── http_request.py
│   ├── file_read.py
│   └── file_write.py
│
└── data/                  # Estructuras de datos
    ├── json_parse.py
    ├── json_stringify.py
    ├── dict_get.py
    ├── list_append.py
    ├── list_get.py
    └── list_length.py
```

## Reglas de Validación

### Por el Orquestador
1. **START:** Exactamente UNO por flujo
2. **RETURN:** Al menos UNO por flujo
3. **Variables:** Los nombres deben ser únicos en el flujo
4. **Tipos:** Los tipos de conexiones deben coincidir

### Visuales en el Editor
- **START:** Color verde, solo exec out
- **RETURN:** Color rojo, solo exec in + data in
- **Variables:** Color naranja, ícono especial
- **Math/Logic:** Color azul
- **I/O:** Color morado
- **Data:** Color cyan
