# SPDX-License-Identifier: GPL-3.0-only
import itertools
import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fakes import PLAYLIST_ID, FakeBackend, write_item

from ytb_playlist.backends.base import (
    BackendError,
    DownloadError,
    DownloadMessage,
    DownloadProgress,
    DownloadRequest,
    DownloadSaved,
)
from ytb_playlist.backends.ytdlp_proc import parse_line
from ytb_playlist.core.fetch import FetchError, ItemsError, fetch, parse_items
from ytb_playlist.core.models import (
    CoverSource,
    Event,
    FailureKind,
    FetchDone,
    FetchOptions,
    FetchPlanned,
    ItemFailed,
    ItemProgress,
    ItemSaved,
    ItemStarted,
    ItemTagged,
    MediaFormat,
    PlaylistInfo,
)
from ytb_playlist.core.state import (
    FolderConflictError,
    FormatChangeError,
    PlaylistState,
    load_state,
    save_state,
)
from ytb_playlist.naming import UnsafeIdError
from ytb_playlist.tagging.apply import TaggingError
from ytb_playlist.urls import UnsupportedUrlError

FIXTURES = Path(__file__).parent.parent / "fixtures"
URL = f"https://www.youtube.com/playlist?list={PLAYLIST_ID}&si=tracking"
TODAY = date(2026, 11, 4)
GONE = DownloadError("b", FailureKind.PERMANENT, "This video is unavailable")
FLAKY = DownloadError("b", FailureKind.TEMPORARY, "timeout")


def no_tag(_path: Path, _info: dict, _thumbnail: Path | None) -> tuple[str, ...]:
    return ()


class Run:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.events: list[Event] = []
        self.tagged: list[tuple[str, str, str | None]] = []
        self.tag_error: str | None = None
        self.tag_warnings: tuple[str, ...] = ()

    def __call__(self, backend: FakeBackend, **options: object) -> list[Event]:
        self.events = []
        values = {"format": MediaFormat.MP3, "output_root": self.root} | options
        fetch(URL, FetchOptions(**values), backend, self.tag, self.events.append, TODAY)
        return self.events

    def tag(self, path: Path, info: dict, thumbnail: Path | None) -> tuple[str, ...]:
        self.tagged.append((path.name, info["id"], thumbnail and thumbnail.name))
        if self.tag_error:
            raise TaggingError(self.tag_error)
        return self.tag_warnings

    @property
    def folder(self) -> Path:
        return self.root / f"My playlist [{PLAYLIST_ID}]"

    def media(self) -> list[str]:
        return sorted(p.name for p in self.folder.iterdir() if not p.name.startswith("."))


@pytest.fixture
def run(tmp_path: Path) -> Run:
    return Run(tmp_path / "root")


def of_type(events: list[Event], kind: type) -> list:
    return [event for event in events if isinstance(event, kind)]


def test_items_move_to_their_final_names(run: Run) -> None:
    run(FakeBackend(("a",)))
    assert run.media() == ["2024-10-23 - Title a [a].mp3"]
    assert (run.folder / "2024-10-23 - Title a [a].mp3").read_bytes() == b"media"


def test_metadata_and_thumbnail_are_kept_for_tagging(run: Run) -> None:
    run(FakeBackend(("a",)))
    state_dir = run.folder / ".ytb-playlist"
    assert json.loads((state_dir / "a.info.json").read_text())["id"] == "a"
    assert (state_dir / "thumbs" / "a.jpg").read_bytes() == b"jpeg"


def test_work_folder_is_removed_after_a_clean_run(run: Run) -> None:
    run(FakeBackend(("a",)))
    assert not (run.folder / ".ytb-playlist" / "tmp").exists()


def test_url_is_normalised_before_use(run: Run) -> None:
    backend = FakeBackend(("a",))
    run(backend)
    assert backend.url == f"https://www.youtube.com/playlist?list={PLAYLIST_ID}"


def test_unsupported_url_stops_before_any_call(tmp_path: Path) -> None:
    backend = FakeBackend()
    options = FetchOptions(MediaFormat.MP3, tmp_path)
    with pytest.raises(UnsupportedUrlError):
        fetch("https://vimeo.com/1", options, backend, no_tag, lambda _: None, TODAY)
    assert backend.requests == []


