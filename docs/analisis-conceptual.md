# Análisis conceptual de Rayflow

> Este documento analiza Rayflow **en sus propios términos**: qué ideas lo
> sostienen, cómo se relacionan entre sí y dónde están sus zonas grises
> conceptuales. No es una guía de uso ni una revisión de implementación línea
> a línea. La fuente de verdad es el código (`rayflow/`), no la documentación
> previa; donde el código y `docs/rayflow.md` discrepan, se analiza lo que el
> código hace y se anota la divergencia (§12).
>
> Punto de partida del recorrido: **el engine** (`rayflow/engine/executor.py`),
> porque es donde se materializa el modelo de cómputo del que cuelga todo lo
> demás.

---

## 1. Qué es Rayflow, definido por lo que hace

Rayflow es un sistema donde **un grafo descrito en JSON se convierte en un
conjunto de actores vivos que ejecutan ese grafo bajo demanda**. El grafo no es
un script que corre y termina: se *carga* (`load`), se *ejecuta* tantas veces
como haga falta (`execute`), y se *descarga* (`unload`). Entre ejecuciones el
estado sobrevive. Mientras está cargado puede además reaccionar a eventos.

El grafo tiene **dos planos superpuestos** sobre el mismo conjunto de nodos:

- Un **plano de ejecución** (los *exec pins*) que define un orden de disparo.
- Un **plano de datos** (los *data pins*) que define de dónde sale cada valor.

Toda la identidad de Rayflow está en cómo se define cada plano y, sobre todo,
en **cómo se pegan los dos**. El resto del documento desarrolla eso.

El vocabulario primitivo del sistema es pequeño y conviene fijarlo antes de
seguir:

| Término | Qué es |
|---|---|
| **Nodo** | Una clase Python decorada. Declara pins y un método `run`. |
| **Pin** | Un punto de conexión. Cuatro variantes: `ExecInput`, `ExecOutput`, `Input` (data), `Output` (data). |
| **Plano de ejecución** | El grafo formado por las aristas exec. Define *cuándo* corre cada nodo. |
| **Plano de datos** | El grafo formado por las aristas data. Define *qué valor* recibe cada input. |
| **Engine** | `FlowEngine`: el actor que recorre el plano de ejecución y resuelve el de datos. |
| **GraphState** | El actor que guarda variables y los outputs vigentes de los nodos. |
| **Flow cargado** | Un grafo con sus actores vivos y su GraphState persistente. |

---

## 2. El modelo de cómputo (el engine)

### 2.1 El plano de ejecución es una recursión en profundidad

El corazón del engine es `_run_loop` (`executor.py:142`). Recorrer el plano de
ejecución consiste en: comprobar si un nodo está listo, dispararlo, y continuar
con sus sucesores. Pero el detalle decisivo no está en `_run_loop` sino en
**cómo continúa la ejecución de un nodo al siguiente**.

Un nodo no "devuelve" su continuación. La provoca él mismo, desde dentro de su
`run`, llamando `await ctx.fire("exec_out")`. Y `ctx.fire` **no encola** el
siguiente disparo: ejecuta el subgrafo entero de esa salida y no retorna hasta
que ese subgrafo termina (`fire` / `_local_fire`, `executor.py:97` y `:113`,
ambas hacen `await self._run_loop(target)`).

La consecuencia es la idea más importante del sistema:

> **El `run` de un nodo permanece en la pila mientras todo lo que cuelga de su
> exec output se ejecuta. Disparar un exec pin es una llamada bloqueante que
> corre la continuación completa.**

Esto se ve directo en `Add` (`math.py:14`):

```python
async def run(self, ctx, a, b):
    ctx.set_output("result", a + b)
    await ctx.fire("exec_out")   # no vuelve hasta que TODO lo de aguas abajo terminó
```

De aquí salen, sin maquinaria adicional, tres propiedades:

1. **Orden de efectos estrictamente secuencial y en profundidad.** El recorrido
   es un DFS: se baja hasta el final de una cadena antes de volver. No hay una
   cola de pendientes; la pila de llamadas *es* el estado del recorrido.

