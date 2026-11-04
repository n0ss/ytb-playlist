# SPDX-License-Identifier: GPL-3.0-only
"""The `sync` command: bring saved playlists up to date."""

from typing import Annotated

import typer
from rich.console import Console
from rich.text import Text

from ytb_playlist.cli import common, exit_codes
from ytb_playlist.cli.fetch import run_fetch
from ytb_playlist.cli.playlist import load_or_exit
from ytb_playlist.core.playlists import PlaylistEntry, fetch_options, tag_settings


def _selected(name: str | None, every: bool) -> list[PlaylistEntry]:
    if (name is None) == (not every):
        common.print_error("give a saved name or --all, not both")
        raise typer.Exit(exit_codes.USAGE_ERROR)
    entries = load_or_exit()
    if every:
        return list(entries.values())
    if name not in entries:
        common.print_error(f"no saved playlist called {name}")
        raise typer.Exit(exit_codes.USAGE_ERROR)
    return [entries[name]]


def sync_command(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Argument(help="Saved name.")] = None,
    every: Annotated[bool, typer.Option("--all", help="Every saved playlist.")] = False,
    retry_failed: Annotated[bool, typer.Option(help="Try permanent failures again.")] = False,
    dry_run: Annotated[bool, typer.Option(help="Report what's new; write nothing.")] = False,
) -> None:
    """Download what's new in saved playlists."""
    config = common.load_config_or_exit(ctx)
    entries = _selected(name, every)
    console = Console()
    if not entries:
        console.print("No saved playlists.")
        return
    backend = common.make_backend(config)
    worst = 0
    for entry in entries:
        console.print(Text(entry.name, style="bold"), soft_wrap=True)
        options = fetch_options(
            config, entry.format, entry, retry_failed=retry_failed, dry_run=dry_run
        )
        worst = max(worst, run_fetch(entry.url, options, tag_settings(config, entry), backend))
    if worst:
        raise typer.Exit(worst)