def test_events_describe_the_run(run: Run) -> None:
    events = run(FakeBackend(("a", "b")))
    assert events[0] == FetchPlanned(run.folder, 2, 0)
    assert of_type(events, ItemStarted) == [ItemStarted("a"), ItemStarted("b")]
    assert [event.video_id for event in of_type(events, ItemSaved)] == ["a", "b"]
    assert events[-1] == FetchDone(saved=2, failed=0, skipped=0)


def test_saved_items_are_tagged_with_their_metadata_and_thumbnail(run: Run) -> None:
    events = run(FakeBackend(("a",)))
    assert run.tagged == [("2024-10-23 - Title a [a].mp3", "a", "a.jpg")]
    assert load_state(run.folder).tagged == {"a"}
    assert of_type(events, ItemTagged) == [ItemTagged("a", ())]


def test_item_without_a_thumbnail_is_still_tagged(run: Run) -> None:
    class NoThumbnail(FakeBackend):
        def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
            media = write_item(request.work_dir, "a")
            (request.work_dir / "a.jpg").unlink()
            yield DownloadSaved("a", media)

    run(NoThumbnail(("a",)))
    assert run.tagged == [("2024-10-23 - Title a [a].mp3", "a", None)]


def test_tagging_warnings_reach_the_event(run: Run) -> None:
    run.tag_warnings = ("cover over budget",)
    events = run(FakeBackend(("a",)))
    assert of_type(events, ItemTagged) == [ItemTagged("a", ("cover over budget",))]


def test_tagging_failure_keeps_the_file_and_counts_as_failed(run: Run) -> None:
    run.tag_error = "bad file"
    events = run(FakeBackend(("a",)))
    assert run.media() == ["2024-10-23 - Title a [a].mp3"]
    assert of_type(events, ItemFailed)[0].kind == FailureKind.TEMPORARY
    assert events[-1] == FetchDone(saved=1, failed=1, skipped=0)
    assert load_state(run.folder).tagged == set()


def test_untagged_download_is_retried_without_downloading_again(run: Run) -> None:
    run.tag_error = "bad file"
    run(FakeBackend(("a",)))
    run.tag_error = None
    backend = FakeBackend(("a",))
    events = run(backend)
    assert backend.requests == []
    assert load_state(run.folder).tagged == {"a"}
    assert load_state(run.folder).failures == {}
    assert of_type(events, ItemTagged) == [ItemTagged("a", ())]
    assert events[-1] == FetchDone(saved=0, failed=0, skipped=0)


def test_tagged_items_are_not_tagged_again(run: Run) -> None:
    run(FakeBackend(("a",)))
    run.tagged.clear()
    run(FakeBackend(("a",)))
    assert run.tagged == []


def test_dry_run_tags_nothing(run: Run) -> None:
    run.tag_error = "bad file"
    run(FakeBackend(("a",)))
    run.tag_error = None
    run.tagged.clear()
    run(FakeBackend(("a",)), dry_run=True)
    assert run.tagged == []


def test_failed_tagging_stops_nothing_else(run: Run) -> None:
    run.tag_error = "bad file"
    events = run(FakeBackend(("a", "c")))
    assert events[-1] == FetchDone(saved=2, failed=2, skipped=0)


def test_tagged_file_removed_by_hand_is_not_an_error(run: Run) -> None:
    run.tag_error = "bad file"
    run(FakeBackend(("a",)))
    (run.folder / "2024-10-23 - Title a [a].mp3").unlink()
    run.tag_error = None
    run.tagged.clear()
    assert run(FakeBackend(("a",)))[-1] == FetchDone(saved=0, failed=0, skipped=0)
    assert run.tagged == []


def test_rerun_downloads_nothing(run: Run) -> None:
    run(FakeBackend())
    backend = FakeBackend()
    events = run(backend)
    assert backend.requests == []
    assert events[-1] == FetchDone(saved=0, failed=0, skipped=0)


def test_only_new_items_are_requested_by_their_position(run: Run) -> None:
    run(FakeBackend(("a", "c")))
    backend = FakeBackend(("new", "a", "other", "c"))
    run(backend)
    assert backend.requests[0].positions == (1, 3)


