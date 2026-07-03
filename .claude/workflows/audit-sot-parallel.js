export const meta = {
  name: 'audit-sot-parallel',
  description: 'Audita las claims de RAYFLOW_SOURCE_OF_TRUTH.json en paralelo (6 grupos de secciones) y consolida los issues nuevos en rayflow_issues.json en una sola escritura atómica',
  phases: [
    { title: 'Audit', detail: '6 instancias de rayflow-auditor en paralelo, una por grupo de secciones, solo lectura + reporte estructurado (no pueden escribir aunque quisieran: no tienen Edit en su frontmatter)' },
    { title: 'Consolidate', detail: 'una instancia de rayflow-issue-writer recibe el batch completo de propuestas de los 6 grupos, las re-verifica de forma independiente, dedupea contra el estado actual y entre sí, y hace la única escritura atómica en rayflow_issues.json' },
  ],
}

// Partición de las secciones de RAYFLOW_SOURCE_OF_TRUTH.json en 6 grupos
// balanceados por cantidad de claims (~215 claims total al momento de
// escribir esto, ~36 por grupo). El orden del archivo se preserva dentro
// de cada grupo para mantener juntas secciones temáticamente contiguas
// (p.ej. las 5 secciones `sistema-de-nodos-*` comparten varios archivos de
// evidencia, así que agruparlas reduce reads redundantes entre agentes).
//
// Hardcodeado a propósito: el script de Workflow no tiene acceso a
// filesystem, así que no puede leer RAYFLOW_SOURCE_OF_TRUTH.json él mismo
// para calcular esta partición dinámicamente — cada agente abajo lee el
// archivo en runtime y filtra por su lista de section_id. Si el SOT gana o
// pierde secciones, esta lista puede desbalancearse con el tiempo; no es
// grave (las secciones son unidades indivisibles, algo de desbalance es
// esperable), pero si un grupo queda muy por encima del resto conviene
// re-partir a mano.
const SECTION_GROUPS = [
  ['carpeta-de-pruebas', 'comandos-de-desarrollo', 'arquitectura-general', 'frontend-editor-visual'],
  ['sistema-de-nodos-decoradores', 'sistema-de-nodos-entrada', 'sistema-de-nodos-estado', 'sistema-de-nodos-ctx-fire', 'sistema-de-nodos-pending-outputs'],
  ['sistema-de-nodos-runqueue-sse', 'sistema-de-nodos-descubrimiento', 'api-rest-flows'],
  ['api-rest-custom-nodes', 'capa-mcp'],
  ['schema-de-un-flow', 'reglas-de-ui', 'ciclo-de-vida-de-un-flow'],
  ['sistema-de-eventos', 'triggers-por-cambio-de-variable', 'archivos-clave-del-backend'],
]

const PROPOSED_ISSUES_SCHEMA = {
  type: 'object',
  properties: {
    proposed_issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
          kind: { type: 'string', enum: ['claim_contradicted', 'orphan_claim'] },
          title: { type: 'string' },
          summary: { type: 'string' },
          claim_ids: { type: 'array', items: { type: 'string' } },
          files: { type: 'array', items: { type: 'string' } },
          docs: { type: 'array', items: { type: 'string' } },
          evidence: {
            type: 'array',
            items: {
              type: 'object',
              properties: { file: { type: 'string' }, note: { type: 'string' } },
              required: ['file', 'note'],
            },
          },
        },
        required: ['severity', 'kind', 'title', 'summary', 'claim_ids'],
      },
    },
    claims_checked_count: { type: 'integer' },
    claims_skipped_existing_issue: { type: 'array', items: { type: 'string' } },
  },
  required: ['proposed_issues', 'claims_checked_count'],
}

