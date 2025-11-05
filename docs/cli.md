# CLI de RayFlow

## Instalación

```bash
pip install rayflow
```

## Comandos Disponibles

### rayflow create

Lanza el editor visual con servidor backend.

```bash
# Uso básico (puerto 8000 por defecto)
rayflow create

# Puerto personalizado
rayflow create --port 8080

# Directorio de trabajo personalizado
rayflow create --working-path ./my-project

# Ayuda
rayflow create --help
```

**Opciones:**
- `--port INTEGER`: Puerto para el servidor (default: 8000)
- `--working-path PATH`: Directorio de trabajo para nodos y flujos (default: directorio actual)

**Comportamiento:**
1. Inicia FastAPI backend en el puerto especificado
2. Sirve el editor React desde el backend
3. Expone API REST en `/api/nodes` para listar nodos
4. Sirve archivos estáticos (components/*.js, app.js, index.html)
5. Habilita CORS para desarrollo
6. Abre automáticamente el navegador (opcional)

**Output:**
```
🚀 RayFlow Editor starting...
📂 Working directory: /Users/username/my-project
🌐 Server running on http://localhost:8000
📝 Open http://localhost:8000 in your browser
```

**Environment Variables:**
- `NODES_PATH`: Directorio de nodos (default: `nodes/`)
- `FLOWS_PATH`: Directorio de flujos guardados (default: `flows/`)

---

### rayflow run (Planificado)

Ejecuta un flujo RayFlow desde JSON.

```bash
# Modo CLI - Ejecutar una vez
rayflow run miflujo.json --input '{"user_id": 123, "action": "process"}'

# Modo API Server - Exponer como servicio HTTP
rayflow run miflujo.json --port 8090

# Con archivo de inputs
rayflow run miflujo.json --input-file inputs.json

# Con timeout
rayflow run miflujo.json --input '{"x": 5}' --timeout 30

# Modo debug
rayflow run miflujo.json --input '{"x": 5}' --debug

# Ayuda
rayflow run --help
```

**Opciones:**
- `FLOW_PATH`: Ruta al archivo JSON del flujo (requerido)
- `--input TEXT`: JSON con inputs para el nodo START
- `--input-file PATH`: Archivo JSON con inputs
- `--port INTEGER`: Si se especifica, inicia en modo API server
- `--timeout INTEGER`: Timeout en segundos (default: sin límite)
- `--debug`: Habilita modo debug con logs detallados
- `--ray-address TEXT`: Dirección del cluster Ray (default: local)

**Comportamiento Modo CLI:**
1. Carga el grafo desde JSON
2. Valida estructura (START, RETURN, conexiones)
3. Inicializa Ray
4. Crea orquestador y actores
5. Ejecuta flujo con inputs proporcionados
6. Imprime resultado en stdout
7. Finaliza

**Comportamiento Modo API:**
1. Carga el grafo desde JSON
2. Valida estructura
3. Inicializa Ray
4. Crea servidor FastAPI
5. Expone endpoints:
   - `POST /execute` - Ejecutar flujo
   - `GET /schema` - Ver esquema
   - `GET /health` - Health check
   - `GET /docs` - Swagger UI
6. Mantiene servidor corriendo

**Output Modo CLI:**
```json
{
  "status_code": 200,
  "body": {
    "result": 42,
    "message": "Success"
  }
}
```

**Output Modo API:**
```
🚀 RayFlow API Server running on http://localhost:8090
📋 API Schema: http://localhost:8090/schema
📝 Docs: http://localhost:8090/docs
```

---

### rayflow list-nodes (Planificado)

Lista todos los nodos disponibles en el directorio de trabajo.

```bash
# Listar todos
rayflow list-nodes

# Solo built-in
rayflow list-nodes --builtin

# Solo user nodes
rayflow list-nodes --user

# Con detalles
rayflow list-nodes --verbose
```

**Output:**
```
Available Nodes:
  Built-in:
    - math_add          (nodes/math/add.py)
    - math_subtract     (nodes/math/subtract.py)
    - get_variable      (nodes/variables/get_variable.py)
    - set_variable      (nodes/variables/set_variable.py)
    - start             (nodes/base/start.py)
    - return            (nodes/base/return.py)

  User:
    - my_custom_node    (nodes/my_custom_node.py)
```

---

### rayflow new-node (Planificado)

Crea un template de nodo nuevo.

```bash
# Crear nodo básico
rayflow new-node my_custom_node

# Crear en categoría específica
rayflow new-node my_math_op --category math

# Con template específico
rayflow new-node my_api_call --template http

# Ayuda
rayflow new-node --help
```

**Opciones:**
- `NAME`: Nombre del nodo (requerido)
- `--category TEXT`: Categoría del nodo (default: root)
- `--template TEXT`: Template a usar (basic, http, async)

**Comportamiento:**
1. Valida nombre del nodo
2. Crea archivo en `nodes/[category]/[name].py`
3. Genera código template con estructura RayflowNode
4. Agrega comentarios explicativos
5. Imprime instrucciones de siguiente paso

**Output:**
```
✨ Created new node: nodes/math/my_math_op.py

📝 Edit the file to define:
   - inputs: Dict of input names and types
   - outputs: Dict of output names and types
   - process(**inputs): Implementation logic

💡 The node will be available in the editor after restart
```

---

### rayflow validate (Planificado)

Valida un archivo de flujo JSON.

```bash
# Validar estructura
rayflow validate miflujo.json

# Con verificación de nodos
rayflow validate miflujo.json --check-nodes

# Con sugerencias
rayflow validate miflujo.json --suggestions
```

**Output:**
```
✅ Flow is valid
   - 1 START node found
   - 2 RETURN nodes found
   - 15 total nodes
   - 23 connections
   - No circular dependencies
```

---

### rayflow version

Muestra la versión instalada.

```bash
rayflow version
# Output: RayFlow v0.1.0
```

---

## Ejemplos de Uso

### Desarrollo Local

```bash
# 1. Iniciar editor
rayflow create --port 8000

# 2. Crear flujo en el editor
# 3. Guardar como miflujo.json

# 4. Ejecutar flujo
rayflow run miflujo.json --input '{"user_id": 123}'
```

### Microservicio

```bash
# Terminal 1: Servicio de validación
rayflow run validate_user.json --port 8091

# Terminal 2: Servicio principal
rayflow run main_flow.json --port 8090

# El flujo principal puede llamar al validador vía HTTP
curl -X POST http://localhost:8090/execute \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123, "action": "process"}'
```

### Cluster Ray

```bash
# 1. Iniciar Ray cluster
ray start --head

# 2. Ejecutar flujo en cluster
rayflow run miflujo.json \
  --input '{"data": [...]}' \
  --ray-address auto
```

---

## Variables de Entorno

```bash
# Directorio de nodos
export NODES_PATH=/path/to/nodes

# Directorio de flujos
export FLOWS_PATH=/path/to/flows

# Dirección de Ray cluster
export RAY_ADDRESS=ray://localhost:10001

# Nivel de log
export RAYFLOW_LOG_LEVEL=DEBUG
```

---

## Configuración

### rayflow.toml (Opcional)

```toml
[rayflow]
nodes_path = "nodes/"
flows_path = "flows/"

[editor]
default_port = 8000
auto_open_browser = true

[runtime]
ray_address = "auto"
default_timeout = 300
```
