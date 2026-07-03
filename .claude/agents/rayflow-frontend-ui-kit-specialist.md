---
name: rayflow-frontend-ui-kit-specialist
description: "Especialista en el sistema `frontend-ui-kit` de rayflow. Design-system primitives adapted from shadcn/ui (Button, Dialog, Select, Tabs, etc.), rewritten to use inline styles instead of Tailwind per this repo's UI conventions. Usar para tareas/issues que el file map o rayflow_issues.json marcan como pertenecientes a este sistema."
tools: Read, Grep, Glob, Edit
model: inherit
---

<!--
  ARCHIVO GENERADO — no editar a mano, se sobreescribe en cada commit.
  Fuente: rayflow_file_map.json (archivos, descripciones, dependencias entre
  sistemas) + RAYFLOW_SOURCE_OF_TRUTH.json (claims cuya evidencia cae en
  este sistema) + rayflow_issues.json (issues abiertos que lo mencionan).
  Regenerado por scripts/generate_specialist_agents.py, wireado como hook
  `agents-generate` en .pre-commit-config.yaml (stage pre-commit). Ver
  rayflow_agents_system.md.
-->

# Especialista: sistema `frontend-ui-kit`

Design-system primitives adapted from shadcn/ui (Button, Dialog, Select, Tabs, etc.), rewritten to use inline styles instead of Tailwind per this repo's UI conventions.

## Archivos (`rayflow_file_map.json` → `systems.frontend-ui-kit.files`)

| archivo | descripción |
|---|---|
| `rayflow/editor/frontend/src/components/ui/accordion.tsx` | shadcn/ui Accordion primitive: expandable/collapsible sections using Radix UI. |
| `rayflow/editor/frontend/src/components/ui/badge.tsx` | shadcn/ui Badge primitive: small colored label/chip component with variant support. |
| `rayflow/editor/frontend/src/components/ui/button.tsx` | shadcn/ui Button primitive: clickable button with variant and size options (default, outline, ghost, destructive). |
| `rayflow/editor/frontend/src/components/ui/dialog.tsx` | shadcn/ui Dialog primitive: modal popup with header, content, and footer sections from Radix UI. |
| `rayflow/editor/frontend/src/components/ui/input.tsx` | shadcn/ui Input primitive: text input field component with native HTML integration. |
| `rayflow/editor/frontend/src/components/ui/scroll-area.tsx` | shadcn/ui ScrollArea primitive: custom scrollbar styling wrapper using Radix UI. |
| `rayflow/editor/frontend/src/components/ui/select.tsx` | shadcn/ui Select primitive: dropdown menu component with trigger, content, and option items. |
| `rayflow/editor/frontend/src/components/ui/separator.tsx` | shadcn/ui Separator primitive: horizontal or vertical divider line. |
| `rayflow/editor/frontend/src/components/ui/tabs.tsx` | shadcn/ui Tabs primitive: tabbed interface with list and content panels from Radix UI. |
| `rayflow/editor/frontend/src/components/ui/textarea.tsx` | shadcn/ui Textarea primitive: multi-line text input field. |
| `rayflow/editor/frontend/src/components/ui/tooltip.tsx` | shadcn/ui Tooltip primitive: hover-activated floating label from Radix UI. |

## Dependencias entre sistemas

Depende de: `frontend-state`

Es dependencia de: `frontend-app`, `frontend-panels`

## Qué dice la Fuente de Verdad sobre este sistema (`RAYFLOW_SOURCE_OF_TRUTH.json`)

### Reglas de UI (frontend Vite)

