import click

from rayflow import __version__


@click.group()
@click.version_option(version=__version__)
def cli():
    """RayFlow - Visual flow editor with Ray distributed execution"""
    pass


@cli.command()
@click.option("--file", "-f", "files", multiple=True, required=False, metavar="PATH",
              help="Flow JSON a servir. Repetible para varios flows.")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host del servidor")
@click.option("--port", "-p", default=8000, show_default=True, help="Puerto del servidor")
@click.option("--nodes-dir", "nodes_dirs", multiple=True, metavar="DIR",
              help="Directorio extra de nodos de usuario. Repetible.")
@click.option("--debug", is_flag=True, default=False,
              help="Redirige los logs de los actores Ray (prints incluidos) a la consola.")
def serve(files, host, port, nodes_dirs, debug):
    """Lanza el servidor REST y el editor visual."""
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