def test_renamed_playlist_reuses_its_folder(run: Run) -> None:
    run(FakeBackend(("a",)))
    run(FakeBackend(("a", "b"), title="New name on YouTube"))
    assert len(run.media()) == 2
    assert [path.name for path in run.root.iterdir()] == [run.folder.name]


def test_two_matching_folders_stop_the_run(run: Run) -> None:
    (run.root / f"One [{PLAYLIST_ID}]").mkdir(parents=True)
    (run.root / f"Two [{PLAYLIST_ID}]").mkdir()
    backend = FakeBackend()
    with pytest.raises(FolderConflictError):
        run(backend)
    assert backend.requests == []


def test_format_change_is_refused_before_downloading(run: Run) -> None:
    run(FakeBackend(("a",)))
    backend = FakeBackend(("a", "b"))
    with pytest.raises(FormatChangeError):
        run(backend, format=MediaFormat.MP4)
    assert backend.requests == []


def test_format_is_recorded_before_the_first_download_ends(run: Run) -> None:
    class Interrupted(FakeBackend):
        def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
            raise KeyboardInterrupt
            yield

    with pytest.raises(KeyboardInterrupt):
        run(Interrupted(("a",)))
    assert load_state(run.folder).format == MediaFormat.MP3


def test_mp4_files_keep_their_extension(run: Run) -> None:
    run(FakeBackend(("a",)), format=MediaFormat.MP4)
    assert run.media() == ["2024-10-23 - Title a [a].mp4"]


def test_permanent_failure_is_recorded_and_skipped_later(run: Run) -> None:
    events = run(FakeBackend(outcomes={"b": [GONE]}))
    assert of_type(events, ItemFailed) == [
        ItemFailed("b", FailureKind.PERMANENT, "This video is unavailable")
    ]
    assert events[-1] == FetchDone(saved=2, failed=0, skipped=1)
    saved = load_state(run.folder).failures["b"]
    assert (saved.kind, saved.date) == (FailureKind.PERMANENT, "2026-11-04")

    backend = FakeBackend()
    events = run(backend)
    assert backend.requests == []
    assert events[-1] == FetchDone(saved=0, failed=0, skipped=1)


def test_temporary_failure_counts_as_failed_and_is_retried(run: Run) -> None:
    events = run(FakeBackend(("a", "b"), {"b": [FLAKY]}))
    assert events[-1] == FetchDone(saved=1, failed=1, skipped=0)
    backend = FakeBackend(("a", "b"))
    run(backend)
    assert backend.requests[0].positions == (2,)
    assert load_state(run.folder).failures == {}


def test_error_without_an_id_belongs_to_the_item_in_progress(run: Run) -> None:
    message = DownloadError(None, FailureKind.TEMPORARY, "unable to download: HTTP Error 403")
    backend = FakeBackend(("b",), {"b": [DownloadProgress("b", False, 1, 10), message]})
    events = run(backend)
    assert of_type(events, ItemFailed)[0].video_id == "b"
    assert events[-1] == FetchDone(saved=0, failed=1, skipped=0)


def test_error_about_the_playlist_stops_with_fetch_error(run: Run) -> None:
    message = DownloadError(None, FailureKind.TEMPORARY, "HTTP Error 400")
    with pytest.raises(FetchError, match="HTTP Error 400"):
        run(FakeBackend(("b",), {"b": [message]}))


def test_backend_error_keeps_what_was_already_saved(run: Run) -> None:
    class Failing(FakeBackend):
        def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
            yield from super().download(request)
            raise BackendError("yt-dlp stopped with exit 2")

    with pytest.raises(BackendError):
        run(Failing(("a",)))
    assert len(run.media()) == 1


def test_interrupt_leaves_nothing_visible_and_keeps_partial_files(run: Run) -> None:
    class Interrupted(FakeBackend):
        def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
            (request.work_dir / "a.mp3.part").write_bytes(b"partial")
            yield DownloadProgress("a", False, 1, 10)
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run(Interrupted(("a",)))
    assert run.media() == []
    assert (run.folder / ".ytb-playlist" / "tmp" / "a.mp3.part").exists()


