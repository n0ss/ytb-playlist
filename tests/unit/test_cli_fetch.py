# SPDX-License-Identifier: GPL-3.0-only
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes import PLAYLIST_ID, FakeBackend
from typer.testing import CliRunner

from ytb_playlist.backends.base import (
    BackendError,
    DownloadError,
    DownloadMessage,
    DownloadRequest,
)
from ytb_playlist.cli import common
from ytb_playlist.cli.app import app
from ytb_playlist.core.models import FailureKind
from ytb_playlist.tagging.apply import TaggingError

runner = CliRunner()
URL = f"https://www.youtube.com/playlist?list={PLAYLIST_ID}"
GONE = DownloadError("b", FailureKind.PERMANENT, "This video is unavailable")
FLAKY = DownloadError("b", FailureKind.TEMPORARY, "timeout")


@pytest.fixture
def out(tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("COLUMNS", "200")
    return tmp_path / "out"


def use(monkeypatch: pytest.MonkeyPatch, backend: FakeBackend) -> FakeBackend:
    monkeypatch.setattr(common, "make_backend", lambda _config: backend)
    monkeypatch.setattr("ytb_playlist.cli.fetch.tag_file", lambda *_a, **_k: ())
    return backend


def fetch_cli(out: Path, *args: str):
    return runner.invoke(app, ["fetch", URL, "--format", "mp3", "--out", str(out), *args])


def test_fetch_saves_and_exits_0(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("a",)))
    result = fetch_cli(out)
    assert result.exit_code == 0, result.output
    assert "2024-10-23 - Title a [a].mp3" in result.output
    assert (out / f"My playlist [{PLAYLIST_ID}]" / "2024-10-23 - Title a [a].mp3").exists()


def test_permanent_failure_is_listed_and_exits_0(
    out: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use(monkeypatch, FakeBackend(("b",), {"b": [GONE]}))
    result = fetch_cli(out)
    assert result.exit_code == 0
    assert "This video is unavailable" in result.output


def test_temporary_failure_exits_1(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("b",), {"b": [FLAKY]}))
    result = fetch_cli(out)
    assert result.exit_code == 1
    assert "timeout" in result.output


def test_playlist_level_error_exits_4(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    message = DownloadError(None, FailureKind.TEMPORARY, "HTTP Error 400")
    use(monkeypatch, FakeBackend(("b",), {"b": [message]}))
    result = fetch_cli(out)
    assert result.exit_code == 4
    assert "HTTP Error 400" in result.stderr


def test_backend_error_exits_4(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Broken(FakeBackend):
        def playlist_info(self, url: str):
            raise BackendError("HTTP Error 400")

    use(monkeypatch, Broken())
    assert fetch_cli(out).exit_code == 4


def test_bad_url_exits_2(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend())
    result = runner.invoke(
        app, ["fetch", "https://vimeo.com/1", "--format", "mp3", "--out", str(out)]
    )
    assert result.exit_code == 2
    assert "not a YouTube URL" in result.stderr


def test_bad_items_exits_2(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend())
    assert fetch_cli(out, "--items", "x").exit_code == 2


def test_format_change_exits_2(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("a",)))
    fetch_cli(out)
    result = runner.invoke(app, ["fetch", URL, "--format", "mp4", "--out", str(out)])
    assert result.exit_code == 2
    assert "kept as mp3" in result.stderr


def test_two_matching_folders_exit_2(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend())
    (out / f"One [{PLAYLIST_ID}]").mkdir(parents=True)
    (out / f"Two [{PLAYLIST_ID}]").mkdir()
    assert fetch_cli(out).exit_code == 2


def test_damaged_state_exits_2(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend())
    state = out / f"My playlist [{PLAYLIST_ID}]" / ".ytb-playlist" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text("{broken")
    assert fetch_cli(out).exit_code == 2


def test_unsafe_playlist_id_exits_2(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = FakeBackend()
    backend.info = type(backend.info)("../evil", "T", ("a",))
    use(monkeypatch, backend)
    assert fetch_cli(out).exit_code == 2


def test_missing_tool_exits_3(install_tools, out: Path) -> None:
    install_tools("ffmpeg")
    result = fetch_cli(out)
    assert result.exit_code == 3
    assert "ffmpeg" in result.stderr


def test_output_root_that_is_a_file_exits_3(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("a",)))
    out.write_text("a file, not a folder")
    result = fetch_cli(out)
    assert result.exit_code == 3
    assert "Not a directory" in result.stderr


def test_full_disk_exits_3(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("a",)))

    def full(*_: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr("ytb_playlist.core.fetch.save_state", full)
    result = fetch_cli(out)
    assert result.exit_code == 3
    assert "No space left" in result.stderr


def test_tagging_failure_exits_1(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("a",)))

    def fail(*_: object, **__: object) -> tuple[str, ...]:
        raise TaggingError("bad file")

    monkeypatch.setattr("ytb_playlist.cli.fetch.tag_file", fail)
    result = fetch_cli(out)
    assert result.exit_code == 1
    assert "bad file" in result.output


