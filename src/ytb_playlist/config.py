# SPDX-License-Identifier: GPL-3.0-only
"""Load the TOML config: output root and binary paths."""

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ytb_playlist.core.models import CoverSource

TOOLS = ("yt-dlp", "ffmpeg", "deno")
CONFIG_FILE = "config.toml"
ENV_PREFIX = "YTB_PLAYLIST_"
DEFAULT_OUTPUT_ROOT = "~/Music/YouTube"
TEXT_SETTINGS = {"output_root", "genre", "cover"}
NUMBER_SETTINGS = {"max_height": 1, "sleep_min": 0, "sleep_max": 0}
FILE_KEYS = TEXT_SETTINGS | set(NUMBER_SETTINGS) | {"binaries"}


class ConfigError(Exception):
    """The config file is missing or invalid."""


@dataclass(frozen=True)
class Config:
    output_root: Path
    binaries: dict[str, Path]
    genre: str = "YouTube"
    cover: CoverSource = CoverSource.EPISODE
    max_height: int = 1080
    sleep_min: int = 3
    sleep_max: int = 8


def default_config_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/ytb-playlist"
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "ytb-playlist"


def load_config(path: Path | None = None) -> Config:
    """Merge defaults, then the file, then the environment. CLI flags come last, in the CLI.

    Only an explicit path has to exist.
    """
    if path is None:
        path = default_config_dir() / CONFIG_FILE
        if not path.exists():
            return _parse({}, path)
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except OSError as error:
        raise ConfigError(f"cannot read {path}: {error.strerror}") from error
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ConfigError(f"invalid TOML in {path}: {error}") from error
    return _parse(data, path)


def _text(values: dict, key: str) -> str | None:
    value = values.get(key)
    if value is not None and not isinstance(value, str):
        raise ConfigError(f"{key} must be a string")
    return value


def _number(values: dict, key: str) -> int | None:
    value = values.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{key} must be a whole number")
    if value < NUMBER_SETTINGS[key]:
        raise ConfigError(f"{key} must be at least {NUMBER_SETTINGS[key]}")
    return value


def _from_environment(data: dict) -> dict:
    values = dict(data)
    for key in (*TEXT_SETTINGS, *NUMBER_SETTINGS):
        raw = os.environ.get(f"{ENV_PREFIX}{key.upper()}")
        if not raw:
            continue
        if key in NUMBER_SETTINGS:
            try:
                raw = int(raw)
            except ValueError as error:
                raise ConfigError(f"{key} must be a whole number") from error
        values[key] = raw
    return values


def _parse(data: dict, path: Path) -> Config:
    unknown = set(data) - FILE_KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown setting {', '.join(sorted(unknown))}")
    values = _from_environment(data)
    defaults = Config(Path(), {})
    output_root = Path(_text(values, "output_root") or DEFAULT_OUTPUT_ROOT).expanduser()
    if not output_root.is_absolute():
        raise ConfigError(f"{path}: output_root must be an absolute path")
    try:
        cover = CoverSource(_text(values, "cover") or defaults.cover)
    except ValueError as error:
        raise ConfigError(f"cover must be one of {', '.join(CoverSource)}") from error
    sleep_min = _number(values, "sleep_min")
    sleep_max = _number(values, "sleep_max")
    sleep_min = defaults.sleep_min if sleep_min is None else sleep_min
    sleep_max = defaults.sleep_max if sleep_max is None else sleep_max
    if sleep_min > sleep_max:
        raise ConfigError("sleep_min must not be above sleep_max")
    return Config(
        output_root=output_root,
        binaries=_parse_binaries(data.get("binaries", {}), path),
        genre=_text(values, "genre") or defaults.genre,
        cover=cover,
        max_height=_number(values, "max_height") or defaults.max_height,
        sleep_min=sleep_min,
        sleep_max=sleep_max,
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