2. **Los bucles se expresan en el lenguaje anfitrión, no en el grafo.** `ForEach`
   (`control.py:130`) es un `for` de Python que intercala `ctx.fire("loop_body")`
   en cada vuelta:

   ```python
   for i, element in enumerate(array or []):
       ctx.set_output("element", element)
       await ctx.fire("loop_body")   # corre el cuerpo entero, vuelve, siguiente vuelta
   await ctx.fire("completed")
   ```

   El cuerpo del loop se ejecuta anidado dentro del `run` del `ForEach`. Por eso
   no hace falta ningún concepto de "back-edge" ni de iteración en el grafo.

3. **El plano de ejecución es un DAG; la repetición es reentrancia, no ciclo.**
   El build rechaza ciclos exec (`_check_exec_cycles`, `validator.py:549`). Lo que
   un loop hace es **reentrar** a los mismos nodos varias veces — atravesar la
   arista `loop.loop_body → body` N veces — sin que `body` tenga una arista de
   vuelta. La diferencia entre "ciclo" (prohibido) y "reentrancia" (el mecanismo
   de todo loop) es central y es lo que hace que un DAG pueda iterar.

### 2.2 La concurrencia existe, pero es de ejecución cooperativa

Cuando un exec output tiene más de un destino, o un nodo tiene varios sucesores,
el engine los lanza con `asyncio.gather` (`executor.py:109`, `:124`, `:147`). El
`Parallel` (`control.py:100`) explota esto explícitamente:

```python
branches = await ctx.exec_outputs_except("joined")
await asyncio.gather(*[ctx.fire(b) for b in branches])
await ctx.fire("joined")
```

`FlowEngine` es un actor Ray **async**, así que su event loop puede tener varias
ramas en vuelo a la vez. Dos matices importantes:

- La concurrencia es **cooperativa dentro de un único event loop**: las ramas
  avanzan cuando ceden en un `await`. No hay paralelismo real *del control*; hay
  *entrelazado*.
- El paralelismo **real** aparece cuando los nodos de las ramas son `@ray_node`:
  su `run` corre en un actor remoto, y mientras el engine espera ese RPC puede
  hacer avanzar otra rama. El cómputo se solapa de verdad; la *orquestación*
  sigue siendo un solo event loop secuencial.

Esto matiza la "regla mental" de que no hay paralelismo de control: lo hay, como
entrelazado cooperativo, y se vuelve solapamiento real con `@ray_node`.

### 2.3 El plano de datos se resuelve por demanda (pull)

Un input no se "entrega" a un nodo: se **resuelve** justo antes de que el nodo
corra (`_resolve_inputs` → `_resolve_pin`, `executor.py:309` y `:315`). La
resolución de un pin tiene exactamente tres caminos:

1. **Literal** → se sube al object store tal cual (`ray.put(literal)`).
2. **Referencia `nodo.pin` cuyo productor ya escribió** → se lee de `GraphState`
   (`get_node_output`).
3. **Referencia a un nodo sin exec pins (puro) que aún no corrió** → se ejecuta
   ese nodo *en ese instante* (`_eval_pure_engine_node`, `executor.py:341`) y se
   usa su resultado.
4. (Caso límite) Si el productor es un nodo de ejecución que **nunca se disparó**,
   la lectura no falla: entrega el *default del pin consumidor* (`executor.py:335-339`).

Todo viaja como `ObjectRef` y solo se materializa con `ray.get` en la frontera
(el `_resolve_refs` final sobre el resultado del flow, `executor.py:90`).

Dos rasgos conceptuales de este modelo:

- **Los nodos puros no se memoizan.** El resultado de `_eval_pure_engine_node`
  no se guarda en `GraphState`. Si tres consumidores leen la salida del mismo
  nodo puro, ese nodo corre tres veces. Es correcto *bajo el supuesto de que un
  nodo sin exec pins es realmente puro* — supuesto que el sistema asume pero no
  impone (un `@engine_node` sin exec pins puede leer variables o tener efectos;
  `Get` en `variables.py:14` es justamente eso: "puro" pero dependiente del
  estado).
- **La lectura nunca es un error de tipo "valor ausente".** El cuarto camino
  garantiza que cualquier input siempre resuelve a *algo* (default). Esto hace
  que ramas no tomadas de un `Branch` no rompan a los consumidores que cuelgan
  de ellas.

### 2.4 La costura entre los dos planos: el último-valor-escrito

Aquí está la decisión que define el carácter de Rayflow. Una "arista de datos"
**significa dos cosas distintas según quién sea el productor**:

- Si el productor es un **nodo puro**, la arista es una dependencia que se
  *recalcula* cuando se lee.
