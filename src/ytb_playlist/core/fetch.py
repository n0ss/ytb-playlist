# SPDX-License-Identifier: GPL-3.0-only
"""The fetch engine: download into a work folder, then move each item to its final name.

Front ends call `fetch` and render the events; nothing here prints.
"""

import json
import os
import re
from collections.abc import Callable
from contextlib import closing
from datetime import date
from pathlib import Path

from ytb_playlist.backends.base import (
    Backend,
    DownloadError,
    DownloadMessage,
    DownloadProgress,
    DownloadRequest,
    DownloadSaved,
)
from ytb_playlist.core.models import (
    Event,
    Failure,
    FailureKind,
    FetchDone,
    FetchOptions,
    FetchPlanned,
    ItemFailed,
    ItemProgress,
    ItemSaved,
    ItemStarted,
    PlaylistInfo,
)
from ytb_playlist.core.state import (
    STATE_DIR,
    PlaylistState,
    find_folder,
    load_state,
    save_state,
)
from ytb_playlist.naming import file_name, folder_name, is_safe_id
from ytb_playlist.urls import playlist_url

ARCHIVE_FILE = "archive.txt"
WORK_DIR = "tmp"
THUMBNAIL_DIR = "thumbs"
ITEM_RANGE = re.compile(r"(\d+)(?::(\d+))?")


class FetchError(Exception):
    """A failure that concerns the whole playlist rather than one item."""


class ItemsError(ValueError):
    """The `--items` selection can't be read."""


def parse_items(text: str | None, count: int) -> set[int]:
    """Read `2`, `1:10` or `1,3:4` as playlist positions. A range may pass the end."""
    if text is None:
        return set(range(1, count + 1))
    positions: set[int] = set()
    for part in text.split(","):
        match = ITEM_RANGE.fullmatch(part.strip())
        if match is None:
            raise ItemsError(f"unreadable item selection: {text}")
        start, end = int(match[1]), int(match[2] or match[1])
        if start < 1 or end < start:
            raise ItemsError(f"unreadable item selection: {text}")
        positions.update(range(start, min(end, count) + 1))
    return positions


def _read_archive(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.split()[-1] for line in path.read_text(errors="replace").splitlines() if line.strip()
    }


class _ProgressTracker:
    """Percent for one stream. Progress restarts per stream, so `finished` resets it.

    Estimates move, and an early estimate can equal the bytes so far (decision 20), so a line that
    has reached its total says nothing until `finished`.
    """

    def __init__(self) -> None:
        self._best = 0.0

    def update(self, message: DownloadProgress) -> float | None:
        if message.finished:
            self._best = 0.0
            return 100.0
        if not message.total or message.downloaded >= message.total:
            return None
        self._best = max(self._best, message.downloaded / message.total * 100)
        return self._best


