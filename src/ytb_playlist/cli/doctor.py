"""The `doctor` command: render the dependency report with Rich."""

from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from ytb_playlist import deps
from ytb_playlist.cli import exit_codes
from ytb_playlist.config import ConfigError, default_config_dir, load_config


def doctor(ctx: typer.Context) -> None:
    """Check yt-dlp, ffmpeg, deno and the output folder."""
    console = Console()
    config_path: Path | None = ctx.obj
    try:
        config = load_config(config_path)
    except ConfigError as error:
        console.print(Text(f"error: {error}", style="red"))
        raise typer.Exit(exit_codes.USAGE_ERROR) from error

    report = deps.check(config, default_config_dir(), date.today())

    table = Table("Tool", "Version", "Path")
    for dependency in report.dependencies:
        table.add_row(
            dependency.name,
            Text(dependency.version or "-"),
            Text(str(dependency.path or "-")),
        )
    console.print(table)
    for notice in report.notices:
        console.print(Text(notice, style="yellow"))
    for problem in report.problems:
        console.print(Text(problem, style="red"))
    if report.problems:
        raise typer.Exit(exit_codes.MISSING_DEPENDENCY)
