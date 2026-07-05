# Propuesta: sistema de auditoría de documentación (SOT + issues)

> Documento de diseño para ejecutar en una sesión nueva. Es autocontenido: no
> asume contexto de la conversación donde se originó. Describe el problema, las
> piezas acordadas, sus schemas, y qué falta diseñar/implementar todavía.

## 1. Contexto y problema

`CLAUDE.md` es la guía de arquitectura que un agente LLM lee para trabajar en
este repo. Como toda documentación en prosa, se desactualiza silenciosamente
cuando el código cambia y nadie vuelve a leer la línea exacta que quedó
obsoleta. En una sola sesión de auditoría manual sobre este mismo repo ya
aparecieron varios casos reales:

- La sección "Nodos de entrada" describía `is_entry = True` como atributo de
  clase y un flag `exposes_flow_inputs`, ambos reemplazados hace tiempo por el
  decorador `@entry_node`.
- El sistema `schema` (`rayflow_file_map.json`) y un workflow afirmaban que
  `FlowDef`/`NodeDef` eran modelos **Pydantic** — son `@dataclass` de la
  stdlib; `pydantic` ni siquiera es dependencia del proyecto.
- Dos archivos de test describían `POST /flows/{name}/run` con "auto-load on
  demand" para flows del editor — ese comportamiento fue removido
  deliberadamente (`404` si el flow no está servido explícitamente) y los
  tests ya lo confirmaban, pero la descripción no se había actualizado.
- `FlowSettingsDialog.tsx` seguía descripto como editor de "inputs/outputs del
  flow" después de que el campo `inputs` a nivel de flow fue eliminado del
  backend — la sección de UI del propio `CLAUDE.md` no se tocó en ese refactor.

Corregir esto a mano, una vez, no resuelve el problema de fondo: no hay nada
que impida que vuelva a pasar. El objetivo de este sistema es que **la
propia infraestructura del repo garantice** que las afirmaciones de
`CLAUDE.md` se sigan verificando contra el código real, en vez de depender de
que alguien se acuerde de releerlo.

## 2. Piezas del sistema

| Pieza | Rol | Estado |
|---|---|---|
| `RAYFLOW_SOURCE_OF_TRUTH.json` | Cada afirmación de `CLAUDE.md`, estructurada, con evidencia de dónde se sostiene en el código. | **Hecho.** Schema v2 aplicado a los 215 claims (ver §4). |
| `rayflow_issues.json` | Cola de discrepancias abiertas entre una afirmación y la realidad del repo. | **Hecho.** Archivo creado en la raíz, con `ISSUE-0001` (el caso de `FlowSettingsDialog.tsx`, ver §5). |
| `rayflow_file_map.json` | Ya existente, sin cambios de rol: mapa mecánico archivo→{descripción, depends_on, dependents}. | Sin cambios — ver §3 por qué no se fusiona con lo anterior. |
| Agente auditor | Recorre cada claim del SOT (o el subset que le pasen de scope) y valida contra el repo. Ya no escribe `rayflow_issues.json` él mismo — delega cada hallazgo confirmado a `rayflow-issue-writer` (ver fila siguiente y §6.4), salvo cuando corre como parte de un fan-out paralelo, en cuyo caso solo devuelve una estructura de datos. | **Hecho y confirmado.** `.claude/agents/rayflow-auditor.md` + helper `.claude/hooks/_sot_scope.py` (scopea por diff). Invocación real vía `claude -p --agent rayflow-auditor "..."` probada end-to-end (ver §6.1) — funciona, detecta el claim de evidencia vacía por búsqueda activa, reconoce `ISSUE-0001` y no duplica. Ya no tiene `Edit` en su frontmatter (refactor posterior, ver §6.4). |
| Agente `rayflow-issue-writer` | Único agente del repo con permiso para escribir en `rayflow_issues.json`. Recibe candidatos reportados por cualquier otro agente (el auditor, un `rayflow-<sistema>-specialist`, `rayflow-router`, etc.), los re-verifica de forma independiente, dedupea contra el estado real y entre sí, y hace la escritura atómica. | **Hecho.** `.claude/agents/rayflow-issue-writer.md` — ver §6.4. |
| Hook pre-commit | Dispara el agente auditor antes de cada commit; usa `claude -p` en modo headless. | **Hecho.** `scripts/run_sot_audit.py`, stage `pre-commit` de `.pre-commit-config.yaml` — sin scope, exit inmediato sin costo de LLM; con scope, corre el auditor (que a su vez delega a `rayflow-issue-writer` dentro de la misma invocación de `claude -p`) y bloquea el commit (exit 1) solo si `rayflow_issues.json` cambió (ver §6.2). Validado end-to-end. |
| Bloqueo de edición directa | Impide que `RAYFLOW_SOURCE_OF_TRUTH.json` se edite casualmente, para "garantizar" (mayúsculas del nombre del archivo) que nunca quede desactualizado por accidente. | **Hecho.** Dos capas: `.claude/hooks/sot_guard.py` (PreToolUse, rápida) + `scripts/check_sot_commit_message.py` (commit-msg, la garantía real) — ver §6.3. Validado end-to-end. |

