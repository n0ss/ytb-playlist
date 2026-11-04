"""The `info` command: a quick look at a playlist, with nothing downloaded."""

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from ytb_playlist.backends.base import BackendError
from ytb_playlist.cli import common, exit_codes
from ytb_playlist.urls import UnsupportedUrlError, playlist_url


def info(ctx: typer.Context, url: Annotated[str, typer.Argument(help="Playlist URL.")]) -> None:
    """Show a playlist's title, ID and number of items."""
    backend = common.make_backend(common.load_config_or_exit(ctx))
    try:
        playlist = backend.playlist_info(playlist_url(url))
    except UnsupportedUrlError as error:
        common.print_error(error)
        raise typer.Exit(exit_codes.USAGE_ERROR) from error
    except BackendError as error:
        common.print_error(error)
        raise typer.Exit(exit_codes.NETWORK_ERROR) from error

    table = Table(show_header=False, box=None)
    table.add_row("Title", Text(playlist.title))
    table.add_row("ID", Text(playlist.id))
    table.add_row("Items", str(playlist.item_count))
    Console().print(table)