- Si el productor es un **nodo de ejecución**, la arista es la *lectura de un
  registro mutable*. Cuando ese nodo se dispara, escribe sus data outputs a
  `GraphState` (`set_output`); el consumidor, más tarde, lee **el último valor
  que ese nodo escribió**.

`GraphState.set_node_outputs` (`state/actor.py:47`) hace exactamente esto: un
`node_id → {pin → valor}` que se sobrescribe en cada disparo. No hay historial:
solo el valor vigente.

El caso que lo vuelve nítido es `ForEach.element`. No es una arista de datos en
el sentido de "este valor fluye": es un registro que el `ForEach` sobrescribe en
cada vuelta y que el cuerpo del loop lee como "el elemento de la iteración
actual". Funciona porque el recorrido es secuencial y en profundidad (§2.1): en
el momento en que el cuerpo lee `forEach.element`, el valor vigente es,
necesariamente, el de la vuelta en curso.

> **El plano de datos es, en parte, dataflow por demanda (nodos puros) y, en
> parte, memoria compartida de último-valor-escrito sincronizada por el orden
> del plano de ejecución (nodos de ejecución).** La corrección del segundo caso
> depende por completo de la secuencialidad del primero.

Este es el pegamento conceptual del sistema. No es un accidente: es lo que
permite que patrones imperativos familiares (acumular en un contador, iterar y
escribir) se expresen en el grafo. El precio es que una arista `A.x → B` no se
puede interpretar de forma aislada: su valor depende de *cuándo* se dispara `B`
respecto de `A`.

### 2.5 Disponibilidad y *joins*

Un nodo puede tener varias aristas exec entrantes. El build distingue dos
semánticas (`validator.py:404-416`):

- **`and`** (lista de fuentes): el nodo espera a que **todas** lleguen. El engine
  lo implementa acumulando llegadas en `_exec_arrivals` y disparando solo cuando
  el conjunto cubre todas las fuentes (`_is_ready`, `executor.py:151`).
- **`or`** (`{"or": [...]}`): el nodo no se registra en `_exec_arrivals`, así que
  `_is_ready` devuelve siempre `True` — se dispara **con cada** llegada.

Conviene notar que `_is_ready` usa un *set* de llegadas y no marca al nodo como
"ya disparado". En un DAG donde cada fuente dispara una vez esto es correcto; es
un invariante que descansa en la topología, no en un guardia explícito.

---

## 3. El modelo de estado

Rayflow tiene **un único lugar de estado mutable por flow**: el actor
`GraphState` (`state/actor.py`). Guarda dos cosas conceptualmente distintas:

1. **Variables** — bindings nombrados (`nombre → valor`), explícitos, escritos
   con `Set` y leídos con `Get`. **Persisten entre ejecuciones** del flow
   cargado: el GraphState se crea en `load` y vive hasta `unload`, y `execute`
   no las resetea (solo resetea `_output_refs` y `_exec_arrivals`,
   `executor.py:79-80`).
2. **Outputs vigentes de nodos** — el registro de último-valor-escrito de §2.4.
   Es estado *interno* de la ejecución, no algo que el autor del grafo manipule
   directamente.

La distinción importa: **las variables son la memoria persistente y explícita;
los node-outputs son el cableado de datos efímero.** Un loop como
`foreach_demo.json` acumula en una *variable* (`counter`) justamente porque los
node-outputs no sirven para acumular entre iteraciones de forma legible — se
sobrescriben.

Sobre la **concurrencia del estado**: `GraphState` no tiene locking, y su propio
docstring lo justifica diciendo que el engine es secuencial. Esto es cierto
*dentro de una ejecución*. Pero hay dos vías por las que el mismo `GraphState`
recibe actividad concurrente:

- **Ramas paralelas** (`Parallel`) entrelazadas en el event loop del engine. Dos
  ramas que hacen `Get`+`Add`+`Set` sobre la misma variable pueden intercalar
  sus lecturas y escrituras. En `showcase.json` esto se evita por construcción
  (cada rama usa su propia variable), pero nada en el modelo lo impide.
- **Eventos**: cada evento lanza `_run_event_flow` como task Ray independiente
  (`api.py:183`) sobre el **mismo flow cargado** y, por tanto, el mismo
  `GraphState`. `FlowEngine.execute` está serializado por el event loop del
  actor (dos `execute` no corren a la vez), lo que protege contra solapamiento
  entre ejecuciones completas — pero el modelo de consistencia que esto ofrece
  ("las ejecuciones se serializan, las ramas dentro de una ejecución no") no
  está declarado en ningún sitio y conviene hacerlo explícito.