## 3. Por qué tres archivos separados, no uno fusionado

Se evaluó explícitamente fusionar `rayflow_file_map.json` +
`RAYFLOW_SOURCE_OF_TRUTH.json` (+ `rayflow_issues.json`) en un solo documento.
Se descartó por tres razones:

1. **Cadencia de escritura distinta.** `rayflow_file_map.json` cambia en casi
   cada edit (lo dispara `stale_reminder.py` en el hook `Stop`). El SOT
   cambia solo cuando `CLAUDE.md` cambia de verdad — mucho más raro.
   Fusionarlos amplifica el ruido: cada edición chica de un archivo obligaría
   a tocar (o al menos revisar) un documento mucho más grande.
2. **La relación no es la misma.** `depends_on`/`dependents` del file map se
   derivan **mecánicamente** de imports reales (se puede verificar con un
   parser AST, sin entender nada del dominio). La relación claim→evidencia es
   **semántica**: saber que tal función prueba tal afirmación requiere leer y
   entender el código, no hay forma de derivarlo automáticamente. Mezclar un
   grafo mecánico con uno semántico en el mismo documento hace que ninguno de
   los dos sea fácil de regenerar o confiar ciegamente.
3. **`rayflow_issues.json` tiene un tercer eje: es una cola de trabajo, no una
   descripción del estado del mundo.** Un issue típicamente enlaza *varios*
   claims y *varios* archivos a la vez ("este cambio en `executor.py` invalida
   tres afirmaciones de dos secciones distintas del SOT"), una relación
   muchos-a-muchos que no cuelga naturalmente de un solo archivo ni de un
   solo claim.

La alternativa elegida: **archivos separados, unidos por ids estables**, no
por contenido duplicado — el mismo patrón que ya usa `rayflow_file_map.json`
con su objeto `systems` (agrupación separada, no repetida dentro de cada
archivo).

## 4. Schema de `RAYFLOW_SOURCE_OF_TRUTH.json` (v2, implementado)

Cambios respecto al v1 actual (claims como strings sueltos en un array):

- Cada claim pasa a ser un objeto `{id, text, evidence, docs}`.
- `id`: `<section_id>#<slug>`, estable — es lo que un issue referencia en
  `claim_ids`.
- `evidence`: array de rutas repo-relative de **código**, con sufijo
  opcional `#símbolo` cuando conviene precisión
  (`rayflow/nodes/decorators.py#entry_node` en vez de un número de línea,
  que no sobrevive a una edición arriba). Puede estar vacío — significa "no
  localizado todavía", no "no existe". No distingue "sin auditar" de "es
  falso": esa distinción la hace `rayflow_issues.json` (si el auditor lo
  revisó y tiene razones para creer que es falso, nace un issue; si el
  array está vacío porque nadie lo miró todavía, no).
- `docs`: array de rutas de **otra documentación** (no código) que
  restablece el mismo hecho de forma independiente — `README.md`, un
  `SKILL.md`, `rayflow/editor/guide.py`, `docs/*.md`. **Nunca incluye
  `CLAUDE.md`** — una vez que exista la generación programática de
  `CLAUDE.md` a partir del SOT, `CLAUDE.md` deja de ser "otra
  documentación que puede desincronizarse": se vuelve una renderización
  del propio claim, siempre en sync por construcción. El valor de `docs`
  está justamente en capturar los lugares que SÍ pueden quedar
  desincronizados porque se mantienen a mano — el `.claude/hooks/
  _sot_scope.py --docs` resuelve, a partir de archivos de código
  cambiados, qué claims se ven afectados (vía `evidence`) y qué
  documentos de ese `docs` hay que revisar en consecuencia. Mismo criterio
  de "vacío no es falso" que `evidence`.