class _Run:
    def __init__(
        self,
        folder: Path,
        state: PlaylistState,
        on_event: Callable[[Event], None],
        today: date,
    ) -> None:
        self.folder = folder
        self.state_dir = folder / STATE_DIR
        self.work = self.state_dir / WORK_DIR
        self.state = state
        self.on_event = on_event
        self.today = today.isoformat()
        self.saved = 0
        self.failed = 0
        self.playlist_errors: list[str] = []
        self.current: str | None = None
        self.tracker = _ProgressTracker()

    def recover(self, archived: set[str], ext: str) -> None:
        """Yt-dlp records an item before we move it, so a crash can strand a finished file."""
        for video_id in sorted(archived):
            media = self.work / f"{video_id}.{ext}"
            if media.exists():
                self._save(video_id, media)

    def handle(self, message: DownloadMessage) -> None:
        match message:
            case DownloadProgress():
                self._progress(message)
            case DownloadSaved():
                self._save(message.video_id, message.path)
                self.current = None
            case DownloadError():
                self._error(message)

    def _progress(self, message: DownloadProgress) -> None:
        if message.video_id != self.current:
            self.current = message.video_id
            self.tracker = _ProgressTracker()
            self.on_event(ItemStarted(message.video_id))
        percent = self.tracker.update(message)
        if percent is not None:
            self.on_event(ItemProgress(message.video_id, percent))

    def _error(self, message: DownloadError) -> None:
        video_id = message.video_id or self.current
        if video_id is None:
            self.playlist_errors.append(message.reason)
        else:
            self._fail(video_id, message.kind, message.reason)
        self.current = None

    def _save(self, video_id: str, media: Path) -> None:
        try:
            target = self._move_into_place(video_id, media)
        except (OSError, ValueError) as error:
            self._fail(video_id, FailureKind.TEMPORARY, f"could not finish the item: {error}")
            return
        self.state.failures.pop(video_id, None)
        save_state(self.folder, self.state)
        self.saved += 1
        self.on_event(ItemSaved(video_id, target))

    def _move_into_place(self, video_id: str, media: Path) -> Path:
        if not is_safe_id(video_id) or media.parent.resolve() != self.work.resolve():
            raise ValueError(f"unexpected file: {media}")
        info_path = self.work / f"{video_id}.info.json"
        info = json.loads(info_path.read_text())
        if not isinstance(info, dict) or info.get("id") != video_id:
            raise ValueError(f"metadata doesn't match the item: {info_path}")
        target = self.folder / file_name(info, media.suffix.removeprefix("."))
        if target.exists():
            media.unlink()
        else:
            os.replace(media, target)
        os.replace(info_path, self.state_dir / info_path.name)
        thumbnail = self.work / f"{video_id}.jpg"
        if thumbnail.exists():
            thumbnails = self.state_dir / THUMBNAIL_DIR
            thumbnails.mkdir(exist_ok=True)
            os.replace(thumbnail, thumbnails / thumbnail.name)
        return target

    def _fail(self, video_id: str, kind: FailureKind, reason: str) -> None:
        self.state.failures[video_id] = Failure(kind, reason, self.today)
        save_state(self.folder, self.state)
        if kind == FailureKind.TEMPORARY:
            self.failed += 1
        self.on_event(ItemFailed(video_id, kind, reason))

    def remove_empty_work_folder(self) -> None:
        try:
            self.work.rmdir()
        except OSError:
            pass


def _pending(
    info: PlaylistInfo, selected: set[int], archived: set[str], skipped: set[str]
) -> tuple[int, ...]:
    return tuple(
        position
        for position, video_id in enumerate(info.item_ids, start=1)
        if video_id and position in selected and video_id not in archived | skipped
    )


def fetch(
    url: str,
    options: FetchOptions,
    backend: Backend,
    on_event: Callable[[Event], None],
    today: date,
) -> None:
    canonical = playlist_url(url)
    info = backend.playlist_info(canonical)
    new_folder = options.output_root / folder_name(info.title, info.id)
    folder = find_folder(options.output_root, info.id) or new_folder
    state = load_state(folder) or PlaylistState(info.id, options.format)
    state.require_format(options.format)
    selected = parse_items(options.items, info.item_count)

    run = _Run(folder, state, on_event, today)
    archive = run.state_dir / ARCHIVE_FILE
    archived = _read_archive(archive)
    if not options.dry_run:
        run.recover(archived, options.format)

    item_ids = set(info.item_ids)
    positions = _pending(info, selected, archived, state.permanent_failures())
    on_event(FetchPlanned(folder, len(positions), len(state.permanent_failures() & item_ids)))
    if options.dry_run:
        return

    if positions:
        run.work.mkdir(parents=True, exist_ok=True)
        save_state(folder, state)
        request = DownloadRequest(
            canonical, run.work, archive, options.format, positions, options.clip_seconds
        )
        with closing(backend.download(request)) as messages:
            for message in messages:
                run.handle(message)
    run.remove_empty_work_folder()
    if run.playlist_errors:
        raise FetchError(run.playlist_errors[0])
    on_event(FetchDone(run.saved, run.failed, len(state.permanent_failures() & item_ids)))