El estado tiene además **scoping** vía `state_path` (§4): un subflow aislado abre
su propio segmento de claves dentro del mismo `GraphState`.

---

## 4. El modelo de composición: aplanado en build time

Rayflow permite que un flow llame a otro (`CallFlow`). La decisión conceptual
clave es **cuándo** ocurre esa composición: **en build, no en runtime**.

`flatten` (`validator.py:89`) expande recursivamente cada `CallFlow`: toma el
grafo del subflow y lo *inyecta inline* en el grafo padre, prefijando todos los
ids con la ruta del `CallFlow` (`padre/cf/nodo`). El resultado es un único grafo
plano sin ningún `CallFlow` real. Las consecuencias:

- **No hay contenedores en runtime.** Los `/` en los ids son nombres, no
  fronteras — el propio código lo compara con claves estilo S3
  (`validator.py:85`). El engine nunca "entra" ni "sale" de un subflow; recorre
  un grafo plano.
- **La frontera del subflow se reutiliza, no se inventa.** El `OnStart`/
  `FlowOutput` que el subflow ya declara se reaprovechan como puntos de empalme,
  marcados con `subflow_of` (`_splice_subflow`, `validator.py:225`). El
  `CallFlow` shell sobrevive solo como un orquestador delgado: dispara el entry
  del subgrafo (bloqueante), recoge el `FlowOutput` como `result`, y sigue su
  propio `exec_out` (`_fire_callflow_node`, `executor.py:171`).
- **El estado se hereda o se aísla, decidido en build.** Un `CallFlow` con
  `isolated=True` abre un `state_path` propio; si no, comparte el del padre
  (`validator.py:124`, `:142`). El aislamiento es un prefijo de claves, no un
  GraphState aparte.

Lo que este modelo **gana**: un único grafo plano, un único recorrido, un único
estado, sin RPC entre niveles ni gestión de ciclos de vida anidados. La
composición es "gratis" en runtime porque desaparece en build.

Lo que **excluye por construcción**:

- **Recursión.** Como `flatten` expande estáticamente y luego se valida
  aciclicidad, un flow no puede llamarse a sí mismo (directa ni indirectamente):
  la expansión no terminaría. La repetición solo existe dentro de un nodo (§2.1).
- **Despacho dinámico de subflows.** El input `flow` del `CallFlow` debe ser
  estático (un dict o una ruta); el build rechaza una referencia dinámica
  explícitamente (`validator.py:118`). No se puede "elegir qué subflow llamar"
  en tiempo de ejecución.
- **Encapsulación real.** Como todo termina en un namespace plano compartido, la
  modularidad de Rayflow es *organizativa* (de autoría y nombres), no una
  frontera de aislamiento en ejecución (salvo el scoping opcional de estado).

---

## 5. El modelo de tipos

El sistema de tipos (`types.py`) es deliberadamente minimalista y está cerrado:

- **Registro cerrado de primitivos**: `int, float, str, bool, list, dict, Any`.
  No hay tipos de usuario.
- **Genéricos limitados**: `list[T]` y `dict[str, V]` (la clave de un dict es
  siempre `str`). Nada más anidable salvo recursión de estos dos.
- **Compatibilidad nominal y estricta** (`compatible`, `types.py:109`): dos pins
  conectados deben tener el mismo tipo, o uno ser `Any`. **Sin coerción**: `int`
  y `float` son incompatibles; el casteo es explícito (nodos `ToInt`, `ToFloat`,
  …). El error de build incluso lo dice (`validator.py:508`).
- **El tipo es siempre un string canónico.** No se usan clases Python ni
  anotaciones como tipo. El string *es* la representación.

Conceptualmente esto traza una frontera clara: **el tipado existe para detectar
cableados imposibles en build, no para modelar el dominio.** Todo lo que sea más
rico que los primitivos cae en `dict` o `Any`. La validación es total y temprana
(`_validate_declared_types`, `validator.py:270`, recorre incluso la interfaz
pública), pero su poder expresivo es bajo a propósito: prioriza que un flow
escrito a mano (o por un LLM) sea verificable sobre que el tipo capture
invariantes finos.

