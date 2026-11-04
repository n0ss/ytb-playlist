"""What every command needs: errors, the config and the backend."""

import typer
from rich.console import Console
from rich.text import Text

from ytb_playlist import deps
from ytb_playlist.backends.ytdlp_proc import YtDlpBackend
from ytb_playlist.cli import exit_codes
from ytb_playlist.config import TOOLS, Config, ConfigError, load_config


def print_error(message: object) -> None:
    Console(stderr=True).print(Text(f"error: {message}", style="red"), soft_wrap=True)


def load_config_or_exit(ctx: typer.Context) -> Config:
    try:
        return load_config(ctx.obj)
    except ConfigError as error:
        print_error(error)
        raise typer.Exit(exit_codes.USAGE_ERROR) from error


def make_backend(config: Config) -> YtDlpBackend:
    paths = {name: deps.find_binary(name, config.binaries.get(name)) for name in TOOLS}
    missing = [name for name, path in paths.items() if path is None]
    if missing:
        print_error(f"not found: {', '.join(missing)}. Run `ytb-playlist doctor` for details.")
        raise typer.Exit(exit_codes.MISSING_DEPENDENCY)
    return YtDlpBackend(paths["yt-dlp"], paths["ffmpeg"], paths["deno"])