- `known_issues` (el array que vivía embebido en el SOT v1) desaparece por
  completo — se muda a `rayflow_issues.json`. El caso concreto de
  `FlowSettingsDialog.tsx` que motivó ese campo en v1 es hoy `ISSUE-0001`,
  el primer issue real del nuevo archivo.
- **Sin metadata de verificación por-claim** (nada de `last_verified`,
  `verified_by`, etc. colgando de cada uno de los ~215 claims): eso
  generaría diff-noise en cada corrida del auditor aunque no cambie nada
  real. Si se necesita un log de cuándo se auditó qué, va aparte (mensaje de
  commit del propio agente, o un archivo de log distinto — no decidido
  todavía).

```json
{
  "$schema_note": "...",
  "schema_version": 2,
  "source_file": "CLAUDE.md",
  "sections": [
    {
      "id": "sistema-de-nodos-entrada",
      "heading": "Sistema de nodos > Nodos de entrada (@entry_node)",
      "claims": [
        {
          "id": "sistema-de-nodos-entrada#exactly-one-entry",
          "text": "Un flow necesita exactamente un nodo de entrada — el punto donde el engine arranca la ejecución.",
          "evidence": ["rayflow/build/validator.py#_find_entry"],
          "docs": []
        }
      ]
    }
  ]
}
```

## 5. Schema de `rayflow_issues.json` (v1, implementado)

- **Solo issues abiertos.** El archivo no acumula historial: "resolver" un
  issue es eliminarlo del array en el mismo commit que aplica el fix. El
  historial completo (cuándo se creó, cuándo se resolvió, en qué commit) vive
  en `git log -p -- rayflow_issues.json` / `git blame`, no en el archivo.
- `next_id`: contador monótono que nunca retrocede ni reutiliza ids, aunque
  el array se achique. Por eso puede haber huecos en la numeración
  (`ISSUE-0002` existió y se resolvió; se busca en el historial de git para
  saber cuándo).
- **Sin `suggested_fix`**: el issue reporta la discrepancia (`summary` +
  `evidence`) sin proponer una solución — el agente que lo resuelva no debe
  arrancar sesgado por una propuesta escrita por el auditor.
- Cada issue enlaza `claim_ids` (puede estar vacío — no todo issue nace de un
  claim ya capturado en el SOT), `files` (código afectado) y `docs`
  (documentación en prosa a corregir: `CLAUDE.md`, `README.md`, un
  `SKILL.md`, etc.) — campos separados a propósito, un issue puede tener
  código sin doc afectada o viceversa.
- `kind` es un enum abierto (`claim_contradicted`, `orphan_claim`, ... se
  agregan tipos según los vaya necesitando el auditor).

Contenido real (`rayflow_issues.json` en la raíz del repo, al momento de
escribir esto):

```json
{
  "$schema_note": "...",
  "schema_version": 1,
  "next_id": 2,
  "issues": [
    {
      "id": "ISSUE-0001",
      "severity": "low",
      "kind": "claim_contradicted",
      "title": "FlowSettingsDialog.tsx ya no edita inputs del flow, pero CLAUDE.md sigue afirmando que sí",
      "summary": "...",
      "claim_ids": ["frontend-editor-visual#flowsettingsdialog-tsx-modal-inputs-outputs-flow"],
      "files": ["rayflow/editor/frontend/src/components/FlowSettingsDialog.tsx"],
      "docs": ["CLAUDE.md"],
      "detected_by": {"agent": "manual-audit", "run_id": "session-8e8dee33-2026-07-03", "trigger": "manual"},
      "detected_at": "2026-07-03T14:02:11Z",
      "evidence": [{"file": "rayflow/editor/frontend/src/components/FlowSettingsDialog.tsx", "note": "Props ya no incluye `inputs`; solo `outputs`."}]
    }
  ]
}
```

