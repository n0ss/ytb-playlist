# SPDX-License-Identifier: GPL-3.0-only
"""The test seam between the engine and yt-dlp."""

from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ytb_playlist.core.models import FailureKind, MediaFormat, PlaylistInfo


class BackendError(Exception):
    """yt-dlp could not be run, or stopped in a way that says nothing about any one item."""


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    work_dir: Path
    archive: Path
    format: MediaFormat
    positions: tuple[int, ...]
    clip_seconds: int | None


@dataclass(frozen=True)
class DownloadProgress:
    video_id: str
    finished: bool
    downloaded: int
    total: int | None


@dataclass(frozen=True)
class DownloadSaved:
    video_id: str
    path: Path


@dataclass(frozen=True)
class DownloadError:
    """`video_id` is None when the error concerns the whole playlist."""

    video_id: str | None
    kind: FailureKind
    reason: str


DownloadMessage = DownloadProgress | DownloadSaved | DownloadError


class Backend(Protocol):
    def playlist_info(self, url: str) -> PlaylistInfo: ...

    def download(self, request: DownloadRequest) -> Generator[DownloadMessage]: ...
