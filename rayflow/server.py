"""REST API for serving flows as HTTP endpoints.

`rayflow serve --file flow.json` starts a FastAPI server that loads each
served flow into Ray once at startup and exposes it under
`/flows/{name}/run`. Every request reuses that same persistent graph
(engine/GraphState/queue actors) rather than reloading per request —
concurrent/repeated requests are isolated by their own run_id/RunContext,
not by recreating the graph, which is how the engine is designed to work
(see CLAUDE.md's concurrency notes on FlowEngine.execute()).

`/flows/{name}/run` is also the single execution endpoint for flows managed
by the editor (in `flows/`, not passed via `--file`). Loading them into Ray
is the editor's responsibility: `POST /editor/flows/{name}/load` pre-validates
and registers them in rayflow.registry, after which `/run`, `/ui`, and the
rest of the served-flow contract apply uniformly. The editor frontend calls
this same route.

This is distinct from `rayflow.serve_events()` (api.py), which registers a
flow on the internal event bus.
"""
from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.staticfiles import StaticFiles

from rayflow.schema.loader import load_flow
from rayflow.schema.models import FlowDef
from rayflow.nodes.registry import get_catalog
from rayflow.build.validator import build, BuiltFlow, BuildError
from rayflow.engine.executor import LoadedFlow
from rayflow.registry import (
    ServedFlow,
    register_served,
    get_served,
    all_served,
    is_served,
)


def load_served_flows(sources: "list[str | Path | dict] | list[str | Path]",
                      extra_node_dirs: list[str | Path] | None = None
                      ) -> dict[str, ServedFlow]:
    """Loads and validates every flow at startup; indexes them by `name`.

    Fails early (before the server starts) if a flow doesn't build, or if
    two flows share the same name. Each successfully built flow is loaded
    into Ray (actors spawned) and registered in rayflow.registry.
    """
    catalog = get_catalog(extra_node_dirs)
    served: dict[str, ServedFlow] = {}
    for src in sources:
        sf = _build_and_load(src, catalog)
        if sf.name in served:
            raise ValueError(
                f"Two flows share the name '{sf.name}': "
                f"'{served[sf.name].source_label}' and '{src}'"
            )
        served[sf.name] = sf
        register_served(sf)
    return served


def _build_and_load(source: str | Path | dict, catalog=None) -> ServedFlow:
    """Pre-validates (build) and pre-loads (LoadedFlow.load) a flow.

    `build()` runs BEFORE any actor is spawned — so an invalid source fails
    loudly (BuildError) without leaking half-built state. On success, spawns
    actors via `LoadedFlow.load(built)` and returns a ServedFlow with `.loaded`
    populated. Does NOT register in rayflow.registry; the caller decides
    (load_served_flows registers in batch, api.load registers individually).
    """
    if catalog is None:
        catalog = get_catalog()
    flow_def = load_flow(source)
    built = build(flow_def, catalog)
    lf = LoadedFlow.load(built)
    return ServedFlow(source, flow_def, built, loaded=lf)


def _resolve_bundle_dir(sf: ServedFlow) -> Path | None:
    """Returns the entry node's `frontend` bundle directory, or None if the
    entry doesn't declare `frontend` or the bundle is missing on disk.

    None reasons are distinguishable by the caller via logging: a flow with no
    `frontend` is the common case (silent skip); a missing bundle directory
    is logged as a warning.
    """
    if sf.built is None:
        return None
    entry = sf.built.nodes.get(sf.built.entry_node_id)
    if entry is None:
        return None
    frontend = entry.meta.frontend
    if not frontend:
        return None
    py_class = entry.meta.py_class
    try:
        node_dir = Path(inspect.getfile(py_class)).parent
    except (TypeError, OSError):
        return None
    bundle_dir = node_dir / frontend
    if not bundle_dir.is_dir():
        return None
    return bundle_dir


