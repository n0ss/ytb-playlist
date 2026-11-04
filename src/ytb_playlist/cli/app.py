"""The Typer application."""

from importlib.metadata import version as package_version
from pathlib import Path
from typing import Annotated

import typer

from ytb_playlist.cli.doctor import doctor

app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)
app.command()(doctor)


def show_version(value: bool) -> None:
    if value:
        typer.echo(package_version("ytb-playlist"))
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    config: Annotated[Path | None, typer.Option(help="Config file to use.")] = None,
    version: Annotated[
        bool,
        typer.Option("--version", callback=show_version, is_eager=True, help="Show the version."),
    ] = False,
) -> None:
    """Download YouTube playlists as MP3 or MP4, named by date and tagged for Apple Music."""
    ctx.obj = config
