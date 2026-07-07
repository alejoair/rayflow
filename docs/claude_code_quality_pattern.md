# Patrón: control de calidad de documentación/contexto para repos trabajados por agentes LLM

> Este documento describe un **patrón reusable**, no la implementación
> puntual de Rayflow. Para la implementación concreta que motivó este
> documento — con nombres de archivo reales, schemas exactos y decisiones
> específicas de este repo — ver `docs/issues_system.md` y
> `rayflow_agents_system.md`. Acá se aísla deliberadamente lo que es
> transferible a cualquier otro proyecto que use Claude Code (u otro agente
> con capacidades equivalentes de subagentes, hooks y ejecución headless).

## 1. El problema

En un repo grande, trabajado por agentes LLM (y humanos), hay dos capas que
evolucionan a velocidades distintas:

- El **código**, que cambia todo el tiempo: refactors, renames, cambios de
  API, features nuevas, deprecaciones.
- El **contexto en prosa** que un agente LLM lee para entender ese código
  antes de tocarlo — un `CLAUDE.md`, un `AGENTS.md`, un README de
  arquitectura, un doc de diseño — que describe contratos, convenciones,
  invariantes.

La prosa no se actualiza sola. Un refactor puede dejar una afirmación de
documentación mintiendo — un endpoint que ya no existe, un flag que fue
reemplazado por un decorador, un campo que se eliminó de un modelo — sin que
nadie se entere hasta que un agente (o una persona) confía en esa afirmación
y falla por eso. La falla es silenciosa por diseño: nada en el flujo normal
de trabajo la fuerza a salir a la luz. Corregirla a mano, una vez que se
descubre, no resuelve el problema de fondo: no hay nada que impida que vuelva
a pasar con el próximo refactor.

Este patrón ataca ese problema convirtiendo "la documentación describe el
código con precisión" de una expectativa informal a **una propiedad que la
propia infraestructura del repo verifica activamente**, en vez de depender
de que alguien se acuerde de releer la prosa entera cada tanto.

## 2. Visión general

El patrón tiene cuatro piezas de datos/proceso y cuatro mecanismos de
enforcement que las conectan:

```
 registro de afirmaciones          cola de issues
 verificables (claims)   ────────▶ de discrepancia
        │                                │
        │ verifica                       │ escribe (solo él)
        ▼                                ▼
   subagente auditor  ──reporta a──▶ subagente escritor
   (solo lectura)        candidatos    (única escritura)
        │
        │ (opcional, issues cross-sistema)
        ▼
   subagente moderador
   (diseña, nunca implementa)

 + gate de git hooks: bloquea ediciones directas al registro de afirmaciones
 + gate de git hooks: corre el auditor scopeado al diff de cada commit
 + generación automática de contexto (regenerada en cada commit)
 + Claude Code hooks: inyectan ese contexto vivo dentro de cada sesión
 + (opcional) orquestación paralela determinística para auditorías completas
```

Ninguna pieza sola resuelve el problema. El registro de afirmaciones sin un
auditor es solo un documento más que se puede desactualizar. Un auditor sin
separación de roles con quien escribe reintroduce el mismo problema de
confianza ciega que el patrón intenta evitar. Un gate de git sin auditor no
tiene nada que hacer cumplir. La generación automática de contexto sin las
piezas anteriores es solo un mapa del código, no una verificación de que la
prosa lo describe bien.

## 3. Componentes centrales

### 3.1. Registro de afirmaciones verificables

Un archivo estructurado (JSON, YAML, lo que sea fácil de parsear
mecánicamente) que descompone la documentación en prosa en **claims
atómicos**, agrupados en secciones que reflejan la estructura del documento
fuente. Cada claim es un objeto con, como mínimo:

- Un **id estable** (ej. `<sección>#<slug>`) — lo suficientemente estable
  como para que otras piezas del sistema (la cola de issues) lo referencien
  sin que un reordenamiento del documento lo rompa.
- El **texto** de la afirmación en sí.
- La **evidencia**: rutas de archivo (+ símbolo puntual cuando conviene
  precisión, en vez de número de línea — un número de línea no sobrevive a
  una edición arriba) que sostienen esa afirmación en el código real.
  Vacío significa "no localizado todavía", nunca "falso" — esa distinción la
  hace la cola de issues, no este campo.
