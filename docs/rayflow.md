# rayflow

> **Documento histórico — diseño v1.** Describe el diseño original y **ya no
> coincide con la implementación actual** en puntos centrales (contrato de
> `run`, motor por cola vs. recursión, fan-out exec, ciclo de vida de actores,
> `CallFlow`, nombres del bus de eventos). Para la arquitectura vigente ver
> `CLAUDE.md`; para el modelo conceptual y la tabla de divergencias (§12) ver
> `docs/analisis-conceptual.md`. Se conserva como registro de intención.

## ¿Qué es rayflow?

rayflow es un sistema de orquestación de workflows basado en grafos visuales estilo Blueprint de Unreal Engine, construido sobre Ray core, donde los nodos son tareas o actores de Ray conectados por execution pins y data pins. Soporta múltiples grafos concurrentes comunicados por eventos.

---

## 0. Modelo de ejecución

rayflow tiene dos planos:

- **Plano de ejecución (control):** secuencial y determinista. Los execution pins definen un único orden de disparo. El usuario nunca lanza dos cadenas de efectos a la vez.
- **Plano de datos:** las dependencias entre data pins forman un DAG que Ray evalúa en paralelo cuando los nodos son independientes.

El paralelismo en rayflow es **único, implícito y de datos**: el usuario no lo declara ni lo coordina, emerge de la independencia entre cómputos y el scheduler de Ray lo explota automáticamente. No existe paralelismo de control. El resto del documento asume este modelo y no lo repite.

Regla mental única: **el orden de los efectos es secuencial; el cómputo de los valores es paralelo cuando puede serlo.**

---

## 1. Modelo de nodos

### Tipos de nodo
- Hay 2 tipos de nodo: **nodos de datos** (sin execution pins) y **nodos de ejecución** (con execution pins).
- Un **nodo de datos** no está en la cadena de control: la única forma de que corra es que un nodo de ejecución aguas abajo lea su salida. Se evalúa bajo demanda en ese instante, recorriendo hacia atrás la cadena de dependencias de datos. Puede leer estado del grafo (variables vía `Get`, outputs de nodos de ejecución ya disparados), así que dos evaluaciones en momentos distintos pueden dar valores distintos. Se implementa como task de Ray.
- Un **nodo de ejecución** tiene execution pins y puede tener estado. Se implementa como actor de Ray. Al dispararse, materializa sus data outputs en el estado del grafo (sección 3).
- La distinción la determina la presencia o ausencia de `ExecInput`/`ExecOutput` en la declaración del nodo; el loader la infiere automáticamente.

### Pins
- Hay dos tipos de pin: execution pins y data pins, como los blueprints de Unreal Engine.
- Los execution pins transportan el disparo (trigger) entre nodos. Los data pins transportan valores.
- Un data output puede conectarse a varios data inputs (fan-out). El mismo `ObjectRef` se comparte sin copia; los valores del object store son inmutables, así que el fan-out es seguro por construcción.
- Un exec output va a exactamente un exec input. Para disparar varios nodos en orden se usa `Sequence`.

### Default values de pins
- **Todo data input tiene un valor por defecto**, declarado en la definición del nodo o heredado del default del tipo (`0`, `0.0`, `""`, `False`, `[]`, `{}`, `None` para `Any`).
- El default se usa en dos casos: (1) el pin no tiene conexión ni valor literal en el grafo (input opcional); (2) el pin está conectado al data output de un nodo de ejecución que **no se ha disparado** en esta ejecución (por ejemplo, está en la rama no tomada de un `Branch`). En ese caso la lectura entrega el default del pin consumidor. Nunca es un error de runtime.
- Un nodo puede declarar un input como requerido sin default; entonces el build exige conexión o literal (validación 2).

### Definición de un nodo
- Un nodo se define como un archivo Python con una clase decorada con `@node`.
- Los pins se declaran como anotaciones de clase: `Input[T]`, `Output[T]`, `ExecInput`, `ExecOutput`. Un input con default se declara con valor: `Input[int] = 5`.
- El loader descubre los nodos por archivo, sin registro manual.
- `run` recibe los valores de los data inputs ya materializados, como valores de solo lectura (inmutables por construcción; un nodo no puede mutar su input). El autor de un nodo no necesita conocer Ray.

### Contrato de retorno de `run`
- Nodo de datos: devuelve `{pin_name: valor}`.
- Nodo de ejecución: devuelve `(exec_outputs_disparados, {pin_name: valor})`.
- El nodo devuelve qué exec output(s) propio(s) dispara; no conoce destinos. El engine cruza los pins disparados con las aristas exec del grafo para encolar los triggers siguientes.

