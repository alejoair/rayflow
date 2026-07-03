export const meta = {
  name: 'audit-sot-parallel',
  description: 'Audita las claims de RAYFLOW_SOURCE_OF_TRUTH.json en paralelo (6 grupos de secciones) y consolida los issues nuevos en rayflow_issues.json en una sola escritura atómica',
  phases: [
    { title: 'Audit', detail: '6 instancias de rayflow-auditor en paralelo, una por grupo de secciones, solo lectura + reporte estructurado' },
    { title: 'Consolidate', detail: 'una instancia final de rayflow-auditor mergea, dedupea contra el estado actual y escribe rayflow_issues.json una sola vez' },
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

IMPORTANTE — esta es una corrida parcial dentro de un fan-out paralelo de varios agentes auditando distintos grupos de secciones al mismo tiempo. NO edites rayflow_issues.json vos bajo ninguna circunstancia: otra instancia hace el merge y la única escritura atómica después de que todos los grupos terminen, específicamente para evitar una carrera de escritura sobre el mismo archivo compartido. Tu única salida es la estructura de datos pedida — no toques ningún archivo.

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
  `Sos la etapa final de consolidación de una auditoría paralela del SOT. Varios agentes auditaron en paralelo distintos grupos de secciones de RAYFLOW_SOURCE_OF_TRUTH.json y cada uno propuso issues de forma independiente, SIN escribir rayflow_issues.json (esa restricción era solo para esas corridas paralelas, no aplica a vos). Esta es la lista completa de issues propuestos por todos los grupos, en JSON:

${JSON.stringify(allProposed, null, 2)}

Tu tarea:
1. Leé rayflow_issues.json completo (el estado actual real — puede haber cambiado desde que arrancó la auditoría paralela).
2. Para cada issue propuesto arriba, re-verificá contra los claim_ids ya abiertos en el archivo actual — no agregues un issue si ya existe uno abierto con ese claim_id.
3. Deduplicá también entre los propios issues propuestos arriba: si dos entradas comparten claim_ids (dos grupos distintos detectando el mismo síntoma desde ángulos distintos), mergealas en un solo issue en vez de crear dos.
4. A los issues que sobrevivan la dedup, asignales un id ISSUE-XXXX secuencial arrancando desde el next_id actual del archivo, con detected_by = {agent: "audit-sot-parallel-workflow", run_id: "<un identificador descriptivo, ej. incluyendo qué grupos originaron el hallazgo>", trigger: "manual"} y detected_at con una fecha ISO8601 razonable.
5. Hacé una única escritura atómica: reescribí rayflow_issues.json completo con next_id actualizado y el array issues (los que ya existían + los nuevos consolidados).
6. Reportá en texto: cuántos issues nuevos escribiste (con sus ids y títulos), cuántos propuestos se descartaron por ya existir, y cuántos se mergearon entre sí por compartir claim_ids.`,
  { label: 'consolidate-issues', phase: 'Consolidate', agentType: 'rayflow-auditor' }
)

return {
  claims_checked: totalChecked,
  groups_completed: validResults.length,
  groups_total: SECTION_GROUPS.length,
  proposed_before_consolidation: allProposed.length,
  consolidation_report: consolidationReport,
}
