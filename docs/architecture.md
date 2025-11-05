# RayFlow - Arquitectura General

## Concepto

Sistema de ejecución de flujos visuales basado en nodos, inspirado en Blueprints de Unreal Engine, utilizando Ray como backend para ejecución distribuida de actores.

## Arquitectura General

```
┌─────────────────┐         ┌─────────────────┐
│  Editor Visual  │         │   Orquestador   │
│  (React + Vite) │────────▶│   (Ray Core)    │
└─────────────────┘         └─────────────────┘
        │                            │
        │                            ▼
        ▼                    ┌───────────────┐
┌─────────────┐             │  Ray Actors   │
│ miflujo.json│             │  (Nodos)      │
└─────────────┘             └───────────────┘
        ▲                            ▲
        │                            │
        └────────────────┬───────────┘
                   ┌─────▼─────┐
                   │  nodes/   │
                   │  *.py     │
                   └───────────┘
```

## Componentes Principales

### 1. Editor Visual (Frontend - React + Ant Design)
- Interface gráfica profesional con Ant Design 5.28.0
- Lee nodos disponibles desde `nodes/*.py`
- Permite instanciar múltiples veces el mismo nodo
- Editor de código integrado (Monaco/Ace) para modificar nodos
- Sistema de layout collapsible con Sider components
- Tree component para navegación de nodos con search integrado
- Inspector con Cards y Descriptions para propiedades
- Genera/guarda `miflujo.json`

### 2. Orquestador (Backend - Ray)
- Lee el grafo desde JSON
- Coordina la ejecución de nodos
- Gestiona señales de activación y flujo de datos
- Llama `.remote()` en actores según dependencias

### 3. Nodos (Ray Actors - Python)
- Actores Ray completamente independientes
- Templates reutilizables definidos en `nodes/*.py`
- Cada instancia tiene ID único en el grafo

## Estructura del Proyecto

```
rayflow/
├── rayflow/                    # Librería Python
│   ├── __init__.py
│   ├── node.py                 # Clase RayflowNode
│   ├── orchestrator.py         # Orquestador Ray
│   ├── graph.py                # Parser del JSON
│   └── cli.py                  # CLI (create, run)
│
├── editor/                     # Frontend React + Ant Design (CDN)
│   ├── components/
│   │   ├── Canvas.js          # Área de trabajo canvas
│   │   ├── NodeList.js        # Tree component con search integrado
│   │   ├── Inspector.js       # Cards y Descriptions para propiedades
│   │   └── Header.js          # Header component con controles
│   ├── app.js                 # App principal con Layout de Ant Design
│   └── index.html             # HTML con CDNs de React y Ant Design
│
├── nodes/                      # Nodos del usuario
│   ├── math/
│   │   ├── add.py
│   │   ├── multiply.py
│   │   └── divide.py
│   └── ...
│
└── flows/                      # Grafos guardados
    └── miflujo.json
```

## Ventajas de Ray

1. **Paralelismo transparente:** Nodos independientes se ejecutan en paralelo
2. **Distribución:** Puede escalar a múltiples máquinas
3. **Aislamiento:** Cada nodo es un actor independiente
4. **Manejo de estado:** Ray gestiona el ciclo de vida de actores
5. **Fault tolerance:** Ray puede reintentar nodos fallidos

## Principios de Diseño

### Simplicidad Pytónica
- Un nodo = un archivo `.py`
- Un flujo = un archivo `.json`
- Herencia simple de `RayflowNode`
- No magia, solo convención

### Separación de Responsabilidades
- **Nodos:** Solo procesan datos
- **Orquestador:** Solo coordina ejecución
- **Editor:** Solo construye/guarda JSON

### Extensibilidad
- Agregar nodo nuevo: crear archivo en `nodes/`
- Personalizar orquestador: subclasear y override
- Integrar con sistemas externos: crear nodos de I/O

## Resumen

**RayFlow** es un editor visual de flujos de datos basado en nodos, donde:

- Los nodos son **actores Ray independientes** definidos en archivos Python simples
- El **orquestador coordina** la ejecución basándose en señales y dependencias de datos
- El **editor visual** es solo una interfaz para construir el grafo JSON
- El sistema es **pytónico, simple y extensible**
- Escala naturalmente gracias a Ray

La arquitectura separa claramente la **definición** (archivos .py), la **composición** (JSON), y la **ejecución** (orquestador Ray).
