# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path

import pytest

from ytb_playlist.backends.base import (
    BackendError,
    DownloadError,
    DownloadProgress,
    DownloadRequest,
    DownloadSaved,
)
from ytb_playlist.backends.ytdlp_proc import (
    YtDlpBackend,
    download_args,
    parse_line,
    parse_playlist,
)
from ytb_playlist.core.models import FailureKind, MediaFormat

FIXTURES = Path(__file__).parent.parent / "fixtures"
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL9wDNu3ZrVQ63LOO81qh8-Ycq6-vIEqcg"


def request(**fields: object) -> DownloadRequest:
    values = {
        "url": PLAYLIST_URL,
        "work_dir": Path("/work"),
        "archive": Path("/state/archive.txt"),
        "format": MediaFormat.MP3,
        "positions": (3, 5),
        "clip_seconds": None,
    }
    return DownloadRequest(**(values | fields))


def backend_with(tmp_path: Path, script: str) -> YtDlpBackend:
    stub = tmp_path / "yt-dlp"
    stub.write_text(f"#!/bin/sh\n{script}\n")
    stub.chmod(0o755)
    return YtDlpBackend(stub, Path("/opt/ffmpeg"), Path("/opt/deno"))


def test_progress_line_with_a_known_total() -> None:
    line = "PROGRESS 4oEFyaR6uiM|downloading|1024|35979484|NA"
    assert parse_line(line) == DownloadProgress("4oEFyaR6uiM", False, 1024, 35979484)


def test_progress_line_uses_the_estimate_when_the_total_is_unknown() -> None:
    line = "PROGRESS 4oEFyaR6uiM|downloading|2885696|NA|54353293.473684214"
    assert parse_line(line) == DownloadProgress("4oEFyaR6uiM", False, 2885696, 54353293)


def test_progress_line_without_any_total() -> None:
    assert parse_line("PROGRESS id|downloading|10|NA|NA") == DownloadProgress("id", False, 10, None)


def test_finished_progress_line_is_marked() -> None:
    line = "PROGRESS 4oEFyaR6uiM|finished|55381040|55381040|NA"
    assert parse_line(line) == DownloadProgress("4oEFyaR6uiM", True, 55381040, 55381040)


def test_saved_line_keeps_a_path_with_a_separator_in_it() -> None:
    assert parse_line("SAVED abc|/work/a|b.mp3") == DownloadSaved("abc", Path("/work/a|b.mp3"))


@pytest.mark.parametrize(
    "line",
    [
        "",
        "WARNING: [youtube:tab] YouTube said: INFO - 2 unavailable videos are hidden",
        "size=    1800KiB time=00:05:00.00 bitrate=  49.1kbits/s speed= 506x",
        "[https @ 0x10f8be000] Opening 'https://rr4.example/videoplayback'",
        "PROGRESS not|enough",
        "PROGRESS id|downloading|many|NA|NA",
        "SAVED no-separator",
    ],
)
def test_other_lines_are_ignored(line: str) -> None:
    assert parse_line(line) is None


@pytest.mark.parametrize(
    ("line", "video_id", "kind"),
    [
        ("ERROR: [youtube] aaaaaaaaaaa: This video is unavailable", "aaaaaaaaaaa", "permanent"),
        (
            "ERROR: [youtube] abc: Requested format is not available. Use --list-formats",
            "abc",
            "permanent",
        ),
        ("ERROR: [youtube] abc: Private video. Sign in", "abc", "permanent"),
        ("ERROR: [youtube] abc: Sign in to confirm you're not a bot", "abc", "temporary"),
        ("ERROR: [youtube] abc: Unable to download API page: timeout", "abc", "temporary"),
        ("ERROR: [youtube] abc: something nobody has seen", "abc", "temporary"),
        ("ERROR: [youtube:tab] PLaaaa: HTTP Error 400: Bad Request", None, "temporary"),
        ("ERROR: unable to write file", None, "temporary"),
    ],
)
def test_error_lines_are_classified(line: str, video_id: str | None, kind: str) -> None:
    message = parse_line(line)
    assert isinstance(message, DownloadError)
    assert message.video_id == video_id
    assert message.kind == FailureKind(kind)


