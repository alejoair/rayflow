# Propuesta: agentes especialistas por sistema

> Documento de diseño para ejecutar en una sesión nueva. Es autocontenido: no
> asume contexto de la conversación donde se originó. Describe la idea tal
> como se planteó, la opinión/recomendación que se discutió sobre el
> mecanismo concreto, y qué queda pendiente de decidir.

## 1. La idea

`rayflow_file_map.json` ya agrupa los 148 archivos del repo en 20 **sistemas**
(`engine`, `nodes`, `schema`, `frontend-canvas`, etc.), cada uno con su lista
de archivos y sus `depends_on_systems`/`dependents_systems`. Cuando aparece un
issue (vía el sistema descripto en `docs/issues_system.md`) que involucra al
`engine`, no tiene sentido que lo agarre un agente genérico o "el ingeniero de
frontend" — la propuesta es rutear ese trabajo a un **agente especialista en
ese sistema**, generado programáticamente como archivo `.md` en
`.claude/agents/`, de la misma forma en que Claude Code ya descubre
subagentes de proyecto.

La pregunta abierta al plantear la idea era **qué va adentro de ese `.md`**:
¿el contenido completo de los archivos del sistema (para evitar tool calls de
lectura), o algo más liviano?

## 2. Por qué NO embeber el contenido de los archivos

Se discutió y se descartó embeber snapshots de código fuente dentro del
`.md` del agente, por dos razones:

1. **Es el mismo problema de staleness que motivó todo el sistema SOT +
   issues** (`docs/issues_system.md`), pero en una superficie peor: un
   snapshot de código copiado en un system prompt queda mintiendo con máxima
   confianza en cuanto alguien vuelve a tocar el archivo original — y como es
   "el especialista", va a hablar con MÁS autoridad sobre contenido
   potencialmente viejo, no con menos. Requeriría su propio mecanismo de
   invalidación/regeneración, un cuarto sistema paralelo de "mantené esto
   actualizado" además del file map y el SOT.
2. **El ahorro que se buscaba (evitar tool calls) no es donde está el costo
   real.** Leer 2-3 archivos con `Read` al arrancar un agente es marginal
   comparado con los tokens de razonamiento de la tarea en sí. No compensa
   el riesgo de correctitud.

## 3. Alternativa recomendada: apuntar a fuentes vivas, no snapshotear

El `.md` de cada especialista **no lleva contenido embebido** — lleva
instrucciones de dónde mirar, apuntando a lo que ya existe y se mantiene
actualizado por separado:

- `rayflow_file_map.json` → qué archivos pertenecen a su sistema, de qué
  sistemas depende, quién depende de él.
- `RAYFLOW_SOURCE_OF_TRUTH.json` → qué afirma `CLAUDE.md` sobre ese sistema
  (una vez migrado al schema v2 con `evidence` por claim).
- `rayflow_issues.json` → issues abiertos que ya lo mencionan en `files`/
  `claim_ids`.

El agente lee estas fuentes con sus propios tools al arrancar, igual que
cualquier agente hoy. Esto es exactamente el patrón que ya existe a mano en
`rayflow/claude_tools/agents/rayflow-debugger.md`: frontmatter con `name`/
`description`/`tools`/`model`, y un cuerpo que define **rol + método**, cero
contenido de código pegado. El sistema nuevo generaría ese mismo tipo de
archivo, pero de forma programática y apuntando al sistema correspondiente en
vez de a un flujo de debugging genérico.

### Plantilla de referencia (forma, no contenido final)

```markdown
---
name: rayflow-engine-specialist
description: Especialista en el sistema "engine" de rayflow (FlowEngine, LoadedFlow, RunContext). Usar para issues/tareas cuyo rayflow_issues.json o file map los marca como pertenecientes a este sistema.
tools: Read, Grep, Glob, Edit
model: inherit
---

Sos el especialista del sistema `engine` de rayflow. Antes de responder
cualquier pregunta o encarar cualquier tarea:

1. Leé la entrada `systems.engine` de `rayflow_file_map.json` — tus archivos,
   tus dependencias, quién depende de vos.
2. Buscá en `RAYFLOW_SOURCE_OF_TRUTH.json` los claims cuya evidencia apunta a
   tus archivos.
3. Buscá en `rayflow_issues.json` los issues abiertos que te mencionan.

No asumas que conocés el contenido de tus archivos de memoria — leélos con
tus propios tools, siempre, porque pueden haber cambiado desde la última vez
que este archivo se regeneró.

## Frontera del sistema

Si una tarea requiere tocar un archivo fuera de `systems.engine.files`,
señalalo explícitamente en vez de hacerlo en silencio — puede ser trabajo de
otro especialista.
```

## 4. Distinción importante: tooling propio vs. producto para el usuario final

`rayflow/claude_tools/agents/rayflow-debugger.md` se **instala en proyectos
de terceros** vía `rayflow install claude-tools` — es un producto para
alguien construyendo sus propios flows con `rayflow`, sin acceso ni interés
en el código fuente de `rayflow` mismo.