`next_id` vale 2 porque `ISSUE-0001` ya ocupa el slot 1 — el próximo issue que
se cree será `ISSUE-0002`. No hay ningún hueco todavía (para ver el caso de
un hueco — un issue creado y después resuelto/eliminado — hace falta que se
resuelva al menos uno primero).

### 5.1. Principio: revisión incremental, nunca reset masivo

Toda corrección al SOT — resolviendo un issue de `rayflow_issues.json`, un
reporte incidental a `rayflow-issue-writer`, o cualquiera de los cuatro
canales descritos en §6.4 — tiene que ser **incremental**: referenciar
`claim_ids`/archivos puntuales y tocar exactamente esos claims. Nunca una
reescritura masiva de secciones enteras del SOT de una sola vez, ni
siquiera con la excusa de "limpiar" o "modernizar" el documento. Este
mismo archivo documenta una migración inicial de ~215 claims (§4/§7); el
SOT ya creció bastante más allá de eso desde entonces (ver el índice de
secciones en `CLAUDE.md`, que hoy suma 384). Si en algún momento hace
falta repetir un salto de esa escala, tiene que hacerse de forma
consciente y documentada como una **migración deliberada** — con su
propio doc de diseño y su propia revisión — nunca colada como si fuera
"un issue más" resuelto por el flujo normal. Una reescritura masiva no
declarada rompe justamente lo que le da valor al `evidence` de cada
claim: la trazabilidad línea-a-línea vía `git log -p` / `git blame` que
permite auditar qué cambió y por qué (el mismo motivo, en espíritu, por
el que `rayflow_issues.json` tampoco acumula historial en el propio
archivo — ver §5 arriba).

## 6. Flujo previsto (agente auditor + pre-commit)

### 6.1. Agente auditor — implementado y confirmado

`.claude/agents/rayflow-auditor.md` es el agente: verifica claims del SOT
contra el código real y escribe issues en `rayflow_issues.json`. Diseño:

- **Scope**: se le puede pasar una lista de archivos/claims concreta (el
  caso típico desde pre-commit, scopeado al diff vía
  `.claude/hooks/_sot_scope.py`), o correr sin scope para auditar el SOT
  completo.
- `.claude/hooks/_sot_scope.py` es el helper que cruza archivos cambiados
  contra el campo `evidence` de cada claim — mecánico, no exhaustivo: un
  claim con `evidence: []` nunca va a aparecer ahí aunque el diff lo
  afecte, así que el agente tiene instrucción explícita de buscar
  activamente con `Grep`/`Glob` además de confiar en el filtro mecánico.
- **Deduplicación**: antes de crear un issue, revisa si ya hay uno abierto
  con el mismo `claim_id` en `rayflow_issues.json` — no duplica.
- **Restricciones duras**: nunca edita `RAYFLOW_SOURCE_OF_TRUTH.json` ni
  `CLAUDE.md`, nunca agrega `suggested_fix`. Su única escritura es
  `rayflow_issues.json`.
- **Validación manual del método** (no de la invocación real, ver debajo):
  se probó a mano el caso de `FlowSettingsDialog.tsx` — `_sot_scope.py`
  correctamente NO encuentra el claim (evidence vacía a propósito), pero
  una búsqueda activa por texto sí lo encuentra, y ya existe `ISSUE-0001`
  para ese `claim_id` — el flujo de deduplicación funciona como se diseñó.

**Hallazgo — confirmado en una sesión posterior**: invocar
`rayflow-auditor` vía el tool `Agent`/`Task` en la misma sesión que creó
`.claude/agents/rayflow-auditor.md` devuelve "Agent type not found" — el
descubrimiento de subagentes de proyecto vía ese tool sí requiere una
sesión nueva (no se resuelve en caliente). Pero **`claude -p --agent
rayflow-auditor "<prompt>"` funciona sin problema, en la misma sesión que
creó el archivo** — cada invocación de `claude -p` es un proceso nuevo que
lee `.claude/agents/` del disco al arrancar, así que no hereda la lista de
agentes ya cargada por la sesión padre. Probado end-to-end con el mismo
caso de `FlowSettingsDialog.tsx`: escaneó los 18 claims en scope, encontró
el claim de evidencia vacía por búsqueda activa (tal como estaba
instruido), confirmó que `ISSUE-0001` ya lo cubre, y no tocó
`rayflow_issues.json` ni ningún otro archivo (verificado con `git status`
después de la corrida). Esto es exactamente el mecanismo que necesita el
hook de pre-commit (§6.2) — confirmado, no solo hipotético.

