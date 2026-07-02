"""REST API for serving flows as HTTP endpoints.

`rayflow serve --file flow.json` starts a FastAPI server that loads each
served flow into Ray once at startup and exposes it under
`/flows/{name}/run`. Every request reuses that same persistent graph
(engine/GraphState/queue actors) rather than reloading per request —
concurrent/repeated requests are isolated by their own run_id/RunContext,
not by recreating the graph, which is how the engine is designed to work
(see CLAUDE.md's concurrency notes on FlowEngine.execute()).

`/flows/{name}/run` is also the single execution endpoint for flows managed
by the editor (in `flows/`, not passed via `--file`) — it loads them into
Ray on demand the first time they're run instead of requiring a separate
editor-only endpoint. The editor frontend calls this same route.

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
from rayflow.build.validator import build, BuiltFlow


class ServedFlow:
    """A loaded, validated flow, ready to run per request."""

    def __init__(self, source: str | Path | dict, flow_def: FlowDef,
                 built: BuiltFlow | None = None):
        # Keeps the original source (path or dict) to re-run the flow per
        # request via run_async — NOT its str(), which would lose an inline dict.
        self.source = source
        self.flow_def = flow_def
        # The validated BuiltFlow (kept so create_app can read the entry
        # node's meta — e.g. to discover a declared `frontend` bundle to
        # mount at /flows/{name}/ui). None when ServedFlow is constructed
        # without building (some tests).
        self.built = built

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
        built = build(flow_def, catalog)  # early validation — raises BuildError on failure
        if flow_def.name in served:
            raise ValueError(
                f"Two flows share the name '{flow_def.name}': "
                f"'{served[flow_def.name].source_label}' and '{src}'"
            )
        served[flow_def.name] = ServedFlow(src, flow_def, built)
    return served


def _mount_flow_ui(app, sf: "ServedFlow", logger: logging.Logger) -> None:
    """Mounts the entry node's `frontend` bundle at /flows/{name}/ui, if any.

    No-op when the entry didn't declare `frontend` (the common case: OnStart,
    OnEvent without a UI) or when the declared bundle directory doesn't exist
    on disk (logged as a warning so a missing bundle doesn't crash startup).
    """
    if sf.built is None:
        return
    entry = sf.built.nodes.get(sf.built.entry_node_id)
    if entry is None:
        return
    frontend = entry.meta.frontend
    if not frontend:
        return
    py_class = entry.meta.py_class
    try:
        node_dir = Path(inspect.getfile(py_class)).parent
    except (TypeError, OSError):
        return
    bundle_dir = node_dir / frontend
    if not bundle_dir.is_dir():
        logger.warning(
            "Flow '%s': entry node '%s' declared frontend='%s' but the "
            "bundle directory '%s' does not exist; /flows/%s/ui will not be served.",
            sf.name, entry.meta.name, frontend, bundle_dir, sf.name,
        )
        return
    app.mount(
        f"/flows/{sf.name}/ui",
        StaticFiles(directory=str(bundle_dir), html=True),
        name=f"ui-{sf.name}",
    )


def create_app(served: dict[str, ServedFlow]):
    """Builds the FastAPI app with the endpoints for the served flows."""
    from pathlib import Path as _Path
    from fastapi import Body, FastAPI, HTTPException
    from rayflow import __version__
    from rayflow.api import load as load_api, is_flow_loaded, reconnect_async
    from rayflow.editor.routes import router as editor_router, run_flow_response, wants_stream
    from rayflow.editor.custom_nodes_routes import router as custom_nodes_router
    from rayflow.editor.storage import get_flow_dict

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

    # Mount a frontend bundle at /flows/{name}/ui for any served flow whose
    # entry node declared `frontend`. A flow has exactly one entry node
    # (_find_entry), so there is at most one bundle per flow — no slug
    # needed. The bundle is a static directory sibling to the node's source
    # file; it talks to the flow over the normal /flows/{name}/run endpoint.
    _logger = logging.getLogger("rayflow")
    for _sf in served.values():
        _mount_flow_ui(app, _sf, _logger)

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
    async def run_flow(request: Request, name: str, inputs: Any = Body(default=None)):
        """The single run endpoint for any flow — pre-loaded served flows
        (from `rayflow serve --file`) and editor-managed flows in `flows/`
        alike. Set `Accept: text/event-stream` for the SSE event stream
        (same one the editor frontend consumes); otherwise this returns a
        single JSON response once the flow finishes.
        """
        if inputs is None:
            inputs = {}
        if not isinstance(inputs, dict):
            raise HTTPException(
                status_code=400, detail="Body must be a JSON object of inputs"
            )

        # A served flow (loaded once at startup, see create_app above) reuses
        # that persistent graph. Otherwise fall back to an editor-managed
        # flow (flows/ directory), loading it into Ray on demand if needed.
        if served.get(name) is None:
            data = get_flow_dict(name)
            if data is None:
                raise HTTPException(status_code=404, detail=f"Flow '{name}' not found")
            if not is_flow_loaded(name):
                import asyncio
                from functools import partial
                loop = asyncio.get_event_loop()
                try:
                    await loop.run_in_executor(None, partial(load_api, data))
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Error loading the flow: {e}")

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
        """Reconnects to an active SSE run without relaunching execution.

        Useful when the client loses connection while the flow is still
        running. Returns the pending events from the moment of reconnection.
        """
        import json
        from fastapi.responses import StreamingResponse

        if not is_flow_loaded(name):
            raise HTTPException(status_code=404, detail=f"Flow '{name}' is not loaded")

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