def create_app(served: dict[str, ServedFlow] | None = None):
    """Builds the FastAPI app with the endpoints for the served flows.

    `served` is the initial dict (CLI `--file` flows), already registered in
    rayflow.registry by load_served_flows. Endpoints consult the registry in
    runtime (not this dict), so flows added later via POST /editor/flows/.../load
    are visible to /run, /ui, etc. without rebuilding the app.
    """
    from pathlib import Path as _Path
    from fastapi import Body, FastAPI, HTTPException
    from fastapi.responses import FileResponse
    from rayflow import __version__
    from rayflow.api import execute_async, reconnect_async
    from rayflow.editor.routes import router as editor_router, run_flow_response, wants_stream
    from rayflow.editor.custom_nodes_routes import router as custom_nodes_router

    # Build the MCP server before the app: its lifespan (the streamable-http
    # session manager) must be passed to FastAPI so it starts when mounted.
    mcp_app = None
    try:
        from rayflow.mcp.server import create_mcp
        mcp_app = create_mcp().http_app(path="/")
    except Exception as e:  # pragma: no cover - graceful degradation if fastmcp fails
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
        """Lists every served flow (from any origin: --file or editor /load)."""
        return {"flows": [sf.interface for sf in all_served()]}

    @app.get("/flows/{name}")
    async def flow_detail(name: str) -> dict[str, Any]:
        sf = get_served(name)
        if sf is None:
            raise HTTPException(status_code=404, detail=f"Flow '{name}' not found")
        return sf.interface

    @app.post("/flows/{name}/run")
    async def run_flow(request: Request, name: str, inputs: Any = Body(default=None)):
        """The single run endpoint. Requires the flow to be already served
        (loaded into Ray via CLI --file or POST /editor/flows/{name}/load).

        Returns 404 if the flow isn't served — there's no implicit on-demand
        loading. This is consistent with the unified contract: "served" =
        "explicitly loaded", and the editor's /load does the pre-validation
        + actor spawn before a request can hit /run.

        Set `Accept: text/event-stream` for the SSE event stream (the same
        one the editor frontend consumes); otherwise this returns a single
        JSON response once the flow finishes.
        """
        if not is_served(name):
            raise HTTPException(status_code=404, detail=f"Flow '{name}' is not served")
        if inputs is None:
            inputs = {}
        if not isinstance(inputs, dict):
            raise HTTPException(
                status_code=400, detail="Body must be a JSON object of inputs"
            )

        # Every flow's trigger IS this HTTP request — OnStart always exposes
        # headers/query/body/method (see _with_dynamic_pins in
        # build/validator.py), alongside whatever named inputs the flow
        # declares from the body. Reserved names win on collision.
        flow_inputs = {
            **inputs,
            "headers": dict(request.headers),
            "query": dict(request.query_params),
            "body": inputs,
            "method": request.method,
        }
        return await run_flow_response(name, flow_inputs, stream=wants_stream(request))

    @app.get("/flows/{name}/run/{run_id}/stream")
    async def reconnect_flow_run(name: str, run_id: str):
        """Reconnects to an active SSE run without relaunching execution."""
        import json
        from fastapi.responses import StreamingResponse

        if not is_served(name):
            raise HTTPException(status_code=404, detail=f"Flow '{name}' is not served")

        async def event_generator():
            try:
                async for evt in reconnect_async(name, run_id):
                    yield f"data: {json.dumps(evt)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'event': 'flow_error', 'error': str(e)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Frontend bundle: served dynamically per request. The handler looks up
    # the flow in the registry, resolves the entry node's `frontend` bundle
    # directory, and serves files from it via FileResponse. This unifies the
    # CLI (--file) and editor (/load) paths: any served flow whose entry
    # declared `frontend` exposes its UI here, and the UI disappears
    # automatically when the flow is unloaded (no mounts to tear down — the
    # registry lookup simply 404s).
    _logger = logging.getLogger("rayflow")

    @app.get("/flows/{name}/ui")
    @app.get("/flows/{name}/ui/{rest:path}")
    async def flow_ui(name: str, rest: str = ""):
        sf = get_served(name)
        if sf is None:
            raise HTTPException(status_code=404, detail=f"Flow '{name}' is not served")
        bundle_dir = _resolve_bundle_dir(sf)
        if bundle_dir is None:
            # Distinguish "no frontend declared" (common, silent) from
            # "bundle missing on disk" (warn).
            if sf.built is not None:
                entry = sf.built.nodes.get(sf.built.entry_node_id)
                if entry is not None and entry.meta.frontend:
                    _logger.warning(
                        "Flow '%s': entry node '%s' declared frontend='%s' but the "
                        "bundle directory does not exist; /flows/%s/ui not served.",
                        sf.name, entry.meta.name, entry.meta.frontend, sf.name,
                    )
            raise HTTPException(status_code=404, detail=f"Flow '{name}' has no UI bundle")

        # Resolve the requested path against the bundle directory. Empty rest
        # serves index.html (the route's html-root convention).
        rest = rest.strip("/")
        if not rest:
            target = bundle_dir / "index.html"
        else:
            target = (bundle_dir / rest).resolve()
            # Prevent path traversal outside bundle_dir.
            if not str(target).startswith(str(bundle_dir.resolve())):
                raise HTTPException(status_code=404, detail="Not found")
            if not target.is_file():
                raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(str(target))

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