### 6.2. Hook de pre-commit para el auditor — implementado, bloqueante

`scripts/run_sot_audit.py`, wireado en `.pre-commit-config.yaml` en el
stage `pre-commit` (id `sot-audit`):

1. Calcula los archivos staged (`git diff --cached --name-only`).
2. Los pasa por `.claude/hooks/_sot_scope.py` para obtener los `claim_ids`
   afectados. Si no hay ninguno, sale inmediatamente (exit 0) **sin llamar
   al LLM** — la mayoría de los commits no tocan evidence de ningún claim,
   y ese es el caso que tiene que ser gratis.
3. Si hay scope, arma un prompt con esos `claim_ids` (más un
   `detected_by.run_id` con timestamp y `trigger: "pre-commit"`) y corre
   `claude -p --agent rayflow-auditor "<prompt>"` (confirmado en §6.1;
   timeout de 300s).
4. Compara el contenido de `rayflow_issues.json` antes y después de la
   corrida. Si cambió, **bloquea el commit** (exit 1) con un mensaje
   pidiendo revisar el/los issue(s) nuevos y volver a `git add
   rayflow_issues.json` antes de re-commitear. Si no cambió, deja pasar el
   commit (exit 0) — el auditor corrió, no encontró nada, no hay nada que
   revisar.

**Decisión: bloqueante, no asincrónico/informativo.** La alternativa (un
paso de fondo que solo avisa) tiende a llegar tarde — el resultado aparece
después del commit que debería haber marcado, y es fácil terminar
entrenando a todos a ignorarlo. El costo de latencia de LLM se paga solo
en los commits que efectivamente tocan evidence de algún claim (paso 2),
no en cada commit.

**Fail-open en problemas de infraestructura, fail-closed en contenido.**
Si `claude` no está en el PATH, si hace timeout, o si termina con exit
code no-cero pero sin escribir nada en `rayflow_issues.json`, el hook
**no bloquea** — solo imprime un warning a stderr. Bloquear el repo entero
por una falla de infraestructura (el binario no está instalado, la red
falló) sería peor que el problema que este mecanismo intenta resolver. La
única señal que bloquea de verdad es "el auditor corrió y escribió algo
nuevo en `rayflow_issues.json`" — eso sí implica una divergencia real que
alguien tiene que mirar antes de que el commit entre.

Es el contrapunto directo de `scripts/check_sot_commit_message.py`
(§6.3, Capa 2): ese guarda **ediciones al SOT mismo**; este guarda
**cambios de código que invalidan en silencio lo que el SOT ya afirma**.

**Validado**: una corrida real contra un cambio trivial (un comentario en
`rayflow/editor/storage.py`, que sí cae en el scope de un claim) tardó
~60s, terminó en exit 0 y no tocó `rayflow_issues.json` — comportamiento
correcto, no había ninguna divergencia real que reportar. La rama de
bloqueo (exit 1 cuando `rayflow_issues.json` cambia) se validó simulando
la llamada a `subprocess.run` y la escritura del archivo, sin gastar una
corrida real de LLM en forzar una contradicción artificial.

El bloqueo de edición directa del SOT (que originalmente iba a resolverse
acá también) tiene su propio mecanismo, ver §6.3.

### 6.3. Bloqueo de edición directa del SOT — implementado

Dos capas, cada una resolviendo un problema distinto (ninguna reemplaza a la
otra):

**Capa 1 — `.claude/hooks/sot_guard.py`** (`PreToolUse`, matcher
`Edit|Write`): bloquea cualquier intento de tocar
`RAYFLOW_SOURCE_OF_TRUTH.json` con esos tools, salvo que la sesión tenga
`RAYFLOW_SOT_UNLOCK=1` seteado en su entorno. Feedback inmediato, sin costo
de LLM. **No es la garantía real** — un `Bash` con `python3`/`sed`/lo que
sea la esquiva sin problema, porque el hook solo mira `Edit`/`Write`. Por
eso hace falta la Capa 2.

