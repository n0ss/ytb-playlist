# SPDX-License-Identifier: GPL-3.0-only
"""Per-playlist state: folder lookup and `.ytb-playlist/state.json`.

`archive.txt` belongs to yt-dlp and owns "downloaded". This file owns "tagged" and failures.
"""

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ytb_playlist.core.models import Failure, FailureKind, MediaFormat

STATE_DIR = ".ytb-playlist"
STATE_FILE = "state.json"
THUMBNAIL_DIR = "thumbs"
STATE_VERSION = 1


class StateError(Exception):
    """A state file is damaged. It is left in place for the owner to inspect."""


class FolderConflictError(Exception):
    """Two folders claim the same playlist ID."""


class FormatChangeError(Exception):
    """A playlist keeps one format, because the archive tracks IDs, not formats."""


@dataclass
class PlaylistState:
    playlist_id: str
    format: MediaFormat
    tagged: set[str] = field(default_factory=set)
    failures: dict[str, Failure] = field(default_factory=dict)

    def require_format(self, wanted: MediaFormat) -> None:
        if wanted != self.format:
            raise FormatChangeError(
                f"this playlist is kept as {self.format}, so {wanted} is refused"
            )

    def permanent_failures(self) -> set[str]:
        return {
            video_id
            for video_id, failure in self.failures.items()
            if failure.kind == FailureKind.PERMANENT
        }


def find_folder(output_root: Path, playlist_id: str) -> Path | None:
    """Compare the name's ending: titles can hold `[`, so a glob pattern would be wrong."""
    if not output_root.is_dir():
        return None
    suffix = f" [{playlist_id}]"
    matches = sorted(
        path for path in output_root.iterdir() if path.is_dir() and path.name.endswith(suffix)
    )
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches)
        raise FolderConflictError(f"two folders for playlist {playlist_id}: {names}")
    return matches[0] if matches else None


def load_state(folder: Path) -> PlaylistState | None:
    path = folder / STATE_DIR / STATE_FILE
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["version"] != STATE_VERSION:
            raise ValueError(f"unknown version {data['version']}")
        return PlaylistState(
            playlist_id=data["playlist_id"],
            format=MediaFormat(data["format"]),
            tagged=set(data["tagged"]),
            failures={
                video_id: Failure(FailureKind(item["kind"]), item["reason"], item["date"])
                for video_id, item in data["failures"].items()
            },
        )
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise StateError(f"damaged {path}: {error}") from error


def save_state(folder: Path, state: PlaylistState) -> None:
    """Write beside the target, then rename, so a crash never leaves half a file."""
    state_dir = folder / STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "version": STATE_VERSION,
        "playlist_id": state.playlist_id,
        "format": state.format,
        "tagged": sorted(state.tagged),
        "failures": {video_id: asdict(item) for video_id, item in state.failures.items()},
    }
    file_descriptor, temp_name = tempfile.mkstemp(dir=state_dir, prefix=f"{STATE_FILE}.")
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_name, state_dir / STATE_FILE)
    except BaseException:
        os.unlink(temp_name)
        raise