### Nodos de control
- `Sequence`: dispara sus exec outputs en orden, esperando a que cada uno termine antes del siguiente (semántica Unreal). Es la única primitiva para disparar varios destinos.
- `Branch`: tiene dos exec outputs (`true`, `false`); `run` devuelve el nombre del pin que corresponde según su data input `condition`.
- `ForEach`: nodo de ejecución (actor, mantiene estado de iteración). Exec input `exec_in`, data input `array: list[T]`, exec output `loop_body` (se dispara una vez por elemento, en orden), exec output `completed` (se dispara al terminar). Data outputs `element: T` e `index: int` disponibles dentro del loop. Las iteraciones son secuenciales.
- **Ciclos de ejecución:** en v1 los ciclos manuales en el plano de ejecución (un exec output conectado a un nodo anterior de su propia cadena) están prohibidos y los rechaza el build. Los loops se expresan exclusivamente con `ForEach`. Esta restricción elimina la clase de flows colgados por loops mal cerrados y puede relajarse en versiones futuras sin romper grafos existentes.

---

## 2. Motor de ejecución (engine)

- El engine usa un event loop sobre una cola de triggers, drenando un trigger a la vez en orden secuencial. Dispara el nodo, espera su resultado, y encola los triggers siguientes según los exec outputs disparados.
- Como la ejecución de control es secuencial, ningún estado cambia mientras se resuelven los inputs de un nodo: todas las lecturas de una misma resolución ven la misma foto del estado, aunque se repartan en paralelo.
- Para resolver los data inputs de un nodo, el engine construye el subgrafo de datos aguas arriba y lo evalúa encadenando `ObjectRef`. Los nodos de datos independientes dentro de ese subgrafo los evalúa Ray en paralelo; las dependencias que vienen de nodos de ejecución se leen del estado del grafo (sección 3), aplicando el default del pin si nunca se dispararon.
- Los data inputs se pasan como `ObjectRef` antes de invocar `run`. El nodo no conoce el grafo.
- `ray.get` se aplica solo en puntos de decisión de control (Branch necesita el bool materializado) y en la salida final del grafo. Todo lo demás se encadena como `ObjectRef`.
- Al primer fallo de un nodo, el engine aborta el flow y reporta el error. Ray maneja reintentos a nivel de nodo (`max_retries` en tasks, `max_restarts` en actores).
- Los actores de nodos de ejecución se crean al arrancar el flow y se destruyen al terminar. No se reusan entre ejecuciones.

---

## 3. Estado y variables

- El object store de Ray es la capa de valores inmutables de la ejecución: todo valor producido es un `ObjectRef` en el store.
- Hay un solo actor de estado por grafo. Como la ejecución es secuencial, nunca recibe dos escrituras concurrentes. Mantiene dos cosas:
  - **Variables:** bindings mutables `nombre → ObjectRef`. `Set` actualiza el binding; `Get` lo lee. `Get` es un nodo de datos (sin execution pins); su valor depende del estado del grafo en el momento de la lectura.
  - **Outputs vigentes de nodos de ejecución:** `nodo → {pin: ObjectRef}`, escrito por cada nodo de ejecución en su disparo. Es de donde los nodos de datos leen las dependencias que vienen de nodos de ejecución. Para un nodo reentrante (dentro de un `ForEach`), su entrada se sobrescribe en cada disparo; el valor vigente es siempre el del último disparo, que por la secuencialidad es el correcto en el punto en que se lee. Si un nodo de ejecución nunca se disparó, no hay entrada y la lectura resuelve al default del pin consumidor (sección 1).

---

## 4. Sistema de eventos

- Pueden correr varios grafos simultáneamente. El paralelismo entre grafos distintos sí es real; lo que es secuencial es el plano de ejecución *dentro* de un grafo.
- El sistema de eventos usa un actor Ray global con nombre fijo (`rayflow_event_bus`) que mantiene el registro `event_name → [grafo_id, ...]`. Los grafos se suscriben al arrancar y se desuscriben al terminar.
- `EmitEvent` es un nodo de ejecución que llama al actor global con el nombre del evento y un payload opcional. El payload se pone en el object store (`ray.put`) y se pasa como `ObjectRef` al actor global.
- `OnEvent` es el punto de entrada de un grafo disparado por evento. No tiene exec input; el actor global lo activa desde fuera. Tiene exec output y opcionalmente data outputs con el payload del evento.
- El dispatch es fire-and-forget: el actor global notifica a los suscriptores con `.remote()` y el grafo emisor continúa sin bloquear.
- **Aislamiento de fallos entre grafos:** los grafos disparados por evento son ejecuciones independientes. Si el grafo emisor falla después de emitir, los grafos ya disparados continúan; el aborto por fallo es local a cada grafo. Un evento emitido es un hecho consumado.

---

## 5. Esquema del grafo (JSON)

