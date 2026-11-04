# SPDX-License-Identifier: GPL-3.0-only
"""The `playlist` commands: save, list and forget playlists."""

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from ytb_playlist.backends.base import BackendError
from ytb_playlist.cli import common, exit_codes
from ytb_playlist.config import default_config_dir
from ytb_playlist.core.models import CoverSource, MediaFormat
from ytb_playlist.core.playlists import (
    PlaylistEntry,
    PlaylistsError,
    add_playlist,
    load_playlists,
    remove_playlist,
)
from ytb_playlist.naming import clean_title
from ytb_playlist.urls import UnsupportedUrlError, playlist_url

playlist_app = typer.Typer(no_args_is_help=True)


def load_or_exit() -> dict[str, PlaylistEntry]:
    try:
        return load_playlists(default_config_dir())
    except PlaylistsError as error:
        common.print_error(error)
        raise typer.Exit(exit_codes.USAGE_ERROR) from error


@playlist_app.command("add")
def add(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="Playlist URL.")],
    media_format: Annotated[MediaFormat, typer.Option("--format", help="Fixed once saved.")],
    name: Annotated[str | None, typer.Option(help="Defaults to the playlist title.")] = None,
    album: Annotated[str | None, typer.Option(help="Album tag.")] = None,
    genre: Annotated[str | None, typer.Option(help="Genre tag.")] = None,
    cover: Annotated[CoverSource | None, typer.Option(help="Cover for each track.")] = None,
    max_height: Annotated[int | None, typer.Option(min=1, help="Video height cap.")] = None,
) -> None:
    """Save a playlist so `sync` can keep it up to date."""
    backend = common.make_backend(common.load_config_or_exit(ctx))
    try:
        canonical = playlist_url(url)
        info = backend.playlist_info(canonical)
        entry = PlaylistEntry(
            name or clean_title(info.title),
            canonical,
            info.id,
            media_format,
            album,
            genre,
            cover,
            max_height,
        )
        add_playlist(default_config_dir(), entry)
    except (UnsupportedUrlError, PlaylistsError) as error:
        common.print_error(error)
        raise typer.Exit(exit_codes.USAGE_ERROR) from error
    except BackendError as error:
        common.print_error(error)
        raise typer.Exit(exit_codes.NETWORK_ERROR) from error
    except OSError as error:
        common.print_error(error)
        raise typer.Exit(exit_codes.MISSING_DEPENDENCY) from error
    Console().print(Text(f"saved as {entry.name}", style="green"), soft_wrap=True)


@playlist_app.command("list")
def list_playlists() -> None:
    """Show saved playlists."""
    entries = load_or_exit()
    console = Console()
    if not entries:
        console.print("No saved playlists.")
        return
    table = Table("Name", "Format", "Playlist ID")
    for entry in entries.values():
        table.add_row(Text(entry.name), entry.format.value, Text(entry.playlist_id))
    console.print(table)


@playlist_app.command("remove")
def remove(name: Annotated[str, typer.Argument(help="Saved name.")]) -> None:
    """Forget a saved playlist. Its folder and files are left alone."""
    try:
        remove_playlist(default_config_dir(), name)
    except PlaylistsError as error:
        common.print_error(error)
        raise typer.Exit(exit_codes.USAGE_ERROR) from error
    except OSError as error:
        common.print_error(error)
        raise typer.Exit(exit_codes.MISSING_DEPENDENCY) from error
    Console().print(Text(f"removed {name}; its files were left in place"), soft_wrap=True)
