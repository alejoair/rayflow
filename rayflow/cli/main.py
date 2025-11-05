import click
from rayflow.cli.commands import create


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """RayFlow - Visual flow editor with Ray distributed execution"""
    pass


cli.add_command(create.create)


if __name__ == "__main__":
    cli()
