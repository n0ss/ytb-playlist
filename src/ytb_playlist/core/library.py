# SPDX-License-Identifier: GPL-3.0-only
"""Work on files already in a playlist folder, from their saved metadata."""

import json
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ytb_playlist.core.state import (
    STATE_DIR,
    THUMBNAIL_DIR,
    load_state,
    read_item_info,
    save_state,
)
from ytb_playlist.cover import find_thumbnail
from ytb_playlist.naming import file_name

MEDIA_SUFFIXES = (".mp3", ".mp4")
ITEM_NAME = re.compile(r" \[([A-Za-z0-9_-]+)\]\.(?:mp3|mp4)$")
RENAME_LOG = "rename-log.jsonl"


class LibraryError(Exception):
    """This file can't be handled, usually because it isn't one of ours."""


@dataclass(frozen=True)
class LocalItem:
    path: Path
    video_id: str
    info: dict

    @property
    def state_dir(self) -> Path:
        return self.path.parent / STATE_DIR

    @property
    def thumbnail(self) -> Path | None:
        return find_thumbnail(self.state_dir / THUMBNAIL_DIR, self.video_id)


def media_files(paths: list[Path]) -> list[Path]:
    """Expand folders to the media directly inside them. Other files pass through."""
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files += sorted(p for p in path.iterdir() if p.suffix in MEDIA_SUFFIXES)
        else:
            files.append(path)
    return files


def load_item(path: Path) -> LocalItem:
    match = ITEM_NAME.search(path.name)
    if match is None:
        raise LibraryError(f"{path.name}: no video ID in the name")
    video_id = match[1]
    info_path = path.parent / STATE_DIR / f"{video_id}.info.json"
    try:
        return LocalItem(path, video_id, read_item_info(info_path, video_id))
    except FileNotFoundError as error:
        raise LibraryError(f"{path.name}: no saved metadata") from error
    except (OSError, ValueError) as error:
        raise LibraryError(f"{path.name}: unusable metadata: {error}") from error


def mark_tagged(item: LocalItem) -> None:
    state = load_state(item.path.parent)
    if state is not None:
        state.tagged.add(item.video_id)
        state.failures.pop(item.video_id, None)
        save_state(item.path.parent, state)


def rename_target(item: LocalItem) -> Path | None:
    """The name the rules give this item, or None if it already has it."""
    target = item.path.with_name(file_name(item.info, item.path.suffix.removeprefix(".")))
    return None if target == item.path else target


def apply_rename(item: LocalItem, target: Path, today: date) -> None:
    """Log first, so a crash can't leave a rename with no record of the old name."""
    if target.exists():
        raise LibraryError(f"{target.name} already exists")
    entry = {"from": item.path.name, "to": target.name, "date": today.isoformat()}
    with (item.state_dir / RENAME_LOG).open("a", encoding="utf-8") as log:
        log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    os.rename(item.path, target)
