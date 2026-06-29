# Rayflow

[![PyPI version](https://img.shields.io/pypi/v/rayflow.svg)](https://pypi.org/project/rayflow/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://github.com/alejoair/rayflow/actions/workflows/test.yml/badge.svg)](https://github.com/alejoair/rayflow/actions/workflows/test.yml)

**Construye sistemas distribuidos dibujándolos: conecta nodos, enciéndelos, y quedan corriendo.**

Rayflow es un editor visual para construir backends sobre [Ray](https://www.ray.io/). Conectas nodos —cada uno una pieza de lógica en Python— con dos tipos de cable: uno marca el **orden de ejecución** y otro lleva los **datos**. Cuando cargas el grafo, sus nodos se levantan como procesos vivos y **quedan disponibles**: puedes invocarlos como una API, dispararlos con eventos, o dejarlos guardando estado entre llamadas.

No es un orquestador de tareas que corre y termina. Un flow **queda en pie**, con memoria, esperando a que lo invoquen — un servicio que diseñaste dibujándolo.

> Estado: temprano (alpha). El modelo de ejecución y el editor son funcionales; la API puede cambiar.

<!-- Captura del editor: subir a docs/ y enlazar con URL absoluta para que renderice en PyPI, p.ej.
![Editor visual de Rayflow](https://raw.githubusercontent.com/alejoair/rayflow/master/docs/editor.png)
-->

## Instalación

```bash
pip install rayflow
```

Requiere Python 3.10+. Ray, FastAPI y Uvicorn se instalan como dependencias.

## Quickstart

Lanza el servidor (editor visual + API REST):

```bash
rayflow serve --port 8000
```

- Editor visual: http://localhost:8000/editor
- API REST: http://localhost:8000/flows
- Health check: http://localhost:8000/health

O ejecuta un flow desde Python:

```python
import rayflow

# Carga, ejecuta y descarga un flow de una sola vez
result = rayflow.run("examples/suma.json", a=3, b=4)
print(result)  # {"result": 7}
```

## Cómo se dispara un flow

El mismo grafo puede ponerse en marcha de varias formas:

- **De una sola vez** — `rayflow.run(flow, **inputs)`: carga, ejecuta y descarga. Para un cálculo puntual.
- **Servido como API** — `load()` una vez e `execute()` muchas; expuesto por HTTP con streaming de eventos. El sistema queda residente y se invoca repetidamente.
- **Por evento** — `serve_events()` + un nodo `OnEvent`: el flow queda residente y lo dispara un evento, sin invocación directa.
- **Como componente de otro flow** — el nodo `CallFlow` ejecuta un flow dentro de otro.

Y de forma transversal a todos: un flow puede ser **stateless o stateful** — con o sin memoria entre invocaciones (variables del grafo y estado en los nodos residentes). Con `EmitEvent`, además, un flow puede disparar a otros y encadenar reacciones.

## Conceptos

Un flow es un grafo de **nodos** conectados por dos tipos de pin:

- **Exec pins** — definen el orden de ejecución (control).
- **Data pins** — llevan los valores entre nodos.

Cada nodo es una clase Python decorada. El decorador decide dónde corre, no qué hace:

```python
from rayflow.nodes.decorators import ray_node, ExecInput, ExecOutput, Input, Output, ExecContext

@ray_node              # corre distribuido (actor/task de Ray)
class Add:
    exec_in   = ExecInput()
    a         = Input("int", default=0)
    b         = Input("int", default=0)
    result    = Output("int")
    exec_out  = ExecOutput()

    async def run(self, ctx: ExecContext, a: int, b: int) -> None:
        ctx.set_output("result", a + b)
        await ctx.fire("exec_out")
```

- `@ray_node` corre distribuido sobre Ray (con exec pins es un actor persistente y stateful).
- `@engine_node` corre local, dentro del motor (para lógica de control ligera).

Un flow se guarda como JSON. Por ejemplo, el `suma` del quickstart:

```json
{
  "name": "suma",
  "inputs":  { "a": "int", "b": "int" },
  "outputs": { "result": "int" },
  "nodes": [
    { "id": "entry", "type": "FlowInput" },
    { "id": "add", "type": "Add", "exec_in": "entry",
      "inputs": { "a": "entry.a", "b": "entry.b" } },
    { "id": "exit", "type": "FlowOutput", "exec_in": "add",
      "inputs": { "result": "add.result" } }
  ]
}
```

## API de Python

```python
import rayflow

rayflow.run(source, **inputs)   # carga + ejecuta + descarga (one-shot)
rayflow.load(source)            # deja el flow residente en Ray
rayflow.execute(name, inputs)   # ejecuta un flow ya cargado (stream de eventos)
rayflow.unload(name)            # descarga el flow
rayflow.serve_events(source)    # deja el flow residente, suscrito al bus de eventos
rayflow.stop(graph_id, events)  # desuscribe y descarga
```

## Documentación

- Guía de arquitectura y desarrollo: [`CLAUDE.md`](https://github.com/alejoair/rayflow/blob/master/CLAUDE.md)
- Análisis conceptual: [`docs/analisis-conceptual.md`](https://github.com/alejoair/rayflow/blob/master/docs/analisis-conceptual.md)
- Ejemplos de flows: [`examples/`](https://github.com/alejoair/rayflow/tree/master/examples)

## Desarrollo

```bash
pip install -e ".[dev]"
pytest tests/
```

El frontend del editor (React + Vite) vive en `rayflow/editor/frontend/`:

```bash
cd rayflow/editor/frontend
npm install
npm run build
```
