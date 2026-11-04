# SPDX-License-Identifier: GPL-3.0-only
"""Run the Homebrew yt-dlp as a subprocess and parse its output.

Arguments are always lists, and no metadata reaches a shell or `--exec`. Our templates print only
IDs, numbers and paths, so a video title can't forge a line. Exit codes can't tell one failure from
another (decision 20), so failures are classified from the `ERROR:` text.
"""

import json
import re
import subprocess
from collections.abc import Generator
from pathlib import Path

from ytb_playlist.backends.base import (
    BackendError,
    DownloadError,
    DownloadMessage,
    DownloadProgress,
    DownloadRequest,
    DownloadSaved,
)
from ytb_playlist.core.models import FailureKind, MediaFormat, PlaylistInfo

LISTING_TIMEOUT_SECONDS = 300
PROGRESS_TEMPLATE = (
    "download:PROGRESS %(info.id)s|%(progress.status)s|%(progress.downloaded_bytes)s|"
    "%(progress.total_bytes)s|%(progress.total_bytes_estimate)s"
)
SAVED_TEMPLATE = "after_move:SAVED %(id)s|%(filepath)s"
FORMAT_ARGS = {
    MediaFormat.MP3: ["-x", "--audio-format", "mp3", "--audio-quality", "0"],
    MediaFormat.MP4: [
        "-f",
        "bv*[vcodec^=avc1][height<=1080]+ba[ext=m4a]/b[ext=mp4][vcodec^=avc1][height<=1080]",
        "--merge-output-format",
        "mp4",
    ],
}
ERROR_LINE = re.compile(r"ERROR: (?:\[(?P<extractor>[^\]]+)\] (?P<id>[\w-]+): )?(?P<reason>.*)")
ITEM_EXTRACTOR = "youtube"
PERMANENT_ERRORS = (
    "this video is unavailable",
    "video unavailable",
    "private video",
    "requested format is not available",
    "has been removed",
    "account associated with this video has been terminated",
)


def _number(text: str) -> int | None:
    try:
        return int(float(text))
    except ValueError, OverflowError:
        return None


def _parse_progress(body: str) -> DownloadProgress | None:
    fields = body.split("|")
    if len(fields) != 5:
        return None
    video_id, status, downloaded, total, estimate = fields
    done = _number(downloaded)
    if done is None:
        return None
    size = _number(total)
    return DownloadProgress(
        video_id, status == "finished", done, _number(estimate) if size is None else size
    )


def _parse_saved(body: str) -> DownloadSaved | None:
    video_id, separator, path = body.partition("|")
    return DownloadSaved(video_id, Path(path)) if separator else None


def _parse_error(line: str) -> DownloadError:
    match = ERROR_LINE.match(line)
    reason = match["reason"]
    permanent = any(text in reason.lower() for text in PERMANENT_ERRORS)
    return DownloadError(
        match["id"] if match["extractor"] == ITEM_EXTRACTOR else None,
        FailureKind.PERMANENT if permanent else FailureKind.TEMPORARY,
        reason,
    )


def parse_line(line: str) -> DownloadMessage | None:
    if line.startswith("PROGRESS "):
        return _parse_progress(line.removeprefix("PROGRESS "))
    if line.startswith("SAVED "):
        return _parse_saved(line.removeprefix("SAVED "))
    if line.startswith("ERROR: "):
        return _parse_error(line)
    return None


def parse_playlist(text: str) -> PlaylistInfo:
    """Take IDs and positions from the listing; titles and dates there aren't reliable."""
    try:
        data = json.loads(text)
        return PlaylistInfo(
            id=data["id"],
            title=data.get("title") or "",
            item_ids=tuple((entry or {}).get("id") or "" for entry in data["entries"]),
        )
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise BackendError(f"unusable playlist listing: {error}") from error


def download_args(request: DownloadRequest) -> list[str]:
    args = [
        *FORMAT_ARGS[request.format],
        "--ignore-errors",
        "--newline",
        "--progress",
        "--progress-template",
        PROGRESS_TEMPLATE,
        "--print",
        SAVED_TEMPLATE,
        "--write-info-json",
        "--no-write-playlist-metafiles",
        "--write-thumbnail",
        "--convert-thumbnails",
        "jpg",
        "--sleep-interval",
        "3",
        "--max-sleep-interval",
        "8",
        "--download-archive",
        str(request.archive),
        "--playlist-items",
        ",".join(str(position) for position in request.positions),
        "-P",
        str(request.work_dir),
        "-o",
        "%(id)s.%(ext)s",
    ]
    if request.clip_seconds is not None:
        args += ["--download-sections", f"*0-{request.clip_seconds}"]
    return [*args, request.url]


class YtDlpBackend:
    def __init__(self, ytdlp: Path, ffmpeg: Path, deno: Path) -> None:
        self._base = [
            str(ytdlp),
            "--ignore-config",
            "--ffmpeg-location",
            str(ffmpeg),
            "--js-runtimes",
            f"deno:{deno}",
        ]

    def playlist_info(self, url: str) -> PlaylistInfo:
        try:
            result = subprocess.run(
                [*self._base, "-J", "--flat-playlist", url],
                check=False,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=LISTING_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise BackendError(f"could not run yt-dlp: {error}") from error
        if result.returncode:
            raise BackendError(result.stderr.strip().rpartition("\n")[2] or "yt-dlp failed")
        return parse_playlist(result.stdout)

    def download(self, request: DownloadRequest) -> Generator[DownloadMessage]:
        saw_error = False
        try:
            process = subprocess.Popen(
                [*self._base, *download_args(request)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
            )
        except OSError as error:
            raise BackendError(f"could not run yt-dlp: {error}") from error
        with process:
            try:
                for line in process.stdout:
                    message = parse_line(line.rstrip("\n"))
                    if message is not None:
                        saw_error = saw_error or isinstance(message, DownloadError)
                        yield message
            finally:
                if process.poll() is None:
                    process.terminate()
        code = process.returncode
        if code and not (code == 1 and saw_error):
            raise BackendError(f"yt-dlp stopped with exit {code}")
