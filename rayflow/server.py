"""API REST para servir flows como endpoints HTTP.

`rayflow serve --file flow.json` levanta un servidor FastAPI que expone cada
flow cargado bajo `/flows/{name}/run`. Cada request ejecuta el flow de forma
aislada (un graph_id UUID por ejecución), así que requests concurrentes al
mismo flow no colisionan.

Esto es distinto de `rayflow.serve_events()` (api.py), que registra un flow en
el bus de eventos interno.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rayflow.schema.loader import load_flow
from rayflow.schema.models import FlowDef
from rayflow.nodes.registry import get_catalog
from rayflow.build.validator import build


class ServedFlow:
    """Un flow cargado y validado, listo para ejecutarse por request."""

    def __init__(self, source: str | Path | dict, flow_def: FlowDef):
        # Conserva el source original (ruta o dict) para re-ejecutar el flow por
        # request vía run_async — NO su str(), que perdería un dict inline.
        self.source = source
        self.flow_def = flow_def

    @property
    def source_label(self) -> str:
        """Etiqueta legible del origen (para mensajes de error)."""
        return self.source if isinstance(self.source, (str, Path)) else f"<dict:{self.name}>"

    @property
    def name(self) -> str:
        return self.flow_def.name

    @property
    def interface(self) -> dict[str, Any]:
        return {
            "name": self.flow_def.name,
            "version": self.flow_def.version,
            "inputs": dict(self.flow_def.inputs),
            "outputs": dict(self.flow_def.outputs),
        }


def load_served_flows(sources: list[str | Path | dict],
                      extra_node_dirs: list[str | Path] | None = None
                      ) -> dict[str, ServedFlow]:
    """Carga y valida cada flow al arrancar; los indexa por su `name`.

    Falla temprano (antes de levantar el servidor) si un flow no compila o si
    dos flows comparten el mismo nombre.
    """
    catalog = get_catalog(extra_node_dirs)
    served: dict[str, ServedFlow] = {}
    for src in sources:
        flow_def = load_flow(src)
        build(flow_def, catalog)  # validación temprana — lanza BuildError si falla
        if flow_def.name in served:
            raise ValueError(
                f"Dos flows comparten el nombre '{flow_def.name}': "
                f"'{served[flow_def.name].source_label}' y '{src}'"
            )
        served[flow_def.name] = ServedFlow(src, flow_def)
    return served


def create_app(served: dict[str, ServedFlow]):
    """Construye la app FastAPI con los endpoints sobre los flows servidos."""
    try:
        from fastapi import Body, FastAPI, HTTPException
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "La API REST requiere FastAPI y uvicorn. Instala con: "
            "pip install 'rayflow[serve]'"
        ) from e

    from rayflow.api import run_async

    app = FastAPI(title="Rayflow", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/flows")
    async def list_flows() -> dict[str, Any]:
        return {"flows": [sf.interface for sf in served.values()]}

    @app.get("/flows/{name}")
    async def flow_detail(name: str) -> dict[str, Any]:
        sf = served.get(name)
        if sf is None:
            raise HTTPException(status_code=404, detail=f"Flow '{name}' no encontrado")
        return sf.interface

    @app.post("/flows/{name}/run")
    async def run_flow(name: str, inputs: Any = Body(default=None)) -> dict[str, Any]:
        sf = served.get(name)
        if sf is None:
            raise HTTPException(status_code=404, detail=f"Flow '{name}' no encontrado")

        if inputs is None:
            inputs = {}
        if not isinstance(inputs, dict):
            raise HTTPException(
                status_code=400, detail="Body debe ser un objeto JSON de inputs"
            )

        # Ejecuta el flow sin bloquear el event loop: run_async devuelve un
        # ObjectRef de Ray, awaitable directamente. Cada ejecución se aísla por
        # su propio graph_id UUID.
        ref = run_async(sf.source, **inputs)
        try:
            outputs = await ref
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error ejecutando el flow: {e}")
        return outputs

    return app


def serve(sources: list[str | Path], host: str = "127.0.0.1", port: int = 8000,
          extra_node_dirs: list[str | Path] | None = None) -> None:
    """Carga los flows, valida, y levanta el servidor REST (bloqueante)."""
    try:
        import uvicorn
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "La API REST requiere FastAPI y uvicorn. Instala con: "
            "pip install 'rayflow[serve]'"
        ) from e

    served = load_served_flows(sources, extra_node_dirs)
    app = create_app(served)
    names = ", ".join(served) or "(ninguno)"
    print(f"Rayflow sirviendo {len(served)} flow(s): {names}")
    print(f"  -> http://{host}:{port}/flows")
    uvicorn.run(app, host=host, port=port)
