import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from rayflow.server.routes import router


app = FastAPI(title="RayFlow API", version="0.1.0")

# CORS middleware to allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Editor files are included in the package
EDITOR_PATH = Path(__file__).parent.parent.parent / "editor"


@app.get("/components/{filename}")
async def serve_component(filename: str):
    """Serve component files"""
    component_file = EDITOR_PATH / "components" / filename
    if component_file.exists() and component_file.suffix == ".js":
        return FileResponse(component_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Component not found")


@app.get("/app.js")
async def serve_app_js():
    """Serve main app.js file"""
    app_file = EDITOR_PATH / "app.js"
    if app_file.exists():
        return FileResponse(app_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="App file not found")

# Include routes
app.include_router(router, prefix="/api")


@app.get("/")
def root():
    """Serve the editor HTML"""
    html_file = EDITOR_PATH / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    return {"message": "RayFlow API", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


def get_working_directory() -> Path:
    """Get the working directory where rayflow was called"""
    cwd = os.environ.get("RAYFLOW_CWD")
    if cwd:
        return Path(cwd)
    return Path.cwd()
