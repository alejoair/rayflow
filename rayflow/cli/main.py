import click


@click.group()
@click.version_option(version="0.1.0")
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
def serve(files, host, port, nodes_dirs):
    """Lanza el servidor REST y el editor visual."""
    from rayflow.server import serve as _serve
    _serve(
        sources=list(files),
        host=host,
        port=port,
        extra_node_dirs=list(nodes_dirs) or None,
    )
