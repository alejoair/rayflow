> `rayflow_system_prompt.md` — fuente hand-maintained de `CLAUDE.md`.
> `CLAUDE.md` en sí es un archivo **generado**
> (`scripts/generate_claude_md.py`) que envuelve este contenido verbatim más
> un índice de `RAYFLOW_SOURCE_OF_TRUTH.json` y `rayflow_file_map.json`, y se
> regenera y sobreescribe automáticamente en cada commit (hook
> `claude-md-generate` en `.pre-commit-config.yaml`) — así que editar
> `CLAUDE.md` directamente no sirve de nada a partir del próximo commit.
> Editá este archivo en su lugar. Ver `docs/claude_md_generation.md` para el
> diseño completo.

Guía para Claude Code (o cualquier agente LLM) al trabajar en este repositorio.

Este documento se mantiene deliberadamente corto: solo cubre lo que ningún
subagente especializado posee por sí solo (convenciones de workflow, comandos
de desarrollo, y el mapa mental de alto nivel para decidir a quién delegar).
El detalle de cada sistema — arquitectura interna, contratos, API, convenciones
específicas — vive en los subagentes `.claude/agents/rayflow-<sistema>-specialist.md`,
uno por sistema listado en el "Índice de sistemas" al final de este documento
(regenerado automáticamente en cada commit desde `rayflow_file_map.json` +
`RAYFLOW_SOURCE_OF_TRUTH.json` + `rayflow_issues.json`). Ver "Trabajar con los
especialistas" más abajo.

## Carpeta de pruebas

Los flows y nodos custom de prueba viven en un directorio de sandbox **fuera del
repo** (configúralo en tu máquina, p.ej. `~/rayflow_sandbox/`):
- `flows/` — flows JSON de prueba (no en el repo de Rayflow)
- `custom_nodes/` — nodos custom de prueba del usuario

Al lanzar el servidor desde el sandbox, Ray y el editor los detectan automáticamente:
```bash
cd <tu-directorio-sandbox>
rayflow serve --port 8000
```

## Comandos de desarrollo

```bash
# Instalar en modo editable
pip install -e .

# Lanzar el servidor (editor visual + API REST)
rayflow serve --port 8000
# o equivalentemente:
python -m rayflow serve --port 8000

# Con flows precargados
rayflow serve --file flows/suma.json --port 8000

# Con logs de actores Ray (prints incluidos) redirigidos a consola
rayflow serve --port 8000 --debug

# Ejecutar tests
pip install -e ".[dev]"
pytest tests/

# Type-check el backend (ty, de Astral — muy rápido, ~0.3s para todo rayflow/)
ty check rayflow/

# Activar los git hooks de pre-commit (una sola vez por clon; ver .pre-commit-config.yaml)
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

`ty` marca falsos positivos conocidos en archivos con actores Ray (`@ray.remote`
inyecta `.remote()` en tiempo de ejecución, invisible para el analizador estático) —
son ruido esperado, no bugs reales. Los hooks `ty_diff_pre.py`/`ty_diff_post.py`
en `.claude/hooks/` ya filtran ese ruido automáticamente comparando diagnósticos
antes/después de cada edit; correr `ty check` a mano es útil para una revisión
manual amplia del estado actual de tipos.

El servidor sirve:
- Editor visual en `http://localhost:8000/editor`
- API REST en `http://localhost:8000/flows`
- Health check en `http://localhost:8000/health`

## Arquitectura general

```
Editor visual (browser) ←→ FastAPI (rayflow/server.py) ←→ Ray actors/tasks
         ↓                           ↓
  editor/frontend/ (React+Vite)   rayflow/engine/executor.py
   → build a editor/static/dist/  (lo que sirve el server)
```

### Principios de diseño

1. **Un nodo = una clase Python** decorada con `@ray_node` o `@engine_node`
2. **Namespace plano**: `flatten()` expande subflows inline en build time (ids tipo `padre/sub/nodo`)
3. **Ejecución secuencial de control, paralela de datos**: exec pins son secuenciales; data pins se evalúan en paralelo vía Ray
4. **Tipos siempre strings canónicos**: `"int"`, `"str"`, `"list[str]"` — nunca clases Python

## Trabajar con los especialistas de cada sistema

Cada sistema del repo (ver "Índice de sistemas" al final de este documento, o
`rayflow_file_map.json` directamente) tiene un subagente
`rayflow-<sistema>-specialist` regenerado en cada commit con el detalle real
de ese sistema: descripciones de archivos, dependencias entre sistemas, las
claims de `RAYFLOW_SOURCE_OF_TRUTH.json` cuya evidencia cae ahí, e issues
abiertos que lo mencionan.

- **Para trabajo o preguntas acotadas a un sistema, delegá con la tool Agent**
  (`subagent_type: rayflow-<sistema>-specialist`) en lugar de leer los
  archivos del sistema vos mismo — el especialista ya tiene el contexto
  cargado y curado.
- **Para conversar con un especialista ya spawneado — preguntas de
  seguimiento, aclaraciones, "¿y si...?"** — no vuelvas a spawnearlo con
  Agent (un Agent nuevo arranca sin memoria de la conversación previa).
  Usá **SendMessage** dirigido al nombre/id del agente ya activo: retoma la
  misma sesión con todo su contexto, así que puede responder directo sin
  releer archivos. Preferí este camino sobre investigar vos mismo cuando ya
  hay un especialista de ese sistema conversando en la sesión.

## Macro-agentes (grupos de sistemas)

Los 21 sistemas se agrupan además en 4 **macrosistemas** (campo
`macrosistemas` de `rayflow_file_map.json`, muchos-a-muchos — `packaging`
cae tanto en `interfaces` como en `frontend`): `runtime-core`, `interfaces`,
`frontend`, `repo-quality`. Cada uno tiene un
`.claude/agents/rayflow-macro-<macrosistema>.md` regenerado en cada commit
(`scripts/generate_macro_agents.py`, hook `macro-agents-generate`).

El modelo de delegación tiene dos niveles con garantías distintas:

- **`rayflow-main` → los 4 macro-agents**: esto es enforcement técnico real.
  `rayflow-main` corre como hilo principal (`.claude/settings.json` fija
  `"agent": "rayflow-main"`) y su toolset no incluye Read/Grep/Glob/Edit/Bash
  propios — solo puede delegar.
- **Macro-agent → especialistas de su macrosistema**: esto es convención
  documentada, no bloqueo técnico. Un macro-agent spawneado como subagente
  (`tools: Agent, SendMessage`) técnicamente podría invocar cualquier
  subagente del repo — Claude Code no soporta restringir programáticamente
  qué invoca un subagente ya spawneado, solo el hilo principal tiene esa
  restricción real. Cada macro-agent lista su "agenda de contactos" (los
  especialistas de sus sistemas miembro + los otros 3 macro-agents) con esa
  aclaración explícita.
