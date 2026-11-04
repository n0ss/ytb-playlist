# SPDX-License-Identifier: GPL-3.0-only
"""Saved playlists, in a generated file so that `config.toml` stays yours to edit."""

import json
import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ytb_playlist.config import Config
from ytb_playlist.core.models import CoverSource, FetchOptions, MediaFormat

PLAYLISTS_FILE = "playlists.toml"
HEADER = "# Written by `ytb-playlist playlist`. Edits here are kept, comments are not.\n"


class PlaylistsError(Exception):
    """The saved playlists can't be read, or this change can't be made."""


@dataclass(frozen=True)
class PlaylistEntry:
    name: str
    url: str
    playlist_id: str
    format: MediaFormat
    album: str | None = None
    genre: str | None = None
    cover: CoverSource | None = None
    max_height: int | None = None


@dataclass(frozen=True)
class TagSettings:
    album: str | None
    genre: str
    cover: CoverSource


def _text(table: dict, key: str, required: bool = False) -> str | None:
    value = table.get(key) if not required else table[key]
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{key} must be text")
    return value


def _entry(name: str, table: dict) -> PlaylistEntry:
    height = table.get("max_height")
    is_number = isinstance(height, int) and not isinstance(height, bool)
    if height is not None and (not is_number or height < 1):
        raise ValueError("max_height must be a positive whole number")
    cover = _text(table, "cover")
    return PlaylistEntry(
        name=name,
        url=_text(table, "url", required=True),
        playlist_id=_text(table, "playlist_id", required=True),
        format=MediaFormat(table["format"]),
        album=_text(table, "album"),
        genre=_text(table, "genre"),
        cover=CoverSource(cover) if cover else None,
        max_height=height,
    )


def load_playlists(folder: Path) -> dict[str, PlaylistEntry]:
    path = folder / PLAYLISTS_FILE
    if not path.exists():
        return {}
    try:
        with path.open("rb") as file:
            tables = tomllib.load(file).get("playlists", {})
        return {name: _entry(name, table) for name, table in tables.items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise PlaylistsError(f"damaged {path}: {error}") from error


def _render(entry: PlaylistEntry) -> str:
    """JSON strings are valid TOML basic strings, escapes included."""
    fields = {
        "url": entry.url,
        "playlist_id": entry.playlist_id,
        "format": entry.format.value,
        "album": entry.album,
        "genre": entry.genre,
        "cover": entry.cover.value if entry.cover else None,
        "max_height": entry.max_height,
    }
    lines = [f"[playlists.{json.dumps(entry.name, ensure_ascii=False)}]"]
    for key, value in fields.items():
        if value is not None:
            lines.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def save_playlists(folder: Path, entries: dict[str, PlaylistEntry]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    body = HEADER + "\n".join(_render(entry) for entry in entries.values())
    file_descriptor, temp_name = tempfile.mkstemp(dir=folder, prefix=f"{PLAYLISTS_FILE}.")
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
            file.write(body)
        os.replace(temp_name, folder / PLAYLISTS_FILE)
    except BaseException:
        os.unlink(temp_name)
        raise


def add_playlist(folder: Path, entry: PlaylistEntry) -> None:
    entries = load_playlists(folder)
    if entry.name in entries:
        raise PlaylistsError(f"a playlist is already saved as {entry.name}")
    for existing in entries.values():
        if existing.playlist_id == entry.playlist_id:
            raise PlaylistsError(f"this playlist is already saved as {existing.name}")
    save_playlists(folder, {**entries, entry.name: entry})


def remove_playlist(folder: Path, name: str) -> None:
    """Forget a saved playlist. Its folder and files are never touched."""
    entries = load_playlists(folder)
    if name not in entries:
        raise PlaylistsError(f"no saved playlist called {name}")
    del entries[name]
    save_playlists(folder, entries)


def find_entry(entries: dict[str, PlaylistEntry], playlist_id: str | None) -> PlaylistEntry | None:
    for entry in entries.values():
        if entry.playlist_id == playlist_id:
            return entry
    return None


def tag_settings(config: Config, entry: PlaylistEntry | None) -> TagSettings:
    """What tags a playlist gets, wherever the tagging starts from."""
    if entry is None:
        return TagSettings(None, config.genre, config.cover)
    return TagSettings(entry.album, entry.genre or config.genre, entry.cover or config.cover)


def fetch_options(
    config: Config,
    media_format: MediaFormat,
    entry: PlaylistEntry | None = None,
    *,
    output_root: Path | None = None,
    items: str | None = None,
    dry_run: bool = False,
    retry_failed: bool = False,
    cover: CoverSource | None = None,
    max_height: int | None = None,
    quality_max: bool = False,
) -> FetchOptions:
    """Each setting takes the CLI value, then the playlist's, then the config's."""
    return FetchOptions(
        format=media_format,
        output_root=output_root or config.output_root,
        items=items,
        dry_run=dry_run,
        retry_failed=retry_failed,
        cover=cover or tag_settings(config, entry).cover,
        max_height=max_height or (entry and entry.max_height) or config.max_height,
        quality_max=quality_max,
        sleep_min=config.sleep_min,
        sleep_max=config.sleep_max,
    )
