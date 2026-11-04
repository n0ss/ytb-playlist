"""Load the TOML config: output root and binary paths."""

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

TOOLS = ("yt-dlp", "ffmpeg", "deno")
CONFIG_FILE = "config.toml"


class ConfigError(Exception):
    """The config file is missing or invalid."""


@dataclass(frozen=True)
class Config:
    output_root: Path
    binaries: dict[str, Path]


def default_config_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/ytb-playlist"
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "ytb-playlist"


def load_config(path: Path | None = None) -> Config:
    """Read `path`, or the default file. Only an explicit path has to exist."""
    if path is None:
        path = default_config_dir() / CONFIG_FILE
        if not path.exists():
            return _parse({}, path)
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except OSError as error:
        raise ConfigError(f"cannot read {path}: {error.strerror}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"invalid TOML in {path}: {error}") from error
    return _parse(data, path)


def _parse(data: dict, path: Path) -> Config:
    root = data.get("output_root", "~/Music/YouTube")
    if not isinstance(root, str):
        raise ConfigError(f"{path}: output_root must be a string")
    return Config(
        output_root=Path(root).expanduser(),
        binaries=_parse_binaries(data.get("binaries", {}), path),
    )


def _parse_binaries(table: object, path: Path) -> dict[str, Path]:
    if not isinstance(table, dict):
        raise ConfigError(f"{path}: binaries must be a table")
    binaries = {}
    for name, value in table.items():
        if name not in TOOLS:
            raise ConfigError(f"{path}: unknown binary {name}, expected one of {', '.join(TOOLS)}")
        if not isinstance(value, str):
            raise ConfigError(f"{path}: binaries.{name} must be a string")
        binary = Path(value).expanduser()
        if not binary.is_absolute():
            raise ConfigError(f"{path}: binaries.{name} must be an absolute path")
        binaries[name] = binary
    return binaries
