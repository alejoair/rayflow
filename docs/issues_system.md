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
| `RAYFLOW_SOURCE_OF_TRUTH.json` | Cada afirmación de `CLAUDE.md`, estructurada, con evidencia de dónde se sostiene en el código. | Existe (schema v1); migración a schema v2 (ver §4) pendiente de aplicar a los 215 claims reales. |
| `rayflow_issues.json` | Cola de discrepancias abiertas entre una afirmación y la realidad del repo. | Schema acordado (§5); archivo aún no creado en el repo. |
| `rayflow_file_map.json` | Ya existente, sin cambios de rol: mapa mecánico archivo→{descripción, depends_on, dependents}. | Sin cambios — ver §3 por qué no se fusiona con lo anterior. |
| Agente auditor | Recorre cada claim del SOT, valida contra el repo, escribe/actualiza `rayflow_issues.json`. | No implementado. Diseño pendiente. |
| Hook pre-commit | Dispara el agente auditor (y otras herramientas) antes de cada commit; usa `claude -p` en modo headless. | No implementado. Diseño pendiente — `pre-commit` (Python, framework de hooks) ya está instalado en el entorno de trabajo. |
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

## 4. Schema de `RAYFLOW_SOURCE_OF_TRUTH.json` (v2, propuesto)

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
  `FlowSettingsDialog.tsx` que motivó ese campo en v1 es hoy el primer issue
  de ejemplo del nuevo archivo.
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

## 5. Schema de `rayflow_issues.json` (v1, acordado)

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

```json
{
  "$schema_note": "...",
  "schema_version": 1,
  "next_id": 4,
  "issues": [
    {
      "id": "ISSUE-0001",
      "severity": "high",
      "kind": "claim_contradicted",
      "title": "FlowSettingsDialog.tsx ya no edita inputs del flow, pero CLAUDE.md sigue afirmando que sí",
      "summary": "...",
      "claim_ids": ["frontend-editor-visual#flowsettingsdialog-inputs-outputs"],
      "files": ["rayflow/editor/frontend/src/components/FlowSettingsDialog.tsx"],
      "docs": ["CLAUDE.md"],
      "detected_by": {"agent": "rayflow-audit", "run_id": "...", "trigger": "manual"},
      "detected_at": "2026-07-03T14:02:11Z",
      "evidence": [{"file": "rayflow/editor/frontend/src/components/FlowSettingsDialog.tsx", "note": "Props ya no incluye `inputs`; solo `outputs`."}]
    }
  ]
}
```

## 6. Flujo previsto (agente auditor + pre-commit) — sin diseño detallado todavía

Lo discutido hasta ahora, a nivel de intención, no de mecanismo concreto:

- Un hook de **pre-commit** (usando el framework `pre-commit`, ya instalado)
  dispara el agente auditor antes de cada commit, junto con otras
  herramientas (linters, type-check, etc. — no especificado).
- El auditor se invoca como `claude -p` (modo headless/print), pidiéndole que
  revise si el diff staged modifica alguna afirmación del SOT.
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

- [ ] Aprobar el schema v2 del SOT (§4) y migrar los ~215 claims existentes.
- [ ] Crear `rayflow_issues.json` en la raíz con el schema de §5 (arrancando
      con `ISSUE-0001` = el caso de `FlowSettingsDialog.tsx`).
- [ ] Diseñar el mecanismo de bloqueo de edición directa del SOT.
- [ ] Diseñar el prompt/alcance del agente auditor (qué le entra, qué le
      pedimos que devuelva, cómo evita falsos positivos).
- [ ] Configurar `.pre-commit-config.yaml` para disparar el auditor y
      cualquier otra herramienta que se sume.
- [ ] Decidir si el bloqueo/auditor corren en cada commit o solo cuando el
      diff toca archivos relevantes (para no pagar el costo de invocar
      `claude -p` en cada commit trivial).