- Opcionalmente, referencias a **otra documentación** que restablece el
  mismo hecho de forma independiente, para saber qué más hay que revisar
  cuando ese hecho deja de ser cierto.

Es deliberadamente **verboso y granular** — muchos claims chicos en vez de
pocos grandes — porque la unidad de verificación de un auditor tiene que ser
lo bastante chica como para poder confirmarse o refutarse con una lectura de
código acotada. Un claim que mezcla cinco afirmaciones distintas en un
párrafo no se puede auditar de forma incremental: falla como bloque o pasa
como bloque.

### 3.2. Cola de issues de discrepancia

Un segundo archivo, separado del registro de afirmaciones, que acumula
**solo problemas abiertos** — no un historial de todo lo que alguna vez se
detectó y corrigió. Reglas de diseño:

- **Sin campo de "resuelto".** Resolver un issue es eliminar su entrada del
  array, en el mismo commit que aplica el fix. El historial completo (cuándo
  se creó, cuándo se resolvió, en qué commit) vive en el historial de
  control de versiones (`git log -p` / `git blame` sobre el archivo), no
  duplicado dentro de él.
- **Contador de id monótono, nunca reusado.** Aunque el array se achique,
  el próximo id sigue la secuencia — puede haber huecos en la numeración
  (un id que existió y ya se resolvió), y eso es intencional: un id
  reusado sería ambiguo en cualquier referencia externa (un commit message,
  un comentario de PR) que lo mencione por número.
- **Sin campo de "fix sugerido".** El issue describe la discrepancia
  (qué claim, qué evidencia real la contradice) sin proponer una solución.
  Quien lo resuelva no debería arrancar anclado a la primera idea que se le
  ocurrió a quien lo detectó — proponer una solución de entrada sesga
  incluso a un agente/humano que llega con más contexto o mejor criterio.
- Cada entrada enlaza los ids de claims afectados, los archivos de código
  involucrados, y la documentación en prosa a corregir — como campos
  separados, porque un issue puede afectar código sin afectar prosa (o
  viceversa: una sección de docs mal escrita desde el principio, sin que
  haya habido ningún cambio de código).

### 3.3. Subagente auditor (solo lectura)

Un subagente cuyo trabajo es recorrer un subconjunto (o la totalidad) de los
claims del registro, comparar cada uno contra el estado real del código, y
producir un reporte. Dos propiedades no negociables:

- **No tiene permiso de escritura sobre ningún archivo** — ni el registro
  de afirmaciones, ni la documentación en prosa que describe, ni siquiera
  la cola de issues. Su única salida es un reporte de candidatos.
- **Nunca decide la solución.** No genera nada equivalente a un "fix
  sugerido" en sus hallazgos, por la misma razón que la cola de issues no
  tiene ese campo: mantener separado "qué está mal" de "cómo arreglarlo".

Puede correr acotado a un scope concreto (una lista de archivos o de claim
ids — el caso típico cuando lo dispara un gate de git sobre el diff de un
commit) o sin scope, sobre el registro completo, para una auditoría manual
exhaustiva.

### 3.4. Subagente escritor (único punto de escritura)

Un segundo subagente, distinto del auditor, que es el **único** en todo el
repo con permiso de escritura sobre la cola de issues. Recibe candidatos
reportados por el auditor — o por cualquier otro agente que note
incidentalmente una discrepancia mientras hace otro trabajo — y antes de
escribir nada:

1. **Re-verifica cada candidato de forma independiente**: lee el claim real,
   lee los archivos de evidencia citados, confirma o refuta con su propia
   lectura — no transcribe ciegamente lo que le reportaron.
2. **Dedupea** contra el estado real de la cola de issues (no contra lo que
   asuma quien reportó que ya está abierto) y, si le llega un lote de varios
   candidatos a la vez, también entre sí.
3. Recién ahí hace la escritura — preferentemente **una única escritura
   atómica** por corrida, incluso si consolida hallazgos de varias fuentes.

Esta separación de roles — quien **verifica** nunca es quien **escribe**, y
quien **escribe** nunca confía ciegamente en lo que le reportan — es la
pieza de diseño más importante de todo el patrón. Ver §4 para el porqué.

### 3.5. Subagente moderador (opcional, para issues cross-sistema)

En un repo dividido en varios subsistemas/dominios, un issue puede involucrar
a más de uno a la vez. Un subagente moderador opcional, invocado con un id de
issue puntual:

- Identifica qué subsistemas están involucrados y convoca al especialista
  (humano o subagente) de cada uno.
- Si hay uno solo, le pide directamente una propuesta de fix.
- Si hay varios, les pide propuestas independientes primero (sin mostrarles
  las propuestas ajenas, para no sesgarlos de entrada), y después modera una
  o más rondas de intercambio de objeciones hasta que converjan — con un
  tope de rondas para no loopear buscando un consenso perfecto que puede no
  llegar nunca. Si no convergen dentro del tope, decide él mismo, dejando
  **explícito** en el plan final qué no coincidió y por qué se resolvió como
  se resolvió (nunca ocultando el desacuerdo detrás de una propuesta única
  como si hubiera habido consenso).
- Devuelve un **plan de solución en texto**, nunca lo implementa ni lo
  persiste en ningún archivo — ni siquiera agrega el fix sugerido a la cola
  de issues, por la misma razón de §3.2. La implementación, si se pide, es
  un paso posterior explícito y opt-in, no algo que el moderador haga por
  iniciativa propia.

### 3.6. Gates a nivel de git hooks

Dos gates distintos, cada uno resolviendo un problema distinto — ninguno
reemplaza al otro:

**Gate 1 — bloqueo de edición directa del registro de afirmaciones.** El
objetivo es que el registro nunca se edite como un acto aislado,
desconectado del cambio de código que lo motiva — forzar que toda edición
viaje en el mismo commit que también toca el código relacionado (o, como
mínimo, que declare explícitamente por qué se edita). La forma más simple de
hacer cumplir esto es a nivel de gate de commit (ej. exigir un trailer
específico en el mensaje de commit cuando el diff toca ese archivo, y
rechazar el commit si falta) — un gate que corre sobre el estado real de
git, sin importar con qué herramienta se hizo la edición.

**Gate 2 — auditor scopeado al diff de cada commit.** Antes de aceptar un
commit, calcula qué claims del registro tienen evidencia dentro de los
archivos que ese commit modifica, y si hay alguno, corre el auditor
acotado a ese scope. Si el auditor (a través del escritor) confirma una
divergencia real, bloquea el commit.

## 4. Por qué cada pieza de diseño es como es

Esta sección es el contenido más valioso del documento — no la lista de
componentes en sí, sino las decisiones no triviales detrás de cada uno.

**Por qué separar verificar de escribir.** Un solo agente que audita Y
escribe reintroduce exactamente el problema que el patrón intenta resolver:
confiar ciegamente en una sola pasada de razonamiento. Un LLM puede
alucinar una contradicción que no existe, malinterpretar código ambiguo, o
tener un momento de sobre-confianza. Separar los roles no elimina ese riesgo
— un segundo LLM también puede equivocarse — pero lo **reduce**, porque el
escritor no hereda ciegamente la conclusión del auditor: repite el trabajo
de verificación desde cero, con su propia lectura del código. Es el mismo
principio que motiva un segundo par de ojos en una revisión de código
humana, aplicado a dos agentes en vez de dos personas. Además, tener un
único punto de escritura (en vez de que cada agente que detecta algo edite
directamente) evita que la lógica de deduplicación/formato/verificación se
disperse y diverja entre N implementaciones distintas de "cómo reportar un
hallazgo".

**Por qué el auditor no tiene permiso de escritura, ni siquiera sobre la
cola de issues.** No es solo una convención documentada: si el subagente en
sí no tiene el permiso técnico de editar ningún archivo, ninguna instrucción
en su prompt (adversarial o no) puede hacer que efectivamente escriba algo.
Es separación de privilegios real, no solo un acuerdo de buena fe — la
misma razón por la que, en cualquier sistema con roles, "solo se le pide
amablemente que no haga X" es más débil que "no tiene el permiso técnico de
hacer X".

**Por qué fail-open ante problemas de infraestructura, pero fail-closed
cuando el auditor efectivamente escribió algo.** Si el binario/servicio que
corre al agente no está disponible, si hace timeout, o si falla por una
razón de infraestructura ajena al contenido auditado, bloquear el commit
sería peor que el problema que este mecanismo intenta resolver: convertiría
una falla de red o de instalación en un bloqueo total del repo para
cualquiera. La única señal que sí debe bloquear es "el auditor (vía el
escritor) efectivamente escribió una entrada nueva en la cola de issues" —
eso, y solo eso, implica que hay una divergencia real confirmada que alguien
tiene que revisar antes de que el commit entre. Fijar la señal de bloqueo en
"el auditor escribió algo" en vez de "el auditor dijo algo en su texto
libre de respuesta" importa: el texto libre de un LLM puede sonar alarmante
sin que haya pasado la verificación real (la del escritor); un archivo que
efectivamente cambió es una señal binaria y verificable con una simple
comparación de estado antes/después, no una interpretación de prosa.