def test_stopping_closes_the_download_stream(run: Run) -> None:
    closed = []

    class Tracking(FakeBackend):
        def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
            def stream() -> Iterator[DownloadMessage]:
                try:
                    yield DownloadProgress("a", False, 1, 10)
                finally:
                    closed.append(True)

            # Held here so only an explicit close can end it, not garbage collection.
            self.stream = stream()
            return self.stream

    def stop(event: Event) -> None:
        if isinstance(event, ItemStarted):
            raise KeyboardInterrupt

    options = FetchOptions(MediaFormat.MP3, run.root)
    backend = Tracking(("a",))
    with pytest.raises(KeyboardInterrupt):
        fetch(URL, options, backend, no_tag, stop, TODAY)
    assert closed == [True]


def test_finished_file_left_by_a_crash_is_recovered(run: Run) -> None:
    work = run.folder / ".ytb-playlist" / "tmp"
    work.mkdir(parents=True)
    write_item(work, "a")
    (work.parent / "archive.txt").write_text("youtube a\n")
    backend = FakeBackend(("a",))
    events = run(backend)
    assert run.media() == ["2024-10-23 - Title a [a].mp3"]
    assert backend.requests == []
    assert events[-1] == FetchDone(saved=1, failed=0, skipped=0)


def test_unfinished_file_is_not_recovered(run: Run) -> None:
    work = run.folder / ".ytb-playlist" / "tmp"
    work.mkdir(parents=True)
    write_item(work, "a")
    backend = FakeBackend(("a",))
    run(backend)
    assert backend.requests[0].positions == (1,)


def test_existing_file_is_never_overwritten(run: Run) -> None:
    run.folder.mkdir(parents=True)
    target = run.folder / "2024-10-23 - Title a [a].mp3"
    target.write_bytes(b"yours")
    events = run(FakeBackend(("a",)))
    assert target.read_bytes() == b"yours"
    assert of_type(events, ItemSaved) == [ItemSaved("a", target)]


def test_damaged_metadata_fails_the_item_and_keeps_the_file(run: Run) -> None:
    class Damaged(FakeBackend):
        def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
            media = write_item(request.work_dir, "a")
            (request.work_dir / "a.info.json").write_text("{broken")
            yield DownloadSaved("a", media)

    events = run(Damaged(("a",)))
    assert of_type(events, ItemFailed)[0].kind == FailureKind.TEMPORARY
    assert events[-1] == FetchDone(saved=0, failed=1, skipped=0)
    assert (run.folder / ".ytb-playlist" / "tmp" / "a.mp3").exists()


def test_unexpected_extension_is_refused_as_permanent(run: Run) -> None:
    class WrongFormat(FakeBackend):
        def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
            yield DownloadSaved("a", write_item(request.work_dir, "a", "webm"))

    events = run(WrongFormat(("a",)))
    assert of_type(events, ItemFailed)[0].kind == FailureKind.PERMANENT
    assert events[-1] == FetchDone(saved=0, failed=0, skipped=1)
    assert run.media() == []
    assert (run.folder / ".ytb-playlist" / "tmp" / "a.webm").exists()


def test_thumbnail_that_was_not_converted_is_kept(run: Run) -> None:
    class Unconverted(FakeBackend):
        def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
            media = write_item(request.work_dir, "a")
            (request.work_dir / "a.jpg").rename(request.work_dir / "a.webp")
            yield DownloadSaved("a", media)

    run(Unconverted(("a",)))
    state_dir = run.folder / ".ytb-playlist"
    assert (state_dir / "thumbs" / "a.webp").read_bytes() == b"jpeg"
    assert not (state_dir / "tmp").exists()


def test_saved_path_outside_the_work_folder_is_refused(run: Run, tmp_path: Path) -> None:
    outside = tmp_path / "secret.mp3"
    outside.write_bytes(b"not ours")

    class Escaping(FakeBackend):
        def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
            write_item(request.work_dir, "a")
            yield DownloadSaved("a", outside)

    events = run(Escaping(("a",)))
    assert outside.exists()
    assert of_type(events, ItemFailed)[0].video_id == "a"
    assert run.media() == []


def test_metadata_for_another_item_is_refused(run: Run) -> None:
    class Mismatched(FakeBackend):
        def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
            media = write_item(request.work_dir, "a")
            (request.work_dir / "a.info.json").write_text('{"id": "other", "title": "T"}')
            yield DownloadSaved("a", media)

    events = run(Mismatched(("a",)))
    assert events[-1] == FetchDone(saved=0, failed=1, skipped=0)
    assert run.media() == []