def test_tagging_warning_is_shown(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("a",)))
    monkeypatch.setattr("ytb_playlist.cli.fetch.tag_file", lambda *_a, **_k: ("no cover found",))
    result = fetch_cli(out)
    assert result.exit_code == 0
    assert "no cover found" in result.output


def test_retagging_an_existing_file_is_reported(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("a",)))

    def fail(*_: object, **__: object) -> tuple[str, ...]:
        raise TaggingError("bad file")

    monkeypatch.setattr("ytb_playlist.cli.fetch.tag_file", fail)
    fetch_cli(out)
    monkeypatch.setattr("ytb_playlist.cli.fetch.tag_file", lambda *_a, **_k: ())
    result = fetch_cli(out)
    assert result.exit_code == 0
    assert "tagged a" in result.output
    assert "Nothing new" not in result.output


def test_format_is_required(out: Path) -> None:
    result = runner.invoke(app, ["fetch", URL, "--out", str(out)])
    assert result.exit_code == 2


def test_clipping_is_not_a_cli_option(out: Path) -> None:
    result = fetch_cli(out, "--clip-seconds", "60")
    assert result.exit_code == 2
    assert "No such option" in result.output


def test_dry_run_reports_without_writing(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = use(monkeypatch, FakeBackend())
    result = fetch_cli(out, "--dry-run")
    assert result.exit_code == 0
    assert "3 new" in result.output
    assert backend.requests == []
    assert not out.exists()


def test_nothing_new_is_said_out_loud(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("a",)))
    fetch_cli(out)
    result = fetch_cli(out)
    assert result.exit_code == 0
    assert "Nothing new" in result.output


def test_items_past_the_end_says_nothing_new(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("a",)))
    assert "Nothing new" in fetch_cli(out, "--items", "9000").output


def test_every_url_runs_and_the_worst_code_wins(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = use(monkeypatch, FakeBackend(("a",)))
    result = runner.invoke(
        app, ["fetch", "https://vimeo.com/1", URL, "--format", "mp3", "--out", str(out)]
    )
    assert result.exit_code == 2
    assert len(backend.requests) == 1


def test_output_root_comes_from_the_config(
    home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    use(monkeypatch, FakeBackend(("a",)))
    config = tmp_path / "c.toml"
    root = tmp_path / "configured"
    config.write_text(f'output_root = "{root}"\n')
    result = runner.invoke(app, ["--config", str(config), "fetch", URL, "--format", "mp3"])
    assert result.exit_code == 0, result.output
    assert (root / f"My playlist [{PLAYLIST_ID}]").is_dir()


def test_invalid_config_exits_2(home: Path, tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("output_root = [")
    result = runner.invoke(app, ["--config", str(bad), "fetch", URL, "--format", "mp3"])
    assert result.exit_code == 2


def test_titles_are_printed_as_text_not_markup(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("a",), title="[bold]Loud"))
    result = fetch_cli(out)
    assert result.exit_code == 0, result.output
    assert "[bold]Loud" in result.output


def test_reason_is_printed_as_text_not_markup(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    message = DownloadError("b", FailureKind.TEMPORARY, "[/oops] closing tag")
    use(monkeypatch, FakeBackend(("b",), {"b": [message]}))
    result = fetch_cli(out)
    assert result.exit_code == 1
    assert "[/oops] closing tag" in result.output


def test_interrupt_stops_with_a_nonzero_exit(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Interrupted(FakeBackend):
        def download(self, request: DownloadRequest) -> Iterator[DownloadMessage]:
            raise KeyboardInterrupt
            yield

    use(monkeypatch, Interrupted(("a",)))
    assert fetch_cli(out).exit_code != 0


def test_info_shows_title_id_and_count(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend())
    result = runner.invoke(app, ["info", URL])
    assert result.exit_code == 0, result.output
    for expected in ("My playlist", PLAYLIST_ID, "3"):
        assert expected in result.output


def test_info_downloads_nothing(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = use(monkeypatch, FakeBackend())
    runner.invoke(app, ["info", URL])
    assert backend.requests == []


def test_info_bad_url_exits_2(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend())
    assert runner.invoke(app, ["info", "https://vimeo.com/1"]).exit_code == 2


def test_info_backend_error_exits_4(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Broken(FakeBackend):
        def playlist_info(self, url: str):
            raise BackendError("network down")

    use(monkeypatch, Broken())
    result = runner.invoke(app, ["info", URL])
    assert result.exit_code == 4
    assert "network down" in result.stderr


def test_info_missing_tool_exits_3(install_tools, out: Path) -> None:
    install_tools("yt-dlp")
    assert runner.invoke(app, ["info", URL]).exit_code == 3
