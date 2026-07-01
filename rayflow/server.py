"""REST API for serving flows as HTTP endpoints.

`rayflow serve --file flow.json` starts a FastAPI server that loads each
served flow into Ray once at startup and exposes it under
`/flows/{name}/run`. Every request reuses that same persistent graph
(engine/GraphState/queue actors) rather than reloading per request —
concurrent/repeated requests are isolated by their own run_id/RunContext,
not by recreating the graph, which is how the engine is designed to work
(see CLAUDE.md's concurrency notes on FlowEngine.execute()).

This is distinct from `rayflow.serve_events()` (api.py), which registers a
flow on the internal event bus.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rayflow.schema.loader import load_flow
from rayflow.schema.models import FlowDef
from rayflow.nodes.registry import get_catalog
from rayflow.build.validator import build


class ServedFlow:
    """A loaded, validated flow, ready to run per request."""

    def __init__(self, source: str | Path | dict, flow_def: FlowDef):
        # Keeps the original source (path or dict) to re-run the flow per
        # request via run_async — NOT its str(), which would lose an inline dict.
        self.source = source
        self.flow_def = flow_def

    @property
    def source_label(self) -> str:
        """Human-readable origin label (for error messages)."""
        return self.source if isinstance(self.source, (str, Path)) else f"<dict:{self.name}>"

    @property
    def name(self) -> str:
        return self.flow_def.name

    @property
    def interface(self) -> dict[str, Any]:
        return {
            "name": self.flow_def.name,
            "version": self.flow_def.version,
            "endpoint": f"/flows/{self.flow_def.name}/run",
            "method": "POST",
            "inputs": {
                name: {"type": type_str, "required": True}
                for name, type_str in self.flow_def.inputs.items()
            },
            "outputs": {
                name: {"type": type_str}
                for name, type_str in self.flow_def.outputs.items()
            },
        }


def load_served_flows(sources: list[str | Path | dict],
                      extra_node_dirs: list[str | Path] | None = None
                      ) -> dict[str, ServedFlow]:
    """Loads and validates every flow at startup; indexes them by `name`.

    Fails early (before the server starts) if a flow doesn't build, or if
    two flows share the same name.
    """
    catalog = get_catalog(extra_node_dirs)
    served: dict[str, ServedFlow] = {}
    for src in sources:
        flow_def = load_flow(src)
        build(flow_def, catalog)  # early validation — raises BuildError on failure
        if flow_def.name in served:
            raise ValueError(
                f"Two flows share the name '{flow_def.name}': "
                f"'{served[flow_def.name].source_label}' and '{src}'"
            )
        served[flow_def.name] = ServedFlow(src, flow_def)
    return served


def create_app(served: dict[str, ServedFlow]):
    """Builds the FastAPI app with the endpoints for the served flows."""
    from pathlib import Path as _Path
    from fastapi import Body, FastAPI, HTTPException
    from fastapi.staticfiles import StaticFiles
    from rayflow import __version__
    from rayflow.api import execute_async, load as load_api
    from rayflow.editor.routes import router as editor_router
    from rayflow.editor.custom_nodes_routes import router as custom_nodes_router

    # Load every served flow into Ray once, up front. load() always
    # destroys and recreates (safe to call unconditionally, even if a test
    # fixture calls create_app() repeatedly for the same flow name) — the
    # point is that /flows/{name}/run below does NOT reload per request,
    # so concurrent/repeated requests reuse this same persistent graph
    # instead of tearing it down and losing GraphState after every call.
    for _sf in served.values():
        load_api(_sf.source)

    # Build the MCP server before the app: its lifespan (the streamable-http
    # session manager) must be passed to FastAPI so it starts when mounted.
    mcp_app = None
    try:
        from rayflow.mcp.server import create_mcp
        mcp_app = create_mcp(served).http_app(path="/")
    except Exception as e:  # pragma: no cover - graceful degradation if fastmcp fails
        import logging
        logging.getLogger("rayflow").warning("MCP layer unavailable: %s", e)

    app = FastAPI(
        title="Rayflow",
        version=__version__,
        lifespan=mcp_app.lifespan if mcp_app is not None else None,
    )
    app.include_router(editor_router)
    app.include_router(custom_nodes_router)

    # Curated MCP tools at /mcp (streamable-http) for LLM agents.
    if mcp_app is not None:
        app.mount("/mcp", mcp_app)

    _dist_dir = _Path(__file__).parent / "editor" / "static" / "dist"
    if _dist_dir.exists():
        app.mount("/editor", StaticFiles(directory=_dist_dir, html=True), name="editor-static")

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
            raise HTTPException(status_code=404, detail=f"Flow '{name}' not found")
        return sf.interface

    @app.post("/flows/{name}/run")
    async def run_flow(name: str, inputs: Any = Body(default=None)) -> dict[str, Any]:
        sf = served.get(name)
        if sf is None:
            raise HTTPException(status_code=404, detail=f"Flow '{name}' not found")

        if inputs is None:
            inputs = {}
        if not isinstance(inputs, dict):
            raise HTTPException(
                status_code=400, detail="Body must be a JSON object of inputs"
            )

        # execute_async reuses the persistent graph loaded once at startup
        # (see create_app above) instead of reloading per request.
        result: dict[str, Any] = {}
        try:
            async for evt in execute_async(name, inputs):
                if evt.get("event") == "flow_done":
                    result = evt.get("result", {}) or {}
                elif evt.get("event") == "flow_error":
                    raise HTTPException(
                        status_code=500, detail=f"Error running the flow: {evt.get('error')}"
                    )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error running the flow: {e}")
        return result

    return app


def serve(sources: list[str | Path], host: str = "127.0.0.1", port: int = 8000,
          extra_node_dirs: list[str | Path] | None = None) -> None:
    """Loads the flows, validates them, and starts the REST server (blocking)."""
    import signal
    import uvicorn
    served = load_served_flows(sources, extra_node_dirs)
    app = create_app(served)
    names = ", ".join(served) or "(none)"
    print(f"Rayflow serving {len(served)} flow(s): {names}")
    print(f"  -> REST:   http://{host}:{port}/flows")
    print(f"  -> Editor: http://{host}:{port}/editor")
    print(f"  -> MCP:    http://{host}:{port}/mcp/  (tools for LLM agents)")

    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port))

    def _shutdown(signum, frame):
        server.should_exit = True

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    import asyncio
    asyncio.run(server.serve())