**Capa 2 — `scripts/check_sot_commit_message.py`** (stage `commit-msg` del
framework `pre-commit`, wireado en `.pre-commit-config.yaml`): si
`RAYFLOW_SOURCE_OF_TRUTH.json` está en el diff staged de un commit, exige un
trailer `Sot-Change: <razón>` en el mensaje — si falta, rechaza el commit.
Esta es la garantía real: corre sobre el estado de git, no importa cómo se
editó el archivo (Editor, `Bash`, a mano desde la terminal, lo que sea). A
propósito no tiene bypass por variable de entorno acá — el trailer hay que
escribirlo de nuevo en cada commit, así que no puede quedar "prendido" por
accidente para commits futuros no relacionados (a diferencia de una env var
a este nivel).

Para activar las dos capas en un checkout nuevo:

```bash
pip install pre-commit   # si no está ya
pre-commit install       # instala pre-commit Y commit-msg (default_install_hook_types)
```

**Validado end-to-end** (repo git temporal, no en este repo): commit a un
archivo no relacionado sin trailer → pasa; commit al SOT sin trailer →
rechazado con mensaje claro; mismo commit con `Sot-Change: ...` → pasa. La
Capa 1 también se probó simulando el payload de stdin que le manda el
harness: bloquea sin `RAYFLOW_SOT_UNLOCK=1`, permite con la variable
seteada, no interviene en archivos que no son el SOT.

### 6.4. `rayflow-issue-writer`: único punto de escritura, y el cuarto canal de creación de issues

**Problema que motiva este refactor.** Con el diseño de §6.1-6.3, solo
`rayflow-auditor` (y, desde la introducción de
`.claude/workflows/audit-sot-parallel.js`, su etapa de consolidación)
escribían en `rayflow_issues.json`. Eso dejaba un gap de descubribilidad:
cualquier otro agente — un `rayflow-<sistema>-specialist` resolviendo una
tarea normal, `rayflow-router` ubicando un archivo, o cualquiera que notara
*incidentalmente* que un claim del SOT ya no es cierto mientras hacía otra
cosa — no tenía un camino fácil para reportarlo. La alternativa obvia
(editar `rayflow_issues.json` directamente) hubiera dispersado la lógica de
validación/dedup/formato en cada agente del repo, y debilitado la
garantía de que todo lo que entra a ese archivo pasó por una verificación
real antes de escribirse.

**Solución: centralizar toda escritura en `rayflow-issue-writer`.**
`.claude/agents/rayflow-issue-writer.md` es ahora el único agente de este
repo con `Edit` habilitado sobre `rayflow_issues.json` (de hecho, el único
archivo que tiene sentido que edite). Cualquier agente que sospeche una
discrepancia le reporta el candidato — qué `claim_id`(s), por qué, qué
evidencia — y `rayflow-issue-writer`:

1. Verifica cada candidato de forma independiente (lee el claim real, lee
   los archivos de evidencia) — no confía ciegamente en el reporte
   entrante, exactamente la misma disciplina que ya aplicaba
   `rayflow-auditor`.
2. Dedupea contra `rayflow_issues.json` (estado real, no lo que asuma quien
   reportó) y, si le llega un batch, entre los propios candidatos del
   batch.
3. Arma el issue con el mismo formato exacto de siempre (§5) y hace una
   única escritura atómica.

Como consecuencia, `rayflow-auditor` (§6.1) perdió `Edit` de su
frontmatter — ya no puede escribir en `rayflow_issues.json` ni en ningún
otro archivo. Cuando corre standalone (invocación manual o vía
`scripts/run_sot_audit.py`), delega cada hallazgo confirmado a
`rayflow-issue-writer` en vez de escribirlo él mismo. Cuando corre como
parte de un fan-out paralelo (`audit-sot-parallel.js`), sigue devolviendo
únicamente la estructura de datos pedida — la etapa de consolidación de ese
workflow ahora es una instancia de `rayflow-issue-writer` en vez de una
instancia extra de `rayflow-auditor` con un prompt de merge/dedup/escritura
incrustado a mano.

**Los cuatro canales de creación de un issue**, con esto:

1. **Manual, por un humano** — el caso original de `ISSUE-0001`
   (`detected_by.agent: "manual-audit"`): alguien audita a mano y escribe
   el issue directamente (o le pide a `rayflow-issue-writer` que lo haga
   por él, ya que es el único con permiso).
