# Estructura de Archivos - RayFlow

```
rayflow/
│
├── rayflow/                          # Paquete Python principal
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── node.py
│   │   ├── orchestrator.py
│   │   ├── variable_store.py
│   │   ├── graph.py
│   │   └── executor.py
│   │
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── base/
│   │   │   ├── __init__.py
│   │   │   ├── start.py
│   │   │   ├── return_node.py
│   │   │   └── debug.py
│   │   │
│   │   ├── variables/
│   │   │   ├── __init__.py
│   │   │   ├── get_variable.py
│   │   │   └── set_variable.py
│   │   │
│   │   ├── math/
│   │   │   ├── __init__.py
│   │   │   ├── add.py
│   │   │   ├── subtract.py
│   │   │   ├── multiply.py
│   │   │   └── divide.py
│   │   │
│   │   ├── logic/
│   │   │   ├── __init__.py
│   │   │   ├── if_else.py
│   │   │   ├── compare.py
│   │   │   └── branch.py
│   │   │
│   │   ├── string/
│   │   │   ├── __init__.py
│   │   │   ├── concat.py
│   │   │   ├── format.py
│   │   │   └── split.py
│   │   │
│   │   ├── io/
│   │   │   ├── __init__.py
│   │   │   ├── http_request.py
│   │   │   ├── file_read.py
│   │   │   ├── file_write.py
│   │   │   └── database.py
│   │   │
│   │   └── data/
│   │       ├── __init__.py
│   │       ├── json_parse.py
│   │       ├── dict_get.py
│   │       └── list_operations.py
│   │
│   ├── server/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── routes.py
│   │   ├── schema.py
│   │   ├── middleware.py
│   │   └── models.py
│   │
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       ├── run.py
│   │       ├── create.py
│   │       ├── list_nodes.py
│   │       ├── new_node.py
│   │       └── validate.py
│   │
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── schema_validator.py
│   │   ├── type_checker.py
│   │   └── graph_validator.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── logger.py
│   │   └── serialization.py
│   │
│   └── exceptions.py
│
├── editor/
│   ├── package.json
│   ├── vite.config.js
│   ├── tsconfig.json
│   ├── index.html
│   │
│   ├── public/
│   │   ├── favicon.ico
│   │   └── logo.svg
│   │
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       │
│       ├── components/
│       │   ├── Canvas/
│       │   │   ├── NodeCanvas.tsx
│       │   │   ├── Node.tsx
│       │   │   ├── Connection.tsx
│       │   │   └── ControlPanel.tsx
│       │   │
│       │   ├── Sidebar/
│       │   │   ├── NodeLibrary.tsx
│       │   │   ├── Inspector.tsx
│       │   │   └── CodeEditor.tsx
│       │   │
│       │   ├── Toolbar/
│       │   │   ├── Toolbar.tsx
│       │   │   └── ActionButtons.tsx
│       │   │
│       │   └── Common/
│       │       ├── Button.tsx
│       │       ├── Input.tsx
│       │       └── Modal.tsx
│       │
│       ├── hooks/
│       │   ├── useGraph.ts
│       │   ├── useNodes.ts
│       │   ├── useConnections.ts
│       │   └── useNodeLibrary.ts
│       │
│       ├── store/
│       │   ├── graphStore.ts
│       │   ├── editorStore.ts
│       │   └── uiStore.ts
│       │
│       ├── services/
│       │   ├── api.ts
│       │   ├── nodeLoader.ts
│       │   ├── graphSaver.ts
│       │   └── executor.ts
│       │
│       ├── types/
│       │   ├── node.ts
│       │   ├── graph.ts
│       │   ├── connection.ts
│       │   └── editor.ts
│       │
│       ├── utils/
│       │   ├── validation.ts
│       │   ├── position.ts
│       │   └── colors.ts
│       │
│       └── styles/
│           ├── globals.css
│           └── theme.ts
│
├── .gitignore
├── pyproject.toml
├── setup.py
├── requirements.txt
├── LICENSE
└── README.md
```
