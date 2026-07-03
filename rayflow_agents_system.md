# Propuesta: agentes especialistas por sistema

> Documento de diseño para ejecutar en una sesión nueva. Es autocontenido: no
> asume contexto de la conversación donde se originó. Describe la idea tal
> como se planteó, la opinión/recomendación que se discutió sobre el
> mecanismo concreto, y qué queda pendiente de decidir.

> **Actualización — implementado, revirtiendo la recomendación de §2/§3.**
> Los agentes especialistas están generados: `scripts/generate_specialist_agents.py`
> produce un `.claude/agents/rayflow-<system>-specialist.md` por cada uno de
> los 21 sistemas de `rayflow_file_map.json`, wireado como hook
> `agents-generate` en `.pre-commit-config.yaml` (stage `pre-commit`, mismo
> mecanismo que `claude-md-generate` — ver `docs/claude_md_generation.md`).
>
> La diferencia con lo que proponían §2/§3 originalmente: **sí llevan
> contenido embebido** (descripciones de archivos, dependencias entre
> sistemas, los claims de la SOT cuya evidencia cae en ese sistema —texto +
> evidencia, no solo el id—, e issues abiertos que lo mencionan), no solo
> punteros a "andá a leer tal archivo". La razón para revertir: el riesgo
> que motivaba §2 (un snapshot de código pegado a mano queda mintiendo en
> cuanto alguien toca el original) se neutraliza por completo si el
> contenido se regenera y re-stagea en cada commit — exactamente el mismo
> argumento que ya se aplicó a `CLAUDE.md`. No hace falta elegir entre
> "contenido rico" y "nunca stale": regenerar automáticamente da las dos
> cosas. La preocupación de §2.2 ("no compensa el riesgo de correctitud")
> ya no aplica porque no hay snapshot manual, hay una función pura de
> `rayflow_file_map.json` + `RAYFLOW_SOURCE_OF_TRUTH.json` +
> `rayflow_issues.json` corriendo en cada commit.
>
> El criterio de curación de §5 quedó resuelto por omisión: se genera un
> especialista por **cada** sistema, sin selección manual — es la opción
> más mecánica (nada que decidir a mano) y, como el contenido de la SOT no
> es proporcional a la cantidad de archivos de un sistema (`events` tiene 2
> archivos pero 17 claims relevantes en la SOT), un sistema "chico" en
> archivos igual puede tener un especialista con contenido sustancial.
>
> Ver el detalle completo de la implementación en §9bis, al final de este
> documento — el resto del documento (§1 a §9) se deja tal cual quedó
> planteado originalmente, como registro de la discusión.

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

- [x] Definir el criterio de curación de qué sistemas ameritan agente propio
      (§5) — decisión: sin curación, un especialista por cada sistema de
      `rayflow_file_map.json.systems` (21 al momento de implementar). Ver
      §9bis.
- [x] Escribir el script que genera/actualiza los `.md` en `.claude/agents/`
      a partir de `rayflow_file_map.json.systems` — `scripts/
      generate_specialist_agents.py`. A diferencia de §3, **sí lleva
      contenido embebido** (ver nota al principio del documento y §9bis).
- [x] Decidir el trigger de regeneración (§6) — hook de `pre-commit` propio
      (`agents-generate`), mismo mecanismo que `claude-md-generate` de
      `docs/claude_md_generation.md`, no el pre-commit del auditor de
      `docs/issues_system.md` (ese es un mecanismo distinto: bloqueante,
      basado en LLM, scopeado al diff — este es determinístico y siempre
      regenera todo).
- [ ] Decidir el nivel de acceso a tools de cada especialista (¿todos con
      `Read, Grep, Glob, Edit` como en la plantilla, o varía según el
      sistema — por ejemplo, sistemas más sensibles con menos permisos, al
      estilo `rayflow-debugger.md` siendo deliberadamente read-only?). Por
      ahora los 21 generados usan el mismo default uniforme (`Read, Grep,
      Glob, Edit`) — sigue abierto.
- [x] Prototipar un primer especialista (candidato natural: `engine`, dado
      que ya se identificó como ejemplo motivador) — hecho, junto con los
      otros 20 (no se prototipó uno solo porque el generador no distingue
      entre sistemas). Falta probarlo contra un issue real de
      `rayflow_issues.json` — ninguno de los issues abiertos hoy referencia
      todavía a un sistema con evidencia suficiente para un caso de prueba
      significativo.
- [ ] Retomar el diseño de "meets" (§8) una vez que la delegación secuencial
      esté probada y se vea si hace falta algo más.

## 9bis. Implementación (generación con contenido embebido)

`scripts/generate_specialist_agents.py` — determinístico, sin LLM, sin red,
mismo espíritu que `scripts/generate_claude_md.py`
(`docs/claude_md_generation.md`). Por cada sistema en
`rayflow_file_map.json.systems` genera
`.claude/agents/rayflow-<system>-specialist.md` con:

- Frontmatter (`name`, `description`, `tools: Read, Grep, Glob, Edit`,
  `model: inherit`) — el `description` va serializado con `json.dumps()`
  (no como escalar YAML plano) porque las descripciones de sistema del
  file map habitualmente contienen `:`, que rompería el parseo de YAML si
  se escribiera sin comillas.
- La descripción del sistema (`systems.<system>.description`).
- Tabla de archivos del sistema con su descripción individual
  (`files.<path>.description`) — con `|` y saltos de línea escapados, por
  la misma razón que el frontmatter: son tablas Markdown reales, no texto
  libre.
- `depends_on_systems`/`dependents_systems` del sistema.
- Los claims de `RAYFLOW_SOURCE_OF_TRUTH.json` cuya `evidence` cae en
  algún archivo del sistema (reutilizando
  `_sot_scope.affected_claims()`, la misma función que scopea al agente
  auditor a un diff — acá se le pasa la lista completa de archivos del
  sistema en vez de un diff), agrupados por sección de la SOT, mostrando
  texto completo + evidencia (no solo el id del claim).
- Issues abiertos de `rayflow_issues.json` cuyo `files` o `claim_ids` se
  cruza con el sistema.

Wireado como hook `agents-generate` en `.pre-commit-config.yaml`, stage
`pre-commit`: en cada commit regenera los 21 archivos, compara contra lo
que hay en disco, y solo sobreescribe + `git add` los que cambiaron. Nunca
bloquea. Corre después de `claude-md-generate` en el mismo stage — si un
commit cambia `rayflow_file_map.json` (p.ej. agrega un archivo a un
sistema), ambos generadores necesitan correr para converger: se probó
corriendo los dos en un loop hasta un punto fijo (3 pasadas, sin más
cambios en la segunda) antes de wirearlos, para confirmar que no quedan
oscilando entre sí — no debería pasar en uso normal porque `pre-commit`
corre cada hook una sola vez por commit, pero valía la pena confirmarlo
antes de asumirlo.

**Bug real encontrado y corregido durante la implementación**: la primera
versión escribía el `description` del frontmatter como escalar YAML plano
(`description: texto con : en el medio`) — cualquier descripción de
sistema con `:` (la mayoría) rompía el parseo YAML del frontmatter
completo. Se corrigió serializando con `json.dumps()` (subconjunto válido
de YAML de comillas dobles). Se encontró y corrigió también un caso
análogo en las tablas de archivos: descripciones con `|` literal rompían
las filas de la tabla Markdown — se agregó escape de `|` y de saltos de
línea. Validado corriendo `yaml.safe_load()` sobre el frontmatter de los
21 archivos generados después del fix.
