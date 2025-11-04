import click
import subprocess
import sys
import os
from pathlib import Path


@click.command()
@click.option('--port', default=8000, help='Server port')
@click.option('--working-path', type=click.Path(exists=True, file_okay=False, dir_okay=True), 
              help='Working directory for nodes and flows (default: current directory)')
def create(port, working_path):
    """Launch the RayFlow editor (backend serves frontend)"""

    # Get the directory where rayflow is installed
    rayflow_root = Path(__file__).parent.parent.parent.parent
    editor_path = rayflow_root / "editor"

    if not editor_path.exists():
        click.echo(f"Error: Editor directory not found at {editor_path}")
        sys.exit(1)

    # Working directory: use --working-path if provided, otherwise current directory
    cwd = Path(working_path) if working_path else Path.cwd()

    click.echo(f"🚀 Starting RayFlow editor...")
    click.echo(f"   Working directory: {cwd}")
    click.echo(f"   Server: http://localhost:{port}")
    click.echo(f"   Editor: http://localhost:{port}")

    # Start backend server (it will serve the frontend HTML too)
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "rayflow.server.app:app",
         "--host", "0.0.0.0", "--port", str(port), "--reload"],
        env={**os.environ, "RAYFLOW_CWD": str(cwd), "RAYFLOW_EDITOR_PATH": str(editor_path)}
    )

    try:
        # Wait for process
        backend_process.wait()
    except KeyboardInterrupt:
        click.echo("\n🛑 Shutting down RayFlow...")
        backend_process.terminate()
        backend_process.wait()
