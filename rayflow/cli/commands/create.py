import click
import subprocess
import sys
import os
from pathlib import Path


@click.command()
@click.option('--port', default=8000, help='Backend port')
@click.option('--frontend-port', default=5173, help='Frontend port')
def create(port, frontend_port):
    """Launch the RayFlow editor (backend + frontend)"""

    # Get the directory where rayflow is installed
    rayflow_root = Path(__file__).parent.parent.parent.parent
    editor_path = rayflow_root / "editor"

    if not editor_path.exists():
        click.echo(f"Error: Editor directory not found at {editor_path}")
        sys.exit(1)

    # Current working directory (where user called the command)
    cwd = Path.cwd()

    click.echo(f"🚀 Starting RayFlow editor...")
    click.echo(f"   Working directory: {cwd}")
    click.echo(f"   Backend: http://localhost:{port}")
    click.echo(f"   Frontend: http://localhost:{frontend_port}")

    # Start backend server
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "rayflow.server.app:app",
         "--host", "0.0.0.0", "--port", str(port), "--reload"],
        env={**os.environ, "RAYFLOW_CWD": str(cwd)}
    )

    # Start frontend dev server
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(frontend_port), "--host"],
        cwd=editor_path
    )

    try:
        # Wait for processes
        backend_process.wait()
        frontend_process.wait()
    except KeyboardInterrupt:
        click.echo("\n🛑 Shutting down RayFlow...")
        backend_process.terminate()
        frontend_process.terminate()
        backend_process.wait()
        frontend_process.wait()