def test_unsafe_id_in_a_saved_message_is_refused(run: Run) -> None:
    backend = FakeBackend(("a",), {"a": [DownloadSaved("../evil", Path("/x/y.mp3"))]})
    events = run(backend)
    assert events[-1].failed == 1


def test_unsafe_playlist_id_is_refused(tmp_path: Path) -> None:
    backend = FakeBackend()
    backend.info = PlaylistInfo("../evil", "T", ("a",))
    with pytest.raises(UnsafeIdError):
        fetch(URL, FetchOptions(MediaFormat.MP3, tmp_path), backend, no_tag, lambda _: None, TODAY)


def test_entries_without_an_id_are_not_requested(run: Run) -> None:
    backend = FakeBackend(("a", "", "c"))
    run(backend)
    assert backend.requests[0].positions == (1, 3)


def test_dry_run_reports_and_writes_nothing(run: Run) -> None:
    backend = FakeBackend()
    events = run(backend, dry_run=True)
    assert events == [FetchPlanned(run.folder, 3, 0)]
    assert backend.requests == []
    assert not run.root.exists()


def test_dry_run_leaves_a_crashed_file_alone(run: Run) -> None:
    work = run.folder / ".ytb-playlist" / "tmp"
    work.mkdir(parents=True)
    media = write_item(work, "a")
    (work.parent / "archive.txt").write_text("youtube a\n")
    run(FakeBackend(("a",)), dry_run=True)
    assert media.exists()


def test_retry_failed_requests_permanent_failures_again(run: Run) -> None:
    run(FakeBackend(outcomes={"b": [GONE]}))
    backend = FakeBackend()
    events = run(backend, retry_failed=True)
    assert backend.requests[0].positions == (2,)
    assert events[0] == FetchPlanned(run.folder, 1, 0)
    assert load_state(run.folder).failures == {}
    assert events[-1] == FetchDone(saved=1, failed=0, skipped=0)


def test_retry_that_fails_again_stays_permanent(run: Run) -> None:
    run(FakeBackend(("b",), {"b": [GONE]}))
    events = run(FakeBackend(("b",), {"b": [GONE]}), retry_failed=True)
    assert events[-1] == FetchDone(saved=0, failed=0, skipped=1)


def test_quality_settings_reach_the_backend(run: Run) -> None:
    backend = FakeBackend(("a",))
    run(backend, max_height=720, quality_max=True, sleep_min=1, sleep_max=2)
    request = backend.requests[0]
    assert (request.max_height, request.quality_max) == (720, True)
    assert (request.sleep_min, request.sleep_max) == (1, 2)


class PlaylistImage(FakeBackend):
    def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
        (request.work_dir / f"{PLAYLIST_ID}.jpg").write_bytes(b"playlist image")
        (request.work_dir / f"{PLAYLIST_ID}.info.json").write_text("{}")
        yield from super().download(request)


def test_playlist_cover_is_used_for_every_track(run: Run) -> None:
    backend = PlaylistImage(("a", "c"))
    run(backend, cover=CoverSource.PLAYLIST)
    assert backend.requests[0].playlist_cover
    assert [name for _, _, name in run.tagged] == [f"{PLAYLIST_ID}.jpg"] * 2
    thumbs = run.folder / ".ytb-playlist" / "thumbs"
    assert (thumbs / f"{PLAYLIST_ID}.jpg").read_bytes() == b"playlist image"
    assert not (run.folder / ".ytb-playlist" / "tmp").exists()


def test_episode_cover_is_the_default(run: Run) -> None:
    backend = FakeBackend(("a",))
    run(backend)
    assert not backend.requests[0].playlist_cover
    assert run.tagged[0][2] == "a.jpg"


def test_missing_playlist_image_falls_back_to_the_episode(run: Run) -> None:
    run(FakeBackend(("a",)), cover=CoverSource.PLAYLIST)
    assert run.tagged[0][2] == "a.jpg"


