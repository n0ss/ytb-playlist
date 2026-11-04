# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path

import pytest
from fakes import PLAYLIST_ID, FakeBackend
from typer.testing import CliRunner

from ytb_playlist.backends.base import BackendError, DownloadError
from ytb_playlist.cli import common
from ytb_playlist.cli.app import app
from ytb_playlist.config import default_config_dir
from ytb_playlist.core.models import FailureKind, MediaFormat, PlaylistInfo
from ytb_playlist.core.playlists import PlaylistEntry, load_playlists, save_playlists

runner = CliRunner()
URL = f"https://www.youtube.com/playlist?list={PLAYLIST_ID}"
GONE = DownloadError("b", FailureKind.PERMANENT, "This video is unavailable")
FLAKY = DownloadError("b", FailureKind.TEMPORARY, "timeout")


@pytest.fixture
def root(tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setenv("YTB_PLAYLIST_OUTPUT_ROOT", str(tmp_path / "root"))
    monkeypatch.setattr("ytb_playlist.cli.fetch.tag_file", lambda *_a, **_k: ())
    return tmp_path / "root"


def use(monkeypatch: pytest.MonkeyPatch, backend: FakeBackend) -> FakeBackend:
    monkeypatch.setattr(common, "make_backend", lambda _config: backend)
    return backend


def saved(*entries: PlaylistEntry) -> None:
    save_playlists(default_config_dir(), {entry.name: entry for entry in entries})


def entry(name: str = "Show", playlist_id: str = PLAYLIST_ID) -> PlaylistEntry:
    return PlaylistEntry(
        name,
        f"https://www.youtube.com/playlist?list={playlist_id}",
        playlist_id,
        MediaFormat.MP3,
    )


def test_add_saves_with_the_title_as_the_default_name(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use(monkeypatch, FakeBackend())
    result = runner.invoke(app, ["playlist", "add", URL, "--format", "mp3"])
    assert result.exit_code == 0, result.output
    saved_entry = load_playlists(default_config_dir())["My playlist"]
    assert (saved_entry.playlist_id, saved_entry.url) == (PLAYLIST_ID, URL)


def test_add_with_a_name_and_settings(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend())
    result = runner.invoke(
        app,
        ["playlist", "add", URL, "--format", "mp4", "--name", "Show", "--album", "A",
         "--genre", "Radio", "--cover", "playlist", "--max-height", "720"],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    saved_entry = load_playlists(default_config_dir())["Show"]
    assert (saved_entry.album, saved_entry.genre, saved_entry.max_height) == ("A", "Radio", 720)


def test_add_cleans_the_url(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend())
    runner.invoke(app, ["playlist", "add", f"{URL}&si=x", "--format", "mp3"])
    assert load_playlists(default_config_dir())["My playlist"].url == URL


def test_add_bad_url_exits_2(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend())
    assert runner.invoke(app, ["playlist", "add", "https://x.y", "--format", "mp3"]).exit_code == 2


def test_add_network_error_exits_4(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Broken(FakeBackend):
        def playlist_info(self, url: str) -> PlaylistInfo:
            raise BackendError("down")

    use(monkeypatch, Broken())
    assert runner.invoke(app, ["playlist", "add", URL, "--format", "mp3"]).exit_code == 4


def test_add_duplicate_exits_2(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend())
    runner.invoke(app, ["playlist", "add", URL, "--format", "mp3"])
    assert runner.invoke(app, ["playlist", "add", URL, "--format", "mp3"]).exit_code == 2


def test_list_shows_saved_playlists(root: Path) -> None:
    saved(entry())
    result = runner.invoke(app, ["playlist", "list"])
    assert result.exit_code == 0
    assert "Show" in result.output
    assert "mp3" in result.output


def test_list_when_empty(root: Path) -> None:
    assert "No saved playlists" in runner.invoke(app, ["playlist", "list"]).output


def test_list_prints_markup_as_text(root: Path) -> None:
    saved(entry("[bold]Loud"))
    assert "[bold]Loud" in runner.invoke(app, ["playlist", "list"]).output


def test_remove_leaves_the_files_alone(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("a",)))
    saved(entry())
    runner.invoke(app, ["sync", "Show"])
    folder = root / f"My playlist [{PLAYLIST_ID}]"
    files = sorted(p.name for p in folder.iterdir())
    result = runner.invoke(app, ["playlist", "remove", "Show"])
    assert result.exit_code == 0
    assert load_playlists(default_config_dir()) == {}
    assert sorted(p.name for p in folder.iterdir()) == files


def test_remove_unknown_exits_2(root: Path) -> None:
    assert runner.invoke(app, ["playlist", "remove", "Nope"]).exit_code == 2


def test_sync_downloads_only_new_items(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("a",)))
    saved(entry())
    assert runner.invoke(app, ["sync", "Show"]).exit_code == 0
    backend = use(monkeypatch, FakeBackend(("new", "a")))
    result = runner.invoke(app, ["sync", "Show"])
    assert result.exit_code == 0
    assert backend.requests[0].positions == (1,)


def test_sync_uses_the_saved_format(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = use(monkeypatch, FakeBackend(("a",)))
    saved(PlaylistEntry("Show", URL, PLAYLIST_ID, MediaFormat.MP4, max_height=480))
    runner.invoke(app, ["sync", "Show"])
    assert backend.requests[0].format == MediaFormat.MP4
    assert backend.requests[0].max_height == 480


def test_sync_applies_album_and_genre_to_the_tags(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use(monkeypatch, FakeBackend(("a",)))
    calls = []
    monkeypatch.setattr(
        "ytb_playlist.cli.fetch.tag_file",
        lambda *_a, **kwargs: calls.append(kwargs) or (),
    )
    saved(PlaylistEntry("Show", URL, PLAYLIST_ID, MediaFormat.MP3, album="A", genre="Radio"))
    runner.invoke(app, ["sync", "Show"])
    assert calls == [{"album": "A", "genre": "Radio"}]


class ByUrl(FakeBackend):
    def playlist_info(self, url: str) -> PlaylistInfo:
        return PlaylistInfo(url.rpartition("=")[2], "My playlist", ("a",))


def test_sync_all_runs_every_playlist(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = use(monkeypatch, ByUrl(("a",)))
    saved(entry("One", "PLone"), entry("Two", "PLtwo"))
    result = runner.invoke(app, ["sync", "--all"])
    assert result.exit_code == 0, result.output
    assert len(backend.requests) == 2
    assert "One" in result.output
    assert "Two" in result.output


def test_sync_all_continues_past_a_failure_and_the_worst_code_wins(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FirstFails(FakeBackend):
        def playlist_info(self, url: str) -> PlaylistInfo:
            if "PLbad" in url:
                raise BackendError("down")
            return super().playlist_info(url)

    backend = use(monkeypatch, FirstFails(("a",)))
    saved(entry("Bad", "PLbad"), entry("Good"))
    result = runner.invoke(app, ["sync", "--all"])
    assert result.exit_code == 4
    assert len(backend.requests) == 1


def test_sync_retry_failed(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend(("b",), {"b": [GONE]}))
    saved(entry())
    runner.invoke(app, ["sync", "Show"])
    backend = use(monkeypatch, FakeBackend(("b",)))
    assert runner.invoke(app, ["sync", "Show"]).exit_code == 0
    assert backend.requests == []
    runner.invoke(app, ["sync", "Show", "--retry-failed"])
    assert backend.requests[0].positions == (1,)


def test_sync_dry_run_reports_and_writes_nothing(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = use(monkeypatch, FakeBackend())
    saved(entry())
    result = runner.invoke(app, ["sync", "Show", "--dry-run"])
    assert result.exit_code == 0
    assert "3 new" in result.output
    assert backend.requests == []
    assert not root.exists()


def test_sync_needs_a_name_or_all(root: Path) -> None:
    assert runner.invoke(app, ["sync"]).exit_code == 2


def test_sync_refuses_a_name_with_all(root: Path) -> None:
    saved(entry())
    assert runner.invoke(app, ["sync", "Show", "--all"]).exit_code == 2


def test_sync_unknown_name_exits_2(root: Path) -> None:
    result = runner.invoke(app, ["sync", "Nope"])
    assert result.exit_code == 2
    assert "no saved playlist" in result.stderr


def test_sync_all_with_nothing_saved_says_so(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeBackend())
    result = runner.invoke(app, ["sync", "--all"])
    assert result.exit_code == 0
    assert "No saved playlists" in result.output


def test_damaged_playlists_file_exits_2(root: Path) -> None:
    folder = default_config_dir()
    folder.mkdir(parents=True)
    (folder / "playlists.toml").write_text("broken = [")
    assert runner.invoke(app, ["playlist", "list"]).exit_code == 2
    assert runner.invoke(app, ["sync", "--all"]).exit_code == 2


def test_fetch_quality_flags_reach_the_backend(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = use(monkeypatch, FakeBackend(("a",)))
    runner.invoke(app, ["fetch", URL, "--format", "mp4", "--max-height", "480", "--quality", "max"])
    assert (backend.requests[0].max_height, backend.requests[0].quality_max) == (480, True)


def test_fetch_cover_flag_reaches_the_backend(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = use(monkeypatch, FakeBackend(("a",)))
    runner.invoke(app, ["fetch", URL, "--format", "mp3", "--cover", "playlist"])
    assert backend.requests[0].playlist_cover


def test_fetch_uses_config_defaults(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YTB_PLAYLIST_MAX_HEIGHT", "360")
    backend = use(monkeypatch, FakeBackend(("a",)))
    runner.invoke(app, ["fetch", URL, "--format", "mp4"])
    assert backend.requests[0].max_height == 360


def test_config_path_prints_the_file(root: Path) -> None:
    result = runner.invoke(app, ["config", "path"])
    assert result.exit_code == 0
    assert "config.toml" in result.output


def test_config_show_keeps_long_paths_whole(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "40")
    assert str(root) in runner.invoke(app, ["config", "show"]).output


def test_config_show_prints_the_merged_values(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YTB_PLAYLIST_GENRE", "From env")
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "From env" in result.output
    assert str(root) in result.output