2. **`rayflow-auditor` invocado manualmente** (§6.1) — auditoría dirigida a
   un scope concreto o al SOT completo, delegando sus hallazgos a
   `rayflow-issue-writer`.
3. **`rayflow-auditor` disparado automáticamente por el hook de
   pre-commit** (§6.2, `scripts/run_sot_audit.py`) — mismo mecanismo de
   delegación, pero dentro de la misma invocación de `claude -p` que
   dispara el hook (por eso el chequeo de "¿cambió `rayflow_issues.json`
   antes/después de la corrida?" en `run_sot_audit.py` sigue funcionando
   sin cambios: la escritura de `rayflow-issue-writer` ocurre como
   subagente dentro del mismo proceso).
4. **Reporte incidental de cualquier otro agente** (nuevo, habilitado por
   este refactor) — un `rayflow-<sistema>-specialist`, `rayflow-router`, o
   cualquier agente que note una discrepancia mientras hace otro trabajo
   puede reportarla directamente a `rayflow-issue-writer` (tool `Agent`,
   `subagent_type: rayflow-issue-writer`), sin necesidad de disparar una
   auditoría formal sobre todo el SOT ni esperar a que la note el hook de
   pre-commit.

### 6.5. Política: preferir auditoría paralela para cambios de alto impacto sobre el documento raíz

Cualquier revisión que toque contenido usado para construir el documento
raíz (`rayflow_system_prompt.md`, o una sección del SOT con alto
impacto/muchos claims — ver el índice de secciones que `CLAUDE.md`
genera desde acá) debería preferir correr
`.claude/workflows/audit-sot-parallel.js` (varias instancias
independientes de `rayflow-auditor`, una por grupo de secciones, con una
única etapa de consolidación vía `rayflow-issue-writer` — ver §6.4) en
vez de una sola pasada secuencial de auditoría. `rayflow_system_prompt.md`
es lo que termina leyendo, vía `CLAUDE.md`, todo agente que trabaje en
este repo — dejar que una sola voz/perspectiva de auditoría decida qué
está bien o mal ahí sesga en silencio el contexto compartido de todo el
sistema. Varios auditores independientes seguidos de una consolidación
explícita que dedupea y resuelve entre ellos es una salvaguarda barata
contra ese sesgo cuando el contenido en juego tiene este nivel de
impacto.

## 7. Pendientes

- [x] Aprobar el schema v2 del SOT (§4) y migrar los ~215 claims existentes.
- [x] Crear `rayflow_issues.json` en la raíz con el schema de §5 (arrancando
      con `ISSUE-0001` = el caso de `FlowSettingsDialog.tsx`).
- [x] Diseñar e implementar el mecanismo de bloqueo de edición directa del
      SOT — dos capas, `sot_guard.py` + `check_sot_commit_message.py`,
      validadas end-to-end (§6.3).
- [x] Diseñar el prompt/alcance del agente auditor — `.claude/agents/
      rayflow-auditor.md` + `.claude/hooks/_sot_scope.py` (§6.1). Método
      validado a mano; invocación real confirmada vía `claude -p --agent
      rayflow-auditor` (el tool `Task`/`Agent` in-session falla con "Agent
      type not found" hasta una sesión nueva, pero `claude -p` no depende
      de eso — ver §6.1).
- [x] Escribir el script que arma el prompt con el scope del diff
      (`_sot_scope.py`) y llama a `claude -p --agent rayflow-auditor`, y
      agregar la entrada correspondiente en `.pre-commit-config.yaml`
      (§6.2 — `scripts/run_sot_audit.py`, id `sot-audit`, stage
      `pre-commit`). Decisión: **bloqueante** — sale gratis (exit 0, sin
      LLM) si el diff no toca evidence de ningún claim; si toca, corre el
      auditor y bloquea el commit solo si escribió en
      `rayflow_issues.json`; fail-open en problemas de infraestructura
      (`claude` ausente, timeout). Validado end-to-end (corrida real sin
      hallazgos + rama de bloqueo simulada).
- [ ] Probar el hook `sot-audit` disparando una divergencia real (no
      simulada) para confirmar el mensaje de bloqueo tal como lo va a ver
      un committer de verdad, no solo la lógica interna del script.