### Estructura
- El grafo se serializa en JSON. El loader deserializa el JSON a dataclasses tipadas antes de pasarlo al engine y al build.
- El JSON tiene siete campos de primer nivel: `name`, `version`, `events`, `variables`, `inputs`, `outputs` y `nodes`.
- `version` es informativo en v1; no afecta a la ejecución. Reservado para migraciones de esquema futuras.

### Interfaz pública
- `inputs` y `outputs` declaran la interfaz pública del flow con nombre y tipo.
- `FlowInput` expone los inputs como data outputs y tiene exec output `then`. `FlowOutput` recibe los outputs como data inputs y tiene exec input.
- Un flow sin parámetros usa `OnStart` en lugar de `FlowInput`. Un flow disparado por evento usa `OnEvent`. Un flow que quiere una UI web usa `ChatTrigger` (idéntico a `OnStart` pero con `frontend` declarado). Cualquier nodo de entrada puede declarar `frontend = "<dir>"` — un directorio de assets estáticos hermano del `.py` del nodo — y cuando el flow se sirve con `rayflow serve --file`, ese bundle se monta en `GET /flows/{name}/ui`. El JS del bundle habla con el flow por el endpoint `/flows/{name}/run` normal; `frontend` solo selecciona "qué UI servir", no es un transporte nuevo.

### API de invocación
- Un flow se ejecuta desde Python con `rayflow.run(path_o_flow, **inputs) → dict`. La función carga, hace build, ejecuta y devuelve los outputs declarados en `FlowOutput` ya materializados (`ray.get` aplicado). Versión asíncrona: `rayflow.run_async(...) → ObjectRef`-like awaitable con los mismos outputs.
- Los flows por evento no se invocan directamente; se registran con `rayflow.serve(path_o_flow)` que los suscribe al event bus y los deja residentes hasta `stop()`.

### Convenciones de conexión
- Los valores estáticos se declaran como data input pins con valor literal en `inputs`. Todo es pin; no hay campo `config` separado.
- Las conexiones se declaran desde el consumidor: un data input con un string `"node_id.pin_name"` es una arista; un valor literal es un valor estático. Un data input ausente usa su default (sección 1).
- El exec input se declara con `exec_in`. Para nodos con varios exec inputs puede ser una lista.
- Esta convención permite a un LLM escribir nodos en orden topológico sin mantener listas de aristas separadas.

### Sistema de tipos
- Los data pins usan tipos Python nativos: `int`, `float`, `str`, `bool`, `list`, `dict`, `Any`.
- **Genéricos opcionales:** `list[T]` y `dict[str, T]` se admiten en las anotaciones de pin. Un `list` sin parámetro equivale a `list[Any]`. La parametrización permite que `ForEach` propague el tipo: con `array: list[str]`, su `element` es `str` y la validación estricta se conserva dentro del loop. Si el tipo del elemento no es inferible, degrada a `Any` sin error.
- La compatibilidad es estricta: dos pins conectados deben tener el mismo tipo o uno de los dos ser `Any` (a nivel de parámetro también: `list[str]` conecta con `list[str]` y con `list[Any]`, no con `list[int]`). Sin coerción implícita.

### Build time
- Los tipos de las conexiones se evalúan en build time.
- El build valida cuatro cosas:
  1. Compatibilidad de tipos en aristas data (incluyendo parámetros genéricos).
  2. Todo data input requerido sin default tiene arista o valor literal.
  3. Todo exec input tiene exactamente una arista entrante.
  4. **Aciclicidad:** el subgrafo de datos es acíclico (un ciclo entre nodos de datos sería recursión infinita en la evaluación), y el plano de ejecución no contiene ciclos manuales (los loops solo vía `ForEach`).
- Si falla cualquier validación, el flow no se ejecuta.
- El build produce una estructura ejecutable tipada lista para el engine.

---

## 6. Requisitos del editor

- **Señalización visual de tipos de nodo:** los nodos de datos se pintan distintos de los nodos de ejecución (convención Unreal: los de datos sin pin de ejecución blanco, color propio). El usuario debe poder distinguir a simple vista "esto se ejecuta" de "esto se lee".
- **Selección del punto de entrada:** al crear un flow, el editor pregunta cómo se dispara (manual, con parámetros, o por evento) y coloca el nodo de entrada correcto (`OnStart`, `FlowInput` u `OnEvent`). El usuario no decide leyendo la spec.
- **Validación en vivo:** las cuatro comprobaciones del build se ejecutan en el canvas a medida que el usuario conecta, no solo en build. Una conexión inválida se marca visualmente y se explica en lenguaje de usuario, no con jerga del motor. El build sigue siendo la red de seguridad para flows escritos a mano o por LLM.
