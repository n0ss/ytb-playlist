# SPDX-License-Identifier: GPL-3.0-only
"""The `fetch` command: run the engine and render its events with Rich."""

from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.progress import Progress, TaskID
from rich.text import Text

from ytb_playlist.backends.base import Backend, BackendError
from ytb_playlist.cli import common, exit_codes
from ytb_playlist.cli.playlist import load_or_exit
from ytb_playlist.core.fetch import FetchError, ItemsError, fetch
from ytb_playlist.core.models import (
    CoverSource,
    Event,
    FailureKind,
    FetchDone,
    FetchOptions,
    FetchPlanned,
    ItemFailed,
    ItemProgress,
    ItemSaved,
    ItemStarted,
    ItemTagged,
    MediaFormat,
)
from ytb_playlist.core.playlists import (
    PlaylistEntry,
    TagSettings,
    fetch_options,
    find_entry,
    tag_settings,
)
from ytb_playlist.core.state import FolderConflictError, FormatChangeError, StateError
from ytb_playlist.naming import UnsafeIdError
from ytb_playlist.tagging.apply import tag_file
from ytb_playlist.urls import UnsupportedUrlError, playlist_id

USAGE_ERRORS = (
    UnsupportedUrlError,
    ItemsError,
    FormatChangeError,
    FolderConflictError,
    StateError,
    UnsafeIdError,
)
NETWORK_ERRORS = (BackendError, FetchError)


class Quality(StrEnum):
    MAX = "max"


def _permanent_failures(count: int) -> str:
    return f"{count} permanent failure{'' if count == 1 else 's'}"


class _Renderer:
    def __init__(self, progress: Progress) -> None:
        self.progress = progress
        self.task: TaskID | None = None
        self.partial = False
        self.tagged = 0

    def __call__(self, event: Event) -> None:
        match event:
            case FetchPlanned():
                self._print(f"{event.folder.name}: {event.pending} new, {event.skipped} skipped")
            case ItemStarted():
                self.task = self.progress.add_task(event.video_id, total=100)
            case ItemProgress():
                if self.task is not None:
                    self.progress.update(self.task, completed=event.percent)
            case ItemSaved():
                self._end_task()
                self._print(f"saved {event.path.name}", "green")
            case ItemTagged():
                self.tagged += 1
                self._print(f"tagged {event.video_id}", "green")
                for warning in event.warnings:
                    self._print(warning, "yellow")
            case ItemFailed():
                self._end_task()
                permanent = event.kind == FailureKind.PERMANENT
                self._print(
                    f"{event.kind} failure, {event.video_id}: {event.reason}",
                    "yellow" if permanent else "red",
                )
            case FetchDone():
                self.partial = event.failed > 0
                permanent = _permanent_failures(event.skipped)
                if event.saved or event.failed or self.tagged:
                    self._print(
                        f"{event.saved} saved, {self.tagged} tagged, "
                        f"{event.failed} failed, {permanent}"
                    )
                else:
                    self._print(f"Nothing new, {permanent}")

    def _print(self, message: str, style: str = "") -> None:
        self.progress.console.print(Text(message, style=style), soft_wrap=True)

    def _end_task(self) -> None:
        if self.task is not None:
            self.progress.remove_task(self.task)
            self.task = None


def run_fetch(url: str, options: FetchOptions, settings: TagSettings, backend: Backend) -> int:
    """Fetch one playlist and return its exit code, so the next one can still run."""

    def tagger(path: Path, info: Mapping[str, object], thumbnail: Path | None) -> tuple[str, ...]:
        return tag_file(path, info, thumbnail, album=settings.album, genre=settings.genre)

    with Progress(transient=True) as progress:
        renderer = _Renderer(progress)
        try:
            fetch(url, options, backend, tagger, renderer, date.today())
        except USAGE_ERRORS as error:
            common.print_error(error)
            return exit_codes.USAGE_ERROR
        except NETWORK_ERRORS as error:
            common.print_error(error)
            return exit_codes.NETWORK_ERROR
        except OSError as error:
            common.print_error(error)
            return exit_codes.MISSING_DEPENDENCY
    return exit_codes.PARTIAL if renderer.partial else 0


def _saved_entry(entries: dict[str, PlaylistEntry], url: str) -> PlaylistEntry | None:
    """A bad URL has no saved entry; the fetch itself reports it."""
    try:
        return find_entry(entries, playlist_id(url))
    except UnsupportedUrlError:
        return None


def fetch_command(
    ctx: typer.Context,
    urls: Annotated[list[str], typer.Argument(help="Playlist URLs.")],
    media_format: Annotated[MediaFormat, typer.Option("--format", help="One format per playlist.")],
    out: Annotated[Path | None, typer.Option(help="Folder that holds the playlists.")] = None,
    items: Annotated[str | None, typer.Option(help="Positions, such as 1:10 or 1,3:4.")] = None,
    dry_run: Annotated[bool, typer.Option(help="Report what's new; write nothing.")] = False,
    cover: Annotated[CoverSource | None, typer.Option(help="Cover for each track.")] = None,
    max_height: Annotated[int | None, typer.Option(min=1, help="Video height cap.")] = None,
    quality: Annotated[
        Quality | None, typer.Option(help="max also allows formats Apple apps may refuse.")
    ] = None,
) -> None:
    """Download playlists into one folder each, skipping what's already there."""
    config = common.load_config_or_exit(ctx)
    backend = common.make_backend(config)
    root = out.expanduser().absolute() if out else None
    entries = load_or_exit()
    worst = 0
    for url in urls:
        entry = _saved_entry(entries, url)
        options = fetch_options(
            config,
            media_format,
            entry,
            output_root=root,
            items=items,
            dry_run=dry_run,
            cover=cover,
            max_height=max_height,
            quality_max=quality == Quality.MAX,
        )
        worst = max(worst, run_fetch(url, options, tag_settings(config, entry), backend))
    if worst:
        raise typer.Exit(worst)
