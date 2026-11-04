# SPDX-License-Identifier: GPL-3.0-only
"""The `fetch` command: run the engine and render its events with Rich."""

from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich.progress import Progress, TaskID
from rich.text import Text

from ytb_playlist.backends.base import Backend, BackendError
from ytb_playlist.cli import common, exit_codes
from ytb_playlist.core.fetch import FetchError, ItemsError, fetch
from ytb_playlist.core.models import (
    Event,
    FailureKind,
    FetchDone,
    FetchOptions,
    FetchPlanned,
    ItemFailed,
    ItemProgress,
    ItemSaved,
    ItemStarted,
    MediaFormat,
)
from ytb_playlist.core.state import FolderConflictError, FormatChangeError, StateError
from ytb_playlist.naming import UnsafeIdError
from ytb_playlist.urls import UnsupportedUrlError

USAGE_ERRORS = (
    UnsupportedUrlError,
    ItemsError,
    FormatChangeError,
    FolderConflictError,
    StateError,
    UnsafeIdError,
)
NETWORK_ERRORS = (BackendError, FetchError)


class _Renderer:
    def __init__(self, progress: Progress) -> None:
        self.progress = progress
        self.task: TaskID | None = None
        self.partial = False

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
            case ItemFailed():
                self._end_task()
                permanent = event.kind == FailureKind.PERMANENT
                self._print(
                    f"{event.kind} failure, {event.video_id}: {event.reason}",
                    "yellow" if permanent else "red",
                )
            case FetchDone():
                self.partial = event.failed > 0
                if event.saved or event.failed:
                    self._print(
                        f"{event.saved} saved, {event.failed} failed, {event.skipped} skipped"
                    )
                else:
                    self._print(f"Nothing new, {event.skipped} skipped")

    def _print(self, message: str, style: str = "") -> None:
        self.progress.console.print(Text(message, style=style), soft_wrap=True)

    def _end_task(self) -> None:
        if self.task is not None:
            self.progress.remove_task(self.task)
            self.task = None


def _fetch_one(url: str, options: FetchOptions, backend: Backend) -> int:
    with Progress(transient=True) as progress:
        renderer = _Renderer(progress)
        try:
            fetch(url, options, backend, renderer, date.today())
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


def fetch_command(
    ctx: typer.Context,
    urls: Annotated[list[str], typer.Argument(help="Playlist URLs.")],
    media_format: Annotated[MediaFormat, typer.Option("--format", help="One format per playlist.")],
    out: Annotated[Path | None, typer.Option(help="Folder that holds the playlists.")] = None,
    items: Annotated[str | None, typer.Option(help="Positions, such as 1:10 or 1,3:4.")] = None,
    dry_run: Annotated[bool, typer.Option(help="Report what's new; write nothing.")] = False,
) -> None:
    """Download playlists into one folder each, skipping what's already there."""
    config = common.load_config_or_exit(ctx)
    backend = common.make_backend(config)
    root = out.expanduser().absolute() if out else config.output_root
    options = FetchOptions(media_format, root, items, dry_run)
    worst = max(_fetch_one(url, options, backend) for url in urls)
    if worst:
        raise typer.Exit(worst)
