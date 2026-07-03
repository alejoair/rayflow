# CLAUDE.md generado automáticamente

> Documento autocontenido: no asume contexto de la conversación donde se
> originó. Describe el mecanismo tal como quedó implementado.

## 1. El problema

`CLAUDE.md` es el archivo que Claude Code (o cualquier agente LLM) lee al
arrancar una sesión en este repo. Antes de este cambio era un archivo de
prosa editado a mano, ~530 líneas, que mezclaba dos cosas de naturaleza
distinta:

1. **Convenciones/proceso** — comandos de desarrollo, reglas de estilo de
   UI, cómo está organizado el editor visual. Cambia poco, no lo audita
   nadie contra el código.
2. **Afirmaciones sobre cómo funciona el código hoy** — exactamente el
   contenido que `RAYFLOW_SOURCE_OF_TRUTH.json` (SOT) ya extrajo como 215
   claims verificables con evidencia, y que el agente `rayflow-auditor`
   audita en cada commit relevante (`docs/issues_system.md`).

El SOT resuelve la staleness de (2) — pero solo si algo lee el SOT. Si
`CLAUDE.md` sigue siendo un archivo de prosa separado editado a mano,
nada garantiza que sus afirmaciones coincidan con las del SOT: son dos
copias del mismo hecho, y las copias divergen.

## 2. La solución: `CLAUDE.md` pasa a ser un archivo generado

- **`rayflow_system_prompt.md`** (nuevo, raíz, git-tracked): la fuente
  hand-maintained. Es, contenido a contenido, lo que antes era
  `CLAUDE.md` — se edita igual que se editaba `CLAUDE.md` antes de este
  cambio.
- **`CLAUDE.md`**: pasa a ser un archivo **generado** por
  `scripts/generate_claude_md.py`, compuesto por:
  1. Un banner HTML comentado avisando que es generado y de dónde sale.
  2. El contenido de `rayflow_system_prompt.md`, verbatim.
  3. Un **índice** de `RAYFLOW_SOURCE_OF_TRUTH.json`: por cada sección,
     `section_id` + heading + cantidad de claims — **no** el texto de los
     215 claims. El objetivo es que el agente sepa que existe más detalle
     verificado y dónde pedirlo (`Read RAYFLOW_SOURCE_OF_TRUTH.json`,
     filtrando por `section_id`), sin que `CLAUDE.md` crezca con cada
     claim nuevo ni duplique la prosa de arriba.
  4. Un **índice** de `rayflow_file_map.json.systems`: sistema + cantidad
     de archivos + descripción.
  5. Un footer con el hash corto del commit desde el que se generó.

## 3. Por qué se decidió NO bloquear la edición directa de `CLAUDE.md`

Se evaluó un mecanismo de bloqueo tipo `sot_guard.py` (el que protege
`RAYFLOW_SOURCE_OF_TRUTH.json`, ver `docs/issues_system.md` §6.3) y se
descartó: acá alcanza con que el archivo se **sobreescriba solo** en cada
commit. Editar `CLAUDE.md` a mano no rompe nada — simplemente esa edición
no sobrevive al próximo commit, porque el hook de pre-commit lo regenera
desde `rayflow_system_prompt.md` y lo vuelve a escribir. No hace falta
prohibir algo que ya se corrige solo.

Esto es más simple que el mecanismo de dos capas del SOT porque el SOT
**si** necesita bloqueo real: sus ediciones son deliberadas y raras (un
claim se corrige después de auditar, no en cada commit), así que un
bloqueo con excepción explícita (`Sot-Change: <razón>`) tiene sentido.
`CLAUDE.md` en cambio se reescribe en *cada* commit por diseño — bloquear
su edición sería redundante con eso.

## 4. Por qué sigue git-tracked, no gitignored

Se consideró gitignorar `CLAUDE.md` (ya que es 100% derivado), pero eso
introduce un problema real: un **clone fresco** no tendría `CLAUDE.md` en
absoluto hasta la primera regeneración, y como Claude Code carga
`CLAUDE.md` al arrancar la sesión (no hay garantía de que un hook corra
*antes* de ese load), la primerísima sesión en un clone nuevo se quedaría
sin contexto de proyecto.

Manteniéndolo git-tracked y regenerándolo/re-stageándolo en cada commit,
ese problema desaparece por construcción: un clone siempre trae *algún*
`CLAUDE.md`, en el peor caso un commit desactualizado respecto a
`rayflow_system_prompt.md` (si alguien commiteó sin pasar por el hook de
pre-commit, algo que el propio framework `pre-commit` previene en uso
normal). No hace falta ningún mecanismo de bootstrap aparte.

## 5. Mecanismo (`scripts/generate_claude_md.py`)

Determinístico, sin LLM, sin red — pura lectura de 3 archivos + templating
de texto:

```
rayflow_system_prompt.md ─┐
RAYFLOW_SOURCE_OF_TRUTH.json ─┼─→ scripts/generate_claude_md.py → CLAUDE.md
rayflow_file_map.json ─────┘
```

Wireado en `.pre-commit-config.yaml`, hook `claude-md-generate`, stage
`pre-commit`:

- Genera el contenido nuevo en memoria.
- Si es igual al `CLAUDE.md` actual en disco, no hace nada (exit 0, sin
  tocar el árbol de trabajo).
- Si es distinto, sobreescribe `CLAUDE.md` y corre `git add CLAUDE.md`
  para que la versión regenerada viaje en el mismo commit que se está
  haciendo — igual que hacen herramientas de auto-fix tipo `black`, pero
  sin necesidad de que el committer vuelva a correr `git commit` a mano:
  el `add` ocurre en el mismo hook, antes de que `pre-commit` termine su
  pasada.
- Nunca bloquea (siempre exit 0) — no hay nada que "fallar", es
  templating puro sobre archivos que ya están validados por sus propios
  mecanismos (el SOT por el auditor, el file map por sus propios checks).

## 6. Qué NO cambia

- `RAYFLOW_SOURCE_OF_TRUTH.json` y `rayflow_issues.json` siguen exactamente
  igual — este mecanismo solo agrega un *consumidor* más (el generador),
  no cambia su schema ni su flujo de auditoría (`docs/issues_system.md`).
- El agente `rayflow-auditor` sigue auditando el SOT contra el código real,
  no contra `CLAUDE.md` — el `$schema_note` del SOT ya excluía `CLAUDE.md`
  de los `docs` de cada claim precisamente porque estaba destinado a
  convertirse en una vista generada, no en documentación independiente
  que pudiera divergir.
- `rayflow/claude_tools/` (lo que se instala en proyectos de terceros vía
  `rayflow install claude-tools`) es un producto completamente distinto,
  no afectado por este cambio.
