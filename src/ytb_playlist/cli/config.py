# SPDX-License-Identifier: GPL-3.0-only
"""The `config` commands: see where the configuration lives and what it resolves to."""

import typer

from ytb_playlist.cli import common
from ytb_playlist.config import CONFIG_FILE, default_config_dir

config_app = typer.Typer(no_args_is_help=True)


@config_app.command("path")
def path(ctx: typer.Context) -> None:
    """Show which config file is used."""
    typer.echo(ctx.obj or default_config_dir() / CONFIG_FILE)


@config_app.command("show")
def show(ctx: typer.Context) -> None:
    """Show the settings after merging the file and the environment."""
    config = common.load_config_or_exit(ctx)
    rows = {
        "output_root": config.output_root,
        "genre": config.genre,
        "cover": config.cover.value,
        "max_height": config.max_height,
        "sleep_min": config.sleep_min,
        "sleep_max": config.sleep_max,
    }
    rows |= {f"binaries.{name}": binary for name, binary in config.binaries.items()}
    for key, value in rows.items():
        typer.echo(f"{key} = {value}")
