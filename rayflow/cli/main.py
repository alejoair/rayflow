from pathlib import Path

import click

from rayflow import __version__


@click.group()
@click.version_option(version=__version__)
def cli():
    """RayFlow - Visual flow editor with Ray distributed execution"""
    pass


@cli.group()
def install():
    """Installs optional tooling into the current working directory."""
    pass


def _claude_tools_dir() -> Path:
    return Path(__file__).parent.parent / "claude_tools"


def _copy_tree(src: Path, dst: Path, force: bool) -> list[tuple[str, str]]:
    """Copies every file under src into dst, preserving relative structure.
    Returns [(relative_path, status)]; status is "installed", "overwritten",
    or "skipped (already exists)" — the last one only when force is False."""
    results = []
    for path in sorted(src.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        target = dst / rel
        existed = target.exists()
        if existed and not force:
            results.append((str(rel), "skipped (already exists, use --force to overwrite)"))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        results.append((str(rel), "overwritten" if existed else "installed"))
    return results


@install.command("claude-tools")
@click.option("--force", is_flag=True, default=False,
              help="Overwrite skill/agent files that already exist. Never overwrites an existing .mcp.json.")
def install_claude_tools(force):
    """Installs Claude Code skills and a debugging subagent for building,
    testing, and debugging Rayflow flows and custom nodes in this directory —
    all wired to use Rayflow's MCP tools (rayflow serve exposes them at
    /mcp). Also drops a .mcp.json registering the server, unless one
    already exists (never overwritten, even with --force, since it may
    already register other MCP servers)."""
    templates = _claude_tools_dir()
    cwd = Path.cwd()

    for kind in ("skills", "agents"):
        for rel, status in _copy_tree(templates / kind, cwd / ".claude" / kind, force):
            click.echo(f"  .claude/{kind}/{rel}: {status}")

    mcp_json = cwd / ".mcp.json"
    if mcp_json.exists():
        click.echo("  .mcp.json: skipped (already exists — merge the 'rayflow' server manually if needed)")
    else:
        mcp_json.write_text((templates / "mcp.json").read_text(encoding="utf-8"), encoding="utf-8")
        click.echo("  .mcp.json: installed")

    click.echo(f"\nInstalled into {cwd}. Restart Claude Code (or open /mcp) to pick up the new server and skills.")


@cli.command()
@click.option("--file", "-f", "files", multiple=True, required=False, metavar="PATH",
              help="Flow JSON to serve. Repeatable for multiple flows.")
@click.option("--host", default="127.0.0.1", show_default=True, help="Server host")
@click.option("--port", "-p", default=8000, show_default=True, help="Server port")
@click.option("--nodes-dir", "nodes_dirs", multiple=True, metavar="DIR",
              help="Extra directory of user nodes. Repeatable.")
@click.option("--debug", is_flag=True, default=False,
              help="Redirects Ray actor logs (including prints) to the console.")
def serve(files, host, port, nodes_dirs, debug):
    """Launches the REST server and the visual editor."""
    import ray
    from rayflow.workspace import ensure_workspace, runtime_env
    from rayflow.events.bus import get_event_broker

    ensure_workspace()
    kwargs = {"ignore_reinit_error": True, "namespace": "rayflow", "log_to_driver": debug}
    env = runtime_env()
    if env is not None:
        kwargs["runtime_env"] = env
    ray.init(**kwargs)
    get_event_broker()

    try:
        from rayflow.server import serve as _serve
        _serve(
            sources=list(files),
            host=host,
            port=port,
            extra_node_dirs=list(nodes_dirs) or None,
        )
    finally:
        ray.shutdown()