**Por qué no hay campo de "resuelto" en la cola de issues.** Agregar
metadata de resolución (cuándo, quién, en qué commit) generaría dos fuentes
de verdad para la misma información: el archivo y el propio historial de
control de versiones. El historial de git ya es un log completo, ordenado
cronológicamente y a prueba de ediciones manuales inconsistentes — duplicar
eso dentro del archivo no agrega nada, solo un lugar más donde puede
desincronizarse.

**Por qué no hay campo de "fix sugerido".** El motivo no es evitar trabajo
extra: es evitar **sesgar** a quien resuelva el issue. Una sugerencia
escrita por quien detectó el problema (a menudo con menos contexto que quien
finalmente lo arregla) tiende a anclar la solución real incluso cuando es
subóptima, simplemente por estar ahí primero. Mantener el issue descriptivo
("qué está mal, con qué evidencia") en vez de prescriptivo ("cómo
arreglarlo") preserva el criterio de quien lo resuelve.

**Por qué el registro de afirmaciones no se fusiona con un mapa mecánico
del código (archivo→descripción, dependencias) que probablemente ya exista
en el repo.** Tienen cadencias de escritura muy distintas (el mapa mecánico
cambia con casi cualquier edición de archivo; el registro de afirmaciones
solo cuando la documentación de arquitectura cambia de verdad) y relaciones
de naturaleza distinta (las dependencias entre archivos se derivan
mecánicamente de imports reales, sin entender nada del dominio; la relación
claim→evidencia es semántica y requiere lectura humana o de un LLM).
Fusionarlos amplifica ruido en el más chico y complica regenerar o confiar
ciegamente en cualquiera de los dos.

**Por qué la generación de contexto (mapas de archivos, subagentes
especializados, documentación derivada) se regenera en cada commit en vez
de mantenerse a mano.** Cualquier mapeo mantenido a mano de "qué archivo
pertenece a qué área" o "qué sabe cada especialista" es, en sí mismo, un
documento más sujeto a desactualizarse silenciosamente — exactamente el
problema de fondo de la sección 1, aplicado recursivamente al propio sistema
de calidad. Generarlo con un script determinístico que lee el estado real
del repo en cada commit elimina esa categoría entera de staleness: no hay
nada que "olvidar actualizar" porque no se edita a mano nunca.

**Por qué un mecanismo de orquestación paralela para auditorías completas
(no scopeadas a un diff).** Auditar el registro completo con una sola pasada
secuencial de un agente puede ser lento y, si el registro es grande, tienta
a que una sola perspectiva de auditoría decida sola qué está bien o mal en
todo el documento raíz que todo agente termina leyendo — sesgando en
silencio el contexto compartido de todo el sistema. Correr varias instancias
independientes en paralelo, cada una sobre un grupo distinto de secciones, y
consolidar con una única instancia final del subagente escritor (nunca del
auditor: la escritura tiene que seguir concentrada en un solo punto incluso
en modo paralelo, para evitar condiciones de carrera sobre el mismo archivo)
es una salvaguarda barata contra ambos problemas a la vez.

## 5. Mapeo a primitivas concretas de Claude Code

- **Subagentes con `tools:` restringido en su frontmatter** son el
  mecanismo real de separación de privilegios: el auditor declara
  únicamente tools de lectura/búsqueda/delegación (nunca `Edit`/`Write`); el
  escritor es el único con `Edit` habilitado, y solo tiene sentido que lo
  use sobre la cola de issues; el moderador, igual que el auditor, no tiene
  `Edit`. Esto no es una convención de prompt — es una restricción que el
  propio harness aplica antes de que el modelo pueda invocar la tool.
- **Un framework de git hooks (ej. `pre-commit`)** implementa los dos gates
  de la sección 3.6: un hook en el stage de mensaje de commit para el
  bloqueo de edición directa (exigir un trailer si el registro está en el
  diff), y un hook en el stage normal de pre-commit para correr el auditor
  scopeado y bloquear si escribió algo. Estos son gates de **git**, no de
  Claude Code — corren para cualquier commit sin importar qué herramienta
  se usó para producirlo (un editor, un LLM, la terminal a mano).
- **Hooks de Claude Code** (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`,
  `SessionStart`, `Stop`, según el evento que corresponda) son el mecanismo
  complementario para inyectar contexto **dentro de una sesión activa**, no
  a nivel de commit: recordatorios de que un archivo tocado tiene contexto
  relacionado que podría estar desactualizado, diagnósticos de tipos/símbolos
  en vivo tras cada edición, o checklists de flujo de trabajo cuando el
  prompt del usuario matchea un patrón conocido (ej. "agregar un tipo de
  nodo nuevo"). Mismo objetivo de calidad que los git hooks, mecanismo
  distinto: estos corren en el ciclo de vida de la conversación, no en el de
  un commit.
- **Un mecanismo de orquestación determinística de múltiples agentes en
  paralelo** (en Claude Code, el tool `Workflow`, que no tiene acceso a
  filesystem por diseño — cualquier partición de trabajo tiene que
  calcularse de antemano o delegarse a los propios agentes que sí leen
  archivos) es la primitiva para el fan-out de la sección 4 (auditorías
  completas): varias instancias del auditor en paralelo, una fase de
  consolidación con una única instancia del escritor al final.

## 6. Límites y trade-offs honestos

Este patrón no es una bala de plata. Trade-offs reales, sin vender:

- **Costo de API real.** Correr un agente LLM en cada commit relevante
  (aunque sea gratis cuando el diff no toca nada auditable) tiene un costo
  de latencia y de tokens que escala con la frecuencia de commits y el
  tamaño del registro de afirmaciones. En un repo con mucha actividad, esto
  no es gratis ni instantáneo — el diseño fail-open/scopeado mitiga el
  costo, no lo elimina.
- **La separación auditor/escritor reduce falsos positivos, no los
  elimina.** Dos LLMs pueden coincidir en una conclusión equivocada,
  especialmente si el código es genuinamente ambiguo o el claim está mal
  redactado desde el origen. Esta separación es una mitigación, no una
  garantía formal.
- **El sistema solo audita lo que está declarado.** Un claim que nunca se
  escribió en el registro de afirmaciones nunca va a ser auditado, aunque el
  código relacionado cambie por completo. Esto requiere disciplina activa:
  cuando se agrega documentación de arquitectura nueva, alguien tiene que
  acordarse de descomponerla en claims nuevos con su evidencia — el patrón
  no genera claims solo, y si esa disciplina se abandona, el registro se
  queda fosilizado mientras la documentación en prosa (que sí puede seguir
  editándose libremente) se aleja de lo que el registro cree que dice.
- **El registro mismo puede quedar desactualizado respecto a la
  documentación que lo generó**, si esta última se edita sin pasar el nuevo
  contenido por el mismo proceso de descomposición en claims — el gate de
  edición directa (sección 3.6) frena ediciones casuales del registro, pero
  no fuerza que la prosa fuente y el registro se mantengan sincronizados
  entre sí en ambas direcciones.
- **Ambigüedad de scope.** El scoping por diff (qué claims tienen evidencia
  en los archivos tocados) es mecánico y, por lo tanto, no exhaustivo: un
  claim con evidencia vacía o desactualizada puede no aparecer en el scope
  de un commit que en realidad lo invalida. Mitigarlo depende de que el
  propio auditor busque activamente más allá del filtro mecánico, lo cual
  vuelve a depender del buen juicio de un LLM, no de una garantía mecánica.
- **Complejidad de mantenimiento del propio sistema de calidad.** Cada
  pieza nueva (el registro, la cola, dos subagentes, dos gates, generación
  automática de contexto, hooks de sesión, orquestación paralela) es
  infraestructura adicional que alguien tiene que entender, depurar y
  mantener — un costo de complejidad real que solo se justifica si el repo
  es lo bastante grande y lo bastante trabajado por agentes como para que
  el problema de la sección 1 sea recurrente, no anecdótico.
- **No reemplaza revisión humana.** El patrón reduce la tasa de
  documentación silenciosamente desactualizada; no elimina la necesidad de
  que un humano revise periódicamente decisiones de diseño de alto impacto,
  ni de que alguien evalúe si el registro de afirmaciones sigue capturando
  lo que realmente importa a medida que el repo crece.
