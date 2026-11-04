"""A stand-in for yt-dlp, shared by the engine and CLI tests."""

import json
from collections.abc import Iterator
from pathlib import Path

from ytb_playlist.backends.base import (
    DownloadMessage,
    DownloadProgress,
    DownloadRequest,
    DownloadSaved,
)
from ytb_playlist.core.models import PlaylistInfo

PLAYLIST_ID = "PLtest"


def write_item(work: Path, video_id: str, ext: str = "mp3") -> Path:
    info = {"id": video_id, "title": f"Title {video_id}", "upload_date": "20241023"}
    (work / f"{video_id}.info.json").write_text(json.dumps(info))
    (work / f"{video_id}.jpg").write_bytes(b"jpeg")
    media = work / f"{video_id}.{ext}"
    media.write_bytes(b"media")
    return media


class FakeBackend:
    """Behaves like yt-dlp for the engine: writes files, the archive and messages."""

    def __init__(
        self,
        ids: tuple[str, ...] = ("a", "b", "c"),
        outcomes: dict[str, list[DownloadMessage]] | None = None,
        title: str = "My playlist",
    ) -> None:
        self.info = PlaylistInfo(PLAYLIST_ID, title, ids)
        self.outcomes = outcomes or {}
        self.requests: list[DownloadRequest] = []

    def playlist_info(self, url: str) -> PlaylistInfo:
        self.url = url
        return self.info

    def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
        self.requests.append(request)
        for position in request.positions:
            video_id = self.info.item_ids[position - 1]
            if video_id in self.outcomes:
                yield from self.outcomes[video_id]
                continue
            yield DownloadProgress(video_id, True, 10, 10)
            media = write_item(request.work_dir, video_id, request.format)
            yield DownloadSaved(video_id, media)
            with request.archive.open("a") as archive:
                archive.write(f"youtube {video_id}\n")
