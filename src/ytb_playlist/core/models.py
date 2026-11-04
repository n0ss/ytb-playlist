"""Data shared by the engine and its front ends. GUI-agnostic."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class MediaFormat(StrEnum):
    MP3 = "mp3"
    MP4 = "mp4"


class FailureKind(StrEnum):
    PERMANENT = "permanent"
    TEMPORARY = "temporary"


@dataclass(frozen=True)
class Failure:
    kind: FailureKind
    reason: str
    date: str


@dataclass(frozen=True)
class PlaylistInfo:
    id: str
    title: str
    item_ids: tuple[str, ...]

    @property
    def item_count(self) -> int:
        return len(self.item_ids)


@dataclass(frozen=True)
class FetchOptions:
    format: MediaFormat
    output_root: Path
    items: str | None = None
    dry_run: bool = False
    # Core only, never a CLI flag: a clipped item is archived as if complete.
    clip_seconds: int | None = None


@dataclass(frozen=True)
class FetchPlanned:
    folder: Path
    pending: int
    skipped: int


@dataclass(frozen=True)
class ItemStarted:
    video_id: str


@dataclass(frozen=True)
class ItemProgress:
    video_id: str
    percent: float


@dataclass(frozen=True)
class ItemSaved:
    video_id: str
    path: Path


@dataclass(frozen=True)
class ItemFailed:
    video_id: str
    kind: FailureKind
    reason: str


@dataclass(frozen=True)
class FetchDone:
    saved: int
    failed: int
    skipped: int


Event = FetchPlanned | ItemStarted | ItemProgress | ItemSaved | ItemFailed | FetchDone