Hay un punto de fuga interesante: los pins de los nodos de **interfaz**
(`OnStart`, `FlowOutput`, `OnEvent`) y los inputs extra de `CallFlow` se generan
*dinámicamente* en build a partir de la interfaz declarada del flow
(`_with_dynamic_pins`, `validator.py:309`). Y los inputs extra del `CallFlow`
entran como `Any` (`validator.py:347`) — es decir, la frontera de un subflow
relaja el tipado a `Any`. El tipado es estricto *dentro* de un nivel y laxo *en
la costura* entre flow y subflow.

---

## 6. La abstracción de despliegue: `@ray_node` vs `@engine_node`

Rayflow declara que estos dos decoradores comparten **el mismo contrato de
`run`** y difieren solo en *dónde* corre el nodo. Es cierto, pero conviene ver
con precisión hasta dónde llega esa equivalencia y dónde se rompe.

Qué comparten (real): el cuerpo de `run` es idéntico — `ctx.set_output(...)` +
`await ctx.fire(...)`. El autor del nodo escribe lo mismo en ambos casos.

Dónde difieren (y por qué importa conceptualmente):

1. **Dónde corre.** Un `@engine_node` se ejecuta **dentro** del `FlowEngine`
   (`_fire_engine_node`, `executor.py:202`): se instancia, corre y se descarta en
   cada disparo. Un `@ray_node` corre en un **actor remoto** persistente
   (`_fire_ray_node`, `executor.py:259`), creado en `load` y vivo hasta `unload`.

2. **Estado.** De lo anterior se sigue una diferencia semántica, no solo de
   despliegue: un `@ray_node` con exec pins **puede acumular estado en `self`**
   entre disparos e incluso entre ejecuciones (el actor persiste); un
   `@engine_node` **no**, porque se reinstancia cada vez. "Mismo contrato" es
   cierto para `run`, pero la *memoria del nodo* es una capacidad que solo tiene
   una de las dos formas.

3. **El camino de `ctx.fire` y `ctx.set_output`.** Para un `@engine_node` el
   engine inyecta atajos locales: `set_output` acumula en un buffer
   (`_pending_outputs`) y `fire` reentra directamente a `_local_fire` sin RPC
   (`executor.py:224-235`). Para un `@ray_node`, el `ExecContext` viaja
   serializado al actor y `ctx.fire` hace un RPC de vuelta al engine
   (`engine.fire.remote`, `decorators.py:140`). Funciona sin deadlock **solo
   porque** el engine es un actor async que puede atender ese RPC reentrante
   mientras espera el `run` del actor — un invariante de concurrencia no obvio
   del que depende que un `@ray_node` pueda disparar exec pins.

El buffer `_pending_outputs` merece una nota: existe porque un `@engine_node` no
puede hacer una escritura `await` al GraphState desde dentro de un método que el
propio engine está ejecutando (sería una auto-llamada bloqueante). El engine
flushea ese buffer en momentos precisos: antes de un `fire` cuyos targets vayan
a leer los outputs, y al terminar el `run` (`executor.py:228-248`). Es
infraestructura para preservar la ilusión de "mismo contrato" pese a que la
mecánica subyacente es distinta.

> La equivalencia `@ray_node`/`@engine_node` es real en la *escritura* de un
> nodo y deliberadamente falsa en su *semántica de estado y de ejecución*. Es
> una abstracción que vale para el autor del nodo, no para razonar sobre el
> sistema.

---

## 7. El modelo de servicio: ciclo de vida, eventos y observabilidad

Rayflow no trata un grafo como una invocación, sino como **algo que se despliega
y queda residente**. Tres piezas componen este carácter:

**Ciclo de vida.** `LoadedFlow.load` (`executor.py:387`) instancia, como actores
*detached*, el `FlowEngine`, el `GraphState`, la `RunQueue` y un actor por cada
`@ray_node` con exec pins. Viven hasta `unload`. "Cargar" un flow es desplegar
un pequeño sistema de actores; "ejecutar" es mandarle inputs.

**Eventos.** El `EventBroker` (`events/bus.py`) es un actor global de pub/sub con
matching **exacto por string** (con namespaces estilo S3 en el nombre, p.ej.
`ventas/order_created`). Es **fire-and-forget y sin persistencia**: si nadie
está suscrito cuando se publica, el evento se pierde (`publish`, `bus.py:44`).
Un flow residente con un `OnEvent` se convierte así en un reactor: cada evento
lanza una ejecución independiente (`_run_event_flow`). El `OnEvent` puede
coexistir con `OnStart` como segundo punto de entrada (`_find_entry`,
`validator.py:571`).

