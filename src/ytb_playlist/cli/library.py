# SPDX-License-Identifier: GPL-3.0-only
"""The `tag`, `cover` and `rename` commands, for files already in a playlist folder."""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.text import Text

from ytb_playlist.cli import common, exit_codes
from ytb_playlist.core import library
from ytb_playlist.core.library import LibraryError, LocalItem
from ytb_playlist.core.state import StateError
from ytb_playlist.naming import UnsafeIdError
from ytb_playlist.tagging.apply import CoverMode, TaggingError, replace_cover, tag_file

Paths = Annotated[list[Path], typer.Argument(exists=True, help="Files or playlist folders.")]
CoverOption = Annotated[CoverMode | None, typer.Option("--cover", help="Cover shape.")]
ITEM_ERRORS = (LibraryError, TaggingError, StateError, UnsafeIdError, OSError)


def _say(message: str, style: str = "") -> None:
    Console().print(Text(message, style=style), soft_wrap=True)


def _for_each_item(paths: list[Path], action: Callable[[LocalItem], None]) -> None:
    files = library.media_files(paths)
    if not files:
        common.print_error("no MP3 or MP4 files found")
        raise typer.Exit(exit_codes.USAGE_ERROR)
    failed = False
    for path in files:
        try:
            action(library.load_item(path))
        except ITEM_ERRORS as error:
            common.print_error(error)
            failed = True
    if failed:
        raise typer.Exit(exit_codes.PARTIAL)


def tag_command(paths: Paths, cover: CoverOption = None) -> None:
    """Write tags and the cover from the saved metadata. Nothing is downloaded."""

    def tag(item: LocalItem) -> None:
        for warning in tag_file(item.path, item.info, item.thumbnail, cover):
            _say(warning, "yellow")
        library.mark_tagged(item)
        _say(f"tagged {item.path.name}", "green")

    _for_each_item(paths, tag)


def cover_command(paths: Paths, cover: CoverOption = None) -> None:
    """Embed the saved thumbnail again, keeping every other tag."""

    def embed(item: LocalItem) -> None:
        if item.thumbnail is None:
            raise LibraryError(f"{item.path.name}: no saved thumbnail")
        replace_cover(item.path, item.thumbnail, cover)
        _say(f"cover updated: {item.path.name}", "green")

    _for_each_item(paths, embed)


def rename_command(
    paths: Paths,
    dry_run: Annotated[bool, typer.Option(help="Show the new names; change nothing.")] = False,
) -> None:
    """Apply the naming rules. Old names are kept in a log beside the state file."""

    def rename(item: LocalItem) -> None:
        target = library.rename_target(item)
        if target is None:
            _say(f"already named: {item.path.name}")
            return
        if not dry_run:
            library.apply_rename(item, target, date.today())
        _say(f"{item.path.name} -> {target.name}")

    _for_each_item(paths, rename)