def test_error_reason_is_kept() -> None:
    message = parse_line("ERROR: [youtube] abc: This video is unavailable")
    assert message.reason == "This video is unavailable"


def test_recorded_failures_all_parse() -> None:
    lines = (FIXTURES / "ytdlp-failures.log").read_text().splitlines()
    messages = [message for line in lines if (message := parse_line(line))]
    assert [(m.video_id, m.kind) for m in messages] == [
        ("aaaaaaaaaaa", FailureKind.PERMANENT),
        ("PiZNuhbUERY", FailureKind.PERMANENT),
        ("PiZNuhbUERY", FailureKind.TEMPORARY),
        (None, FailureKind.TEMPORARY),
    ]


def test_recorded_two_stream_download_parses() -> None:
    lines = (FIXTURES / "ytdlp-two-stream.log").read_text().splitlines()
    messages = [message for line in lines if (message := parse_line(line))]
    assert sum(isinstance(m, DownloadProgress) and m.finished for m in messages) == 2
    assert messages[-1] == DownloadSaved("4oEFyaR6uiM", Path("/WORK/4oEFyaR6uiM.mp4"))


def test_recorded_playlist_listing_parses() -> None:
    info = parse_playlist((FIXTURES / "ytdlp-flat-playlist.json").read_text())
    assert info.id == "PL9wDNu3ZrVQ63LOO81qh8-Ycq6-vIEqcg"
    assert info.title == 'Les essais de "L\'été"'
    assert info.item_ids[:3] == ("PiZNuhbUERY", "LYCiEm4JEkU", "4oEFyaR6uiM")
    assert info.item_count == 5


def test_listing_keeps_the_position_of_an_entry_without_an_id() -> None:
    text = '{"id": "PL1", "title": "T", "entries": [{"id": "a"}, null, {"id": "c"}]}'
    assert parse_playlist(text).item_ids == ("a", "", "c")


@pytest.mark.parametrize("text", ["not json", "[]", '{"title": "T", "entries": []}'])
def test_unusable_listing_is_an_error(text: str) -> None:
    with pytest.raises(BackendError):
        parse_playlist(text)


def test_mp3_arguments() -> None:
    args = download_args(request())
    assert args[args.index("--audio-format") + 1] == "mp3"
    assert args[args.index("--playlist-items") + 1] == "3,5"
    assert args[args.index("--download-archive") + 1] == "/state/archive.txt"
    assert args[args.index("-P") + 1] == "/work"
    assert args[args.index("-o") + 1] == "%(id)s.%(ext)s"
    assert args[-1] == PLAYLIST_URL


def test_mp4_keeps_to_h264_and_aac() -> None:
    args = download_args(request(format=MediaFormat.MP4))
    assert "avc1" in args[args.index("-f") + 1]
    assert args[args.index("--merge-output-format") + 1] == "mp4"
    assert "--audio-format" not in args


def test_clipping_is_off_unless_requested() -> None:
    assert "--download-sections" not in download_args(request())
    args = download_args(request(clip_seconds=60))
    assert args[args.index("--download-sections") + 1] == "*0-60"


def test_no_dangerous_option_is_ever_passed() -> None:
    args = download_args(request())
    assert not {"--exec", "--netrc-cmd", "--write-link", "--downloader"} & set(args)


def test_download_turns_output_into_messages(tmp_path: Path) -> None:
    fixture = FIXTURES / "ytdlp-two-stream.log"
    backend = backend_with(tmp_path, f"cat '{fixture}'")
    messages = list(backend.download(request()))
    assert messages[-1] == DownloadSaved("4oEFyaR6uiM", Path("/WORK/4oEFyaR6uiM.mp4"))