Los especialistas por sistema son **tooling de desarrollo de este repo**:
sirven para trabajar en `rayflow` mismo (el engine, el schema, el frontend
del editor, etc.). Van en `.claude/agents/` en la raíz del repo — no se
publican, no viajan con `pip install rayflow`. Mezclarlos con
`rayflow/claude_tools/` sería un error de empaquetado: un usuario final
nunca necesita un "especialista en el engine de rayflow", porque no toca ese
código.

## 5. No generar un agente por sistema automáticamente

Hay 20 sistemas; varios son triviales (`events`: 2 archivos, `build`: 2
archivos, `state`: 3 archivos). Generar 20 especialistas casi idénticos
satura `.claude/agents/` y hace más difícil elegir el correcto. Falta
definir el criterio de curación — candidatos a considerar:

- Cantidad de archivos del sistema (umbral a definir).
- Complejidad/tamaño acumulado (¿bytes de código, no solo cantidad de
  archivos? `engine` tiene solo 2 archivos pero uno de ellos,
  `executor.py`, es de los más grandes y complejos del repo).
- Frecuencia histórica de cambios/bugs en ese sistema (¿derivable de `git
  log` por archivo?).

Sistemas con muy pocos archivos podrían resolverse con un agente genérico
que lea el file map on-demand, sin necesitar persona dedicada.

## 6. Cuándo (re)generar los archivos de agente

No se decidió el trigger concreto. La opción que mejor encaja con lo ya
construido: regenerar (o revisar) los `.md` de especialistas cuando cambia la
**forma** del objeto `systems` en `rayflow_file_map.json` (se agrega/quita un
sistema, se mueven archivos entre sistemas) — no en cada commit. Como el
`.md` no contiene snapshots de código, su contenido es barato de mantener
correcto: solo son metadatos de rutéo (qué sistema, qué archivos pertenecen,
qué otras fuentes consultar), no un espejo del código en sí.

Esto podría integrarse al mismo pipeline de pre-commit que se está diseñando
en `docs/issues_system.md`, como un paso más — pendiente de decidir si va
ahí mismo o es un script separado con su propio trigger.

## 7. Delegación desde la sesión principal

El agente principal de una sesión ya puede delegar a un especialista con el
`Agent`/`Task` tool (`subagent_type`), pasándole la tarea y confiando en que
el especialista se orienta solo con las fuentes vivas del §3. Nada nuevo
requerido acá más allá de tener los `.md` generados y bien descriptos (el
campo `description` del frontmatter es lo que permite al agente principal
elegir el especialista correcto).

## 8. "Meets" entre agentes — visión a futuro, no diseño todavía

La idea de reuniones entre agentes especialistas (tipo videollamada, para
discutir un issue o una feature nueva, replicando una dinámica de equipo de
ingeniería real) es interesante pero mucho más ambiciosa que lo anterior:
requiere orquestar diálogo entre N agentes, con algún mecanismo de turnos o
moderación, y el costo (en llamadas y en tokens) crece con N × rondas de
discusión, sin que el valor agregado sobre una consulta secuencial esté
todavía demostrado para la escala de este repo.

Hay un escalón intermedio, mucho más barato, que ya es alcanzable hoy sin
diseño nuevo: el `Agent` tool permite retomar una conversación con un
especialista ya creado (pasándole su id/nombre), así que el agente principal
puede **consultar secuencialmente** a varios especialistas — pasándole a
cada uno lo que dijo el anterior — sin necesitar una arquitectura de
"reunión" simultánea. Esto cubre buena parte del valor (síntesis de
conocimiento cruzado entre sistemas) sin la complejidad de orquestación.

Se deja explícitamente fuera del alcance inmediato. Cuando se retome, vale la
pena mirar patrones existentes de "council of agents" / debate multi-agente
antes de diseñar desde cero.

## 9. Pendientes

- [ ] Definir el criterio de curación de qué sistemas ameritan agente propio
      (§5).
- [ ] Escribir el script que genera/actualiza los `.md` en `.claude/agents/`
      a partir de `rayflow_file_map.json.systems` (formato de referencia en
      §3, sin contenido embebido).
- [ ] Decidir el trigger de regeneración (§6) — ¿parte del mismo pre-commit
      de `docs/issues_system.md`, o script aparte con su propio disparador?
- [ ] Decidir el nivel de acceso a tools de cada especialista (¿todos con
      `Read, Grep, Glob, Edit` como en la plantilla, o varía según el
      sistema — por ejemplo, sistemas más sensibles con menos permisos, al
      estilo `rayflow-debugger.md` siendo deliberadamente read-only?).
- [ ] Prototipar un primer especialista (candidato natural: `engine`, dado
      que ya se identificó como ejemplo motivador) y probarlo contra un
      issue real de `rayflow_issues.json`.
- [ ] Retomar el diseño de "meets" (§8) una vez que la delegación secuencial
      esté probada y se vea si hace falta algo más.