def test_playlist_files_are_cleared_even_if_every_item_fails(run: Run) -> None:
    run(PlaylistImage(("b",), {"b": [FLAKY]}), cover=CoverSource.PLAYLIST)
    assert not (run.folder / ".ytb-playlist" / "tmp").exists()


def test_clip_reaches_the_backend(run: Run) -> None:
    backend = FakeBackend(("a",))
    run(backend, clip_seconds=60)
    assert backend.requests[0].clip_seconds == 60


def test_items_option_limits_the_positions(run: Run) -> None:
    backend = FakeBackend()
    run(backend, items="2:3")
    assert backend.requests[0].positions == (2, 3)


def test_items_past_the_end_is_an_explicit_empty_outcome(run: Run) -> None:
    backend = FakeBackend()
    events = run(backend, items="90:95")
    assert backend.requests == []
    assert events == [FetchPlanned(run.folder, 0, 0), FetchDone(0, 0, 0)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, {1, 2, 3, 4, 5}),
        ("2", {2}),
        ("2:4", {2, 3, 4}),
        ("1,3:4", {1, 3, 4}),
        ("4:90", {4, 5}),
        (" 1 , 2 ", {1, 2}),
    ],
)
def test_parse_items(text: str | None, expected: set[int]) -> None:
    assert parse_items(text, 5) == expected


@pytest.mark.parametrize("text", ["", "a", "0", "3:1", "1:", ":2", "1:2:3", "-1"])
def test_bad_items_are_refused(text: str) -> None:
    with pytest.raises(ItemsError):
        parse_items(text, 5)


def test_recorded_two_stream_progress_restarts_for_each_stream(run: Run) -> None:
    lines = (FIXTURES / "ytdlp-two-stream.log").read_text().splitlines()
    messages = [message for line in lines if (message := parse_line(line))]

    class Replay(FakeBackend):
        def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
            for message in messages:
                if isinstance(message, DownloadSaved):
                    media = write_item(request.work_dir, "4oEFyaR6uiM", "mp4")
                    yield DownloadSaved(message.video_id, media)
                else:
                    yield message

    events = run(Replay(("4oEFyaR6uiM",)))
    percents = [event.percent for event in of_type(events, ItemProgress)]
    assert all(0 <= percent <= 100 for percent in percents)
    drops = [pair for pair in itertools.pairwise(percents) if pair[1] < pair[0]]
    assert len(drops) == 1
    assert drops[0][0] == 100


class Replaying(FakeBackend):
    def __init__(self, messages: list[DownloadMessage]) -> None:
        super().__init__(("a",))
        self.messages = messages

    def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
        yield from self.messages


def percents(run: Run, *messages: DownloadMessage) -> list[float]:
    return [e.percent for e in of_type(run(Replaying(list(messages))), ItemProgress)]


def test_progress_never_moves_backwards_within_a_stream(run: Run) -> None:
    assert percents(
        run,
        DownloadProgress("a", False, 50, 100),
        DownloadProgress("a", False, 50, 200),
        DownloadProgress("a", False, 150, 200),
    ) == [50, 50, 75]


def test_size_equal_to_the_estimate_is_not_read_as_complete(run: Run) -> None:
    assert percents(
        run,
        DownloadProgress("a", False, 1024, 1024),
        DownloadProgress("a", False, 500, 1000),
    ) == [50]


def test_finished_stream_is_complete(run: Run) -> None:
    assert percents(run, DownloadProgress("a", True, 10, 10)) == [100]


def test_second_stream_starts_again_from_its_own_progress(run: Run) -> None:
    assert percents(
        run,
        DownloadProgress("a", False, 90, 100),
        DownloadProgress("a", True, 100, 100),
        DownloadProgress("a", False, 10, 100),
    ) == [90, 100, 10]


def test_unknown_size_gives_no_percentage(run: Run) -> None:
    class Unknown(FakeBackend):
        def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
            yield DownloadProgress("a", False, 10, None)

    assert of_type(run(Unknown(("a",))), ItemProgress) == []


def test_state_from_an_earlier_run_is_kept(run: Run) -> None:
    state = PlaylistState(PLAYLIST_ID, MediaFormat.MP3, tagged={"old"})
    save_state(run.folder, state)
    run(FakeBackend(("a",)))
    assert load_state(run.folder).tagged == {"old", "a"}
