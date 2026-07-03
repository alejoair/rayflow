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
| Agente auditor | Recorre cada claim del SOT, valida contra el repo, escribe/actualiza `rayflow_issues.json`. | **Definido.** `.claude/agents/rayflow-auditor.md` + helper `.claude/hooks/_sot_scope.py` (scopea por diff). Método validado a mano (ver §6.1) — la invocación real vía `Task`/`Agent` **no** se pudo probar en la misma sesión que creó el archivo (ver §6.1, hallazgo de descubrimiento de subagentes). |
| Hook pre-commit | Dispara el agente auditor (y otras herramientas) antes de cada commit; usa `claude -p` en modo headless. | No implementado. `pre-commit` (framework) ya está instalado en el entorno de trabajo. |
| Bloqueo de edición directa | Impide que `RAYFLOW_SOURCE_OF_TRUTH.json` se edite a mano fuera del flujo del agente auditor, para "garantizar" (mayúsculas del nombre del archivo) que nunca quede desactualizado. | No implementado. Mecanismo concreto pendiente de diseño. |

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

- Cada claim pasa a ser un objeto `{id, text, evidence}`.
- `id`: `<section_id>#<slug>`, estable — es lo que un issue referencia en
  `claim_ids`.
- `evidence`: array de rutas repo-relative, con sufijo opcional `#símbolo`
  cuando conviene precisión (`rayflow/nodes/decorators.py#entry_node` en vez
  de un número de línea, que no sobrevive a una edición arriba). Puede estar
  vacío — significa "no localizado todavía", no "no existe". No distingue
  "sin auditar" de "es falso": esa distinción la hace `rayflow_issues.json`
  (si el auditor lo revisó y tiene razones para creer que es falso, nace un
  issue; si el array está vacío porque nadie lo miró todavía, no).
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
          "evidence": ["rayflow/build/validator.py#_find_entry"]
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

## 6. Flujo previsto (agente auditor + pre-commit)

### 6.1. Agente auditor — implementado, invocación real sin probar

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

**Hallazgo pendiente de confirmar**: intentar invocar `rayflow-auditor` vía
el tool `Agent`/`Task` en la misma sesión que creó el archivo
`.claude/agents/rayflow-auditor.md` devolvió "Agent type not found" — el
descubrimiento de subagentes de proyecto parece resolverse al arrancar la
sesión, no en caliente. Falta confirmar en una sesión nueva que el agente
efectivamente aparece disponible después de reiniciar. Si esto se confirma,
tiene una implicancia directa para el hook de pre-commit (§6.2): no puede
asumir que un agente recién creado/editado en el mismo proceso ya está
activo.

### 6.2. Hook de pre-commit — sin diseño detallado todavía

Lo discutido hasta ahora, a nivel de intención, no de mecanismo concreto:

- Un hook de **pre-commit** (usando el framework `pre-commit`, ya instalado)
  dispara el agente auditor antes de cada commit, junto con otras
  herramientas (linters, type-check, etc. — no especificado).
- El auditor se invoca como `claude -p` (modo headless/print) — a diferencia
  de invocarlo como subagente vía `Task`/`Agent` (que vive dentro de una
  sesión interactiva), `claude -p` es un proceso nuevo por invocación, así
  que el hallazgo de §6.1 (descubrimiento de subagentes al arrancar) no
  debería aplicar acá de la misma forma — cada invocación de `claude -p` YA
  es un arranque nuevo. Falta confirmar esto también.
- Debería pasarle el scope (`git diff --cached --name-only`) al prompt, para
  que el auditor no re-audite los 215 claims en cada commit — ya resuelto a
  nivel de mecanismo (`_sot_scope.py`), falta engancharlo al hook en sí.
- Si encuentra una divergencia, escribe/actualiza `rayflow_issues.json`.
- Se quiere que `RAYFLOW_SOURCE_OF_TRUTH.json` **no se pueda editar a mano**
  fuera de ese flujo — la idea es que un hook lo bloquee, aunque el mecanismo
  concreto (¿qué distingue una edición "del agente auditor" de una edición
  cualquiera? ¿un flag de entorno, un commit trailer, un proceso que corre
  con permisos distintos?) todavía no está decidido.
- Pensado para correr 100% local (versionado con git normal), sin depender
  de GitHub/GitLab ni de sus mecanismos de CI/PR.

Todo este punto queda abierto para la próxima sesión de diseño.

## 7. Pendientes

- [x] Aprobar el schema v2 del SOT (§4) y migrar los ~215 claims existentes.
- [x] Crear `rayflow_issues.json` en la raíz con el schema de §5 (arrancando
      con `ISSUE-0001` = el caso de `FlowSettingsDialog.tsx`).
- [ ] Diseñar el mecanismo de bloqueo de edición directa del SOT.
- [x] Diseñar el prompt/alcance del agente auditor — `.claude/agents/
      rayflow-auditor.md` + `.claude/hooks/_sot_scope.py` (§6.1). Método
      validado a mano; invocación real vía `Task`/`Agent` sin confirmar
      todavía (falta probarlo en una sesión nueva).
- [ ] Configurar `.pre-commit-config.yaml` para disparar el auditor y
      cualquier otra herramienta que se sume.
- [ ] Decidir si el bloqueo/auditor corren en cada commit o solo cuando el
      diff toca archivos relevantes (para no pagar el costo de invocar
      `claude -p` en cada commit trivial).