**Observabilidad como primera clase.** Cada ejecución produce un *stream* de
eventos (`run_start`, `node_start`, `edge_fire`, `node_done`, `flow_done`/
`flow_error`) empujados a una `RunQueue` por-run (`state/queue.py`) y consumidos
como SSE. La emisión de los eventos de progreso es **fire-and-forget a propósito**
(`executor.py:281-303`): el engine no espera la confirmación del push para no
bloquear su event loop; el orden FIFO lo garantiza el event loop secuencial de
la `RunQueue`. Solo los eventos terminales usan `await`, para que lleguen antes
de cerrar la sub-cola. La ejecución de Rayflow está **diseñada para ser
observada en vivo** (el editor visual la anima), no solo para producir un
resultado.

Que la observabilidad sea estructural —y no un añadido— es parte de la identidad
del sistema: un flow es algo que *se mira ejecutarse*, no solo algo que devuelve.

---

## 8. Los invariantes que sostienen el sistema

Vale la pena nombrar explícitamente los supuestos sobre los que descansa la
corrección de Rayflow, porque son implícitos en el código:

1. **Secuencialidad en profundidad del plano de ejecución.** Sin esto, la
   semántica de último-valor-escrito (§2.4) y la lectura de `ForEach.element`
   serían incorrectas. Es el invariante maestro: casi todo lo demás depende de él.
2. **Pureza de los nodos sin exec pins.** Asumida para que la re-evaluación sin
   memoización (§2.3) sea inocua. No impuesta por el sistema.
3. **El engine atiende RPC reentrantes mientras espera un `@ray_node`.** Sin esta
   propiedad de los actores async de Ray, un `@ray_node` no podría disparar exec
   pins (§6).
4. **Cada fuente exec dispara una vez (topología DAG).** Sostiene la lógica de
   *readiness* basada en sets sin guardia de "ya disparado" (§2.5).
5. **Las ejecuciones completas no se solapan** (serializadas por el actor engine),
   aunque las ramas dentro de una ejecución sí se entrelazan. Es lo que hace
   seguro el `GraphState` sin locks — a nivel de ejecución, no de rama (§3).

Hacer estos invariantes explícitos (en docs y, donde se pueda, en asserts o
validaciones) es probablemente la inversión de mayor retorno conceptual: son
verdades de las que depende todo y que hoy solo viven en la cabeza del autor.

---

## 9. Tensiones y zonas grises

Ninguna de estas es un "error": son consecuencias de decisiones de diseño que
conviene tener nombradas.

1. **"Arista de datos" es un término sobrecargado.** Significa recálculo
   (productor puro) o lectura de registro mutable (productor de ejecución). El
   mismo dibujo en el canvas tiene dos semánticas según el otro extremo. Es
   potente y es la fuente de la mayor parte de la sutileza al razonar un flow.

2. **El grafo no muestra la repetición.** Un `ForEach` itera, pero el plano de
   ejecución dibujado es acíclico. La topología visible no refleja la topología
   ejecutada. El poder de control vive en la *librería de nodos*, no en el
   lenguaje visual: un patrón de iteración nuevo es un nodo Python nuevo, no una
   composición en el grafo.

3. **Pureza sin garantía ni memoización.** Si un nodo "puro" no lo es, o si es
   caro, la re-evaluación múltiple es observable. El sistema podría o bien
   imponer pureza, o bien memoizar por ejecución, o bien documentar que la
   re-evaluación es parte del contrato. Hoy es implícito.

4. **El modelo de consistencia del estado no está declarado.** Ramas paralelas y
   eventos concurrentes comparten `GraphState`. Hay una garantía real
   (ejecuciones serializadas) pero su alcance exacto (qué se protege y qué no) no
   está escrito.

5. **La costura de tipos entre flow y subflow es `Any`.** El tipado estricto se
   relaja justo donde dos flows se conectan (§5). Es pragmático, pero es el punto
   donde un error de cableado entre niveles no se detecta en build.

6. **La abstracción de despliegue filtra en la dimensión que más importa: el
   estado.** "Mismo contrato" induce a pensar que la elección `@ray_node` /
   `@engine_node` es intercambiable, cuando determina si un nodo puede recordar
   (§6).

---

## 10. Síntesis: la identidad conceptual de Rayflow