def test_binaries_and_config_isolation_reach_yt_dlp(tmp_path: Path) -> None:
    argv = tmp_path / "argv.txt"
    backend = backend_with(tmp_path, f"printf '%s\\n' \"$@\" > '{argv}'")
    list(backend.download(request()))
    args = argv.read_text().splitlines()
    assert args[0] == "--ignore-config"
    assert args[args.index("--ffmpeg-location") + 1] == "/opt/ffmpeg"
    assert args[args.index("--js-runtimes") + 1] == "deno:/opt/deno"


def test_exit_1_with_an_error_line_is_a_normal_partial_run(tmp_path: Path) -> None:
    backend = backend_with(tmp_path, "echo 'ERROR: [youtube] abc: Private video'; exit 1")
    assert len(list(backend.download(request()))) == 1


def test_exit_1_without_an_error_line_is_a_backend_error(tmp_path: Path) -> None:
    backend = backend_with(tmp_path, "exit 1")
    with pytest.raises(BackendError, match="exit 1"):
        list(backend.download(request()))


def test_unexpected_exit_code_is_a_backend_error(tmp_path: Path) -> None:
    backend = backend_with(tmp_path, "echo 'ERROR: [youtube] abc: x'; exit 2")
    with pytest.raises(BackendError, match="exit 2"):
        list(backend.download(request()))


def test_stopping_early_ends_the_process(tmp_path: Path) -> None:
    marker = tmp_path / "survived"
    backend = backend_with(tmp_path, f"echo 'SAVED a|/w/a.mp3'; sleep 2; touch '{marker}'")
    stream = backend.download(request())
    next(stream)
    stream.close()
    assert not marker.exists()


def test_undecodable_output_does_not_crash(tmp_path: Path) -> None:
    backend = backend_with(tmp_path, r"printf '\377\376\n'; echo 'SAVED a|/w/a.mp3'")
    assert list(backend.download(request())) == [DownloadSaved("a", Path("/w/a.mp3"))]


def test_playlist_info_reads_the_flat_listing(tmp_path: Path) -> None:
    fixture = FIXTURES / "ytdlp-flat-playlist.json"
    backend = backend_with(tmp_path, f"cat '{fixture}'")
    assert backend.playlist_info(PLAYLIST_URL).item_count == 5


def test_playlist_info_reports_yt_dlp_s_error(tmp_path: Path) -> None:
    backend = backend_with(tmp_path, "echo 'ERROR: [youtube:tab] PLa: HTTP Error 400' >&2; exit 1")
    with pytest.raises(BackendError, match="HTTP Error 400"):
        backend.playlist_info(PLAYLIST_URL)


def test_height_cap_is_applied_to_every_format_choice() -> None:
    selector = download_args(request(format=MediaFormat.MP4, max_height=720))
    selector = selector[selector.index("-f") + 1]
    assert selector.count("height<=720") == 2
    assert "1080" not in selector


def test_quality_max_lifts_the_cap_and_allows_any_stream() -> None:
    args = download_args(request(format=MediaFormat.MP4, quality_max=True))
    selector = args[args.index("-f") + 1]
    assert "height<=" not in selector
    assert selector.endswith("/bv*+ba/b")
    assert args[args.index("--merge-output-format") + 1] == "mp4"


def test_quality_options_do_not_touch_mp3() -> None:
    assert "-f" not in download_args(request(quality_max=True, max_height=480))


def test_sleep_settings_reach_yt_dlp() -> None:
    args = download_args(request(sleep_min=1, sleep_max=2))
    assert args[args.index("--sleep-interval") + 1] == "1"
    assert args[args.index("--max-sleep-interval") + 1] == "2"


def test_playlist_image_is_only_requested_when_needed() -> None:
    assert "--no-write-playlist-metafiles" in download_args(request())
    assert "--no-write-playlist-metafiles" not in download_args(request(playlist_cover=True))