function findPrompt(sectionIds) {
  return `Auditá SOLO las claims de RAYFLOW_SOURCE_OF_TRUTH.json cuyo section_id esté en esta lista: ${JSON.stringify(sectionIds)}.

Leé RAYFLOW_SOURCE_OF_TRUTH.json completo, quedate únicamente con las secciones listadas arriba (el campo "id" de cada entry en "sections"), y aplicá tu método habitual de auditoría (evidence -> Read/Grep -> comparar texto vs código real) a cada claim de esas secciones.

Leé también rayflow_issues.json para no proponer un issue sobre un claim_id que ya tiene un issue abierto (mismo dedup de lectura que hacés en tu corrida normal).

IMPORTANTE — esta es una corrida parcial dentro de un fan-out paralelo de varios agentes auditando distintos grupos de secciones al mismo tiempo. Una instancia de rayflow-issue-writer recibe el batch completo de todos los grupos y hace el merge, la re-verificación y la única escritura atómica después de que todos los grupos terminen — vos ni siquiera tenés Edit en tu frontmatter, así que esto ya está garantizado a nivel de permisos, no solo de instrucción. Tu única salida es la estructura de datos pedida.

Para cada claim de tu scope: si está contradicha por el código real, sumala a proposed_issues con kind="claim_contradicted"; si evidence está vacía y no encontrás sustento tras buscar activamente, kind="orphan_claim"; si se verifica como cierta, o si ya tiene un issue abierto (revisá claim_ids en rayflow_issues.json), no la incluyas en proposed_issues — en ese último caso sumala a claims_skipped_existing_issue. Reportá en claims_checked_count el total de claims que evaluaste en esta corrida (deberían ser todas las de tu scope).`
}

phase('Audit')
const groupResults = await parallel(
  SECTION_GROUPS.map((sectionIds, i) => () =>
    agent(findPrompt(sectionIds), {
      label: `audit-group-${i + 1}`,
      phase: 'Audit',
      agentType: 'rayflow-auditor',
      schema: PROPOSED_ISSUES_SCHEMA,
    })
  )
)

const validResults = groupResults.filter(Boolean)
log(`${validResults.length}/${SECTION_GROUPS.length} grupos de auditoría completados`)

const allProposed = validResults.flatMap(r => r.proposed_issues || [])
const totalChecked = validResults.reduce((sum, r) => sum + (r.claims_checked_count || 0), 0)
log(`${totalChecked} claims chequeadas en total, ${allProposed.length} issues propuestos antes de consolidar`)

if (allProposed.length === 0) {
  return {
    claims_checked: totalChecked,
    groups_completed: validResults.length,
    groups_total: SECTION_GROUPS.length,
    issues_created: [],
    message: 'Auditoría completa: ningún claim contradicho ni huérfano detectado en ningún grupo.',
  }
}

phase('Consolidate')
const consolidationReport = await agent(
  `Sos rayflow-issue-writer, el único agente de este repo con permiso para escribir en rayflow_issues.json. Te llega el batch completo de candidatos propuestos por 6 instancias de rayflow-auditor que corrieron en paralelo, cada una sobre un grupo distinto de secciones de RAYFLOW_SOURCE_OF_TRUTH.json (ninguna de esas instancias tiene Edit en su frontmatter, así que ninguna escribió nada — este es el único punto de escritura de toda la corrida). Esta es la lista completa de candidatos propuestos por todos los grupos, en JSON:

${JSON.stringify(allProposed, null, 2)}

Aplicá tu método habitual: verificá cada candidato de forma independiente (no asumas que el reporte es correcto), leé rayflow_issues.json completo para dedupear contra los claim_ids ya abiertos, dedupealos también entre sí (dos grupos distintos pueden haber detectado el mismo síntoma desde ángulos distintos), y hacé una única escritura atómica para los que sobrevivan. Para detected_by de los que confirmes, usá {agent: "audit-sot-parallel-workflow", run_id: "<un identificador descriptivo, ej. incluyendo qué grupos originaron el hallazgo>", trigger: "manual"} salvo que prefieras tu propio detected_by por defecto. Cerrá con tu reporte final habitual (cuántos candidatos recibiste, cuántos issues creaste con sus ids y títulos, cuántos rechazaste y por qué).`,
  { label: 'consolidate-issues', phase: 'Consolidate', agentType: 'rayflow-issue-writer' }
)

return {
  claims_checked: totalChecked,
  groups_completed: validResults.length,
  groups_total: SECTION_GROUPS.length,
  proposed_before_consolidation: allProposed.length,
  consolidation_report: consolidationReport,
}