Despojado de implementación, Rayflow es:

> **Un lenguaje visual que ejecuta un grafo plano mediante un recorrido
> secuencial en profundidad del plano de ejecución, donde disparar un exec pin
> corre la continuación entera de forma bloqueante; sobre ese recorrido, el
> plano de datos se resuelve por demanda, mezclando recálculo de nodos puros con
> lectura de un estado compartido de último-valor-escrito que el propio orden de
> ejecución mantiene coherente. Un grafo no es una invocación sino un servicio
> residente: se carga como un conjunto de actores vivos con estado persistente,
> se ejecuta muchas veces, reacciona a eventos y se observa en streaming.**

Sus apuestas más características —y lo que lo distingue— son tres:

1. **El disparo bloqueante como primitiva de control.** Que `ctx.fire` ejecute la
   continuación entera, en vez de encolarla, es lo que hace que los bucles se
   escriban como bucles del lenguaje anfitrión y que el orden de efectos sea
   trivialmente secuencial. Es una decisión simple con consecuencias profundas.

2. **La composición que desaparece en build.** Aplanar los subflows convierte la
   modularidad en un problema de nombres y elimina la composición del runtime —
   a cambio de renunciar a recursión y despacho dinámico.

3. **El grafo como servicio observable, no como script.** El ciclo
   load/execute*/unload, el estado persistente, los eventos y el streaming hacen
   que la unidad mental no sea "correr un flow" sino "tener un flow vivo".

La mayor deuda conceptual no está en ninguna de esas apuestas, sino en lo
**implícito**: los invariantes del §8 y los modelos de consistencia, pureza y
tipado-en-la-costura que hoy son convenciones tácitas. El sistema es coherente;
lo que falta es hacer explícito *por qué* lo es.

---

## 11. Mapa para profundizar

Si este análisis se quiere llevar más lejos, el orden sugerido —de lo más
estructural a lo más periférico— es:

1. **El invariante de secuencialidad (§2, §8).** Verificar que ninguna ruta
   (eventos, `Parallel`, `Map`) lo viole, y escribirlo como contrato.
2. **El modelo de consistencia del estado (§3).** Definir y documentar qué
   garantiza Rayflow ante ramas y eventos concurrentes.
3. **El contrato de pureza y la (no) memoización (§2.3).** Decidir y declarar.
4. **La costura de tipos flow/subflow (§5).** Evaluar si puede estrecharse.
5. **La equivalencia de decoradores (§6).** Documentar la diferencia de estado
   como parte del contrato, no como detalle de despliegue.

---

## 12. Divergencia entre el modelo documentado y el implementado

`docs/rayflow.md` describe un diseño anterior que **ya no coincide** con el
código en puntos centrales. Se anota aquí porque afecta a cualquiera que use ese
documento como referencia conceptual. La fuente de verdad de este análisis es el
código.

| Tema | `docs/rayflow.md` dice | El código hace |
|---|---|---|
| Contrato de `run` | El nodo *devuelve* `(exec_outputs, {pin: valor})` | El nodo *llama* `ctx.set_output(...)` + `await ctx.fire(...)` |
| Motor | Event loop sobre una **cola de triggers** | Recursión en profundidad (`_run_loop`); la pila es el recorrido |
| Fan-out exec | "Un exec output va a exactamente un exec input"; "no existe paralelismo de control" | `exec_targets` es una lista; varios destinos se lanzan con `asyncio.gather` (hay entrelazado de control) |
| Tipos de nodo | Datos = task Ray; ejecución = actor Ray | Decoradores `@ray_node` (actor/task remoto) vs `@engine_node` (dentro del engine); la distinción del doc no existe |
| Ciclo de vida de actores | Se crean al arrancar y se destruyen al terminar; no se reusan | Actores *detached* persistentes: load → execute\* → unload; el estado sobrevive entre ejecuciones |
| Composición | No se menciona | `CallFlow` + `flatten` (aplanado en build) — concepto central ausente del doc |
| Entrada | `FlowInput` con exec output `then` | `OnStart` (canónico) con `exec_out`; `FlowInput` es alias |
| Bus de eventos | Actor `rayflow_event_bus`; API `serve()` | Actor `rayflow_event_broker`; API `serve_events()` |

Recomendación: tratar `docs/rayflow.md` como un documento histórico de intención
y considerar este análisis (o una versión derivada) como la descripción
conceptual vigente.