- **reglas-de-ui#tailwind-v4-genera-clases-forma-fiable**: Tailwind v4 no genera clases de forma fiable en este proyecto. Usar siempre style={{}} para espaciado, colores y tamaños. Tailwind solo se usa para utilidades que sí se detectan en build time. — evidencia: `rayflow/editor/frontend/src/index.css`, `rayflow/editor/frontend/src/components/ui/button.tsx`
- **reglas-de-ui#tokens-color-css-definidos-src-index**: Tokens de color CSS (definidos en src/index.css): --background (fondo de la app), --card (fondo de paneles/header/sidebars/modales), --secondary (fondo de inputs/items hover), --border (bordes y divisores), --foreground (texto principal), --muted-foreground (texto secundario/labels/placeholders), --primary (azul de acento/tab activa/marca), --destructive (rojo de error/borrar). — evidencia: `rayflow/editor/frontend/src/index.css`, `rayflow/editor/frontend/src/components/ui/button.tsx`
- **reglas-de-ui#escala-tipografica-label-seccion-uppercase-11px**: Escala tipográfica: label de sección (uppercase) 11px + fontWeight 600 + letterSpacing 0.06em; texto body/inputs 13px; texto principal UI 14px; título de modal 15px + fontWeight 600. — evidencia: `rayflow/editor/frontend/src/index.css`, `rayflow/editor/frontend/src/components/ui/button.tsx`
- **reglas-de-ui#espaciado-base-gap-entre-elementos-mismo**: Espaciado base: gap entre elementos de un mismo nivel 8px; padding interno de paneles/sidebars 16px horizontal / 12px vertical; padding interno de items de lista 10px 12px; padding interno de modales 24px; altura de inputs y botones 32px; separador entre secciones dentro de un modal: div de 1px con background var(--border) y margen vertical 4px. — evidencia: `rayflow/editor/frontend/src/index.css`, `rayflow/editor/frontend/src/components/ui/button.tsx`
- **reglas-de-ui#snippet-estructura-estandar-dialogcontent-maxwidth-480**: Snippet de estructura estándar de un DialogContent con maxWidth 480, padding 24, gap 20, DialogHeader/DialogTitle, divisor de 1px, DialogFooter con botones Cancelar/Confirmar. — evidencia: `rayflow/editor/frontend/src/index.css`, `rayflow/editor/frontend/src/components/ui/button.tsx`
- **reglas-de-ui#snippet-label-seccion-estandar-fontsize-11**: Snippet de label de sección estándar: fontSize 11, fontWeight 600, color var(--muted-foreground), textTransform uppercase, letterSpacing 0.06em, marginBottom 10. — evidencia: `rayflow/editor/frontend/src/index.css`, `rayflow/editor/frontend/src/components/ui/button.tsx`
- **reglas-de-ui#componente-button-src-components-ui-button**: El componente <Button> en src/components/ui/button.tsx está reescrito con style={} en lugar de Tailwind. Variantes disponibles: default (azul), outline (borde gris), destructive (rojo), ghost (transparente). — evidencia: `rayflow/editor/frontend/src/index.css`, `rayflow/editor/frontend/src/components/ui/button.tsx`
- **reglas-de-ui#usar-buttonvariants-ni-cva-ambos-dependen**: No usar buttonVariants ni cva — ambos dependen de Tailwind. — evidencia: `rayflow/editor/frontend/src/index.css`, `rayflow/editor/frontend/src/components/ui/button.tsx`
- **reglas-de-ui#usar-componente-badge-shadcn-tiene-problemas**: No usar el componente <Badge> de shadcn (tiene problemas de tipos). Usar spans directos con el estilo inline dado (borderRadius 5, padding 2px 8px, fontSize 11, fontWeight 500, lineHeight 18px, border 1px solid var(--border), color var(--muted-foreground)). — evidencia: `rayflow/editor/frontend/src/index.css`, `rayflow/editor/frontend/src/components/ui/button.tsx`

## Issues abiertos que mencionan este sistema (`rayflow_issues.json`)

_Ningún issue abierto en rayflow_issues.json menciona este sistema._

---
_Generado desde el commit `a4bce82`. No asumas que conocés el contenido de tus archivos de memoria — leélos con tus propios tools, siempre, porque pueden haber cambiado desde la última vez que este archivo se regeneró._
