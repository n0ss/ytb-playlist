# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path

import pytest

from ytb_playlist.config import Config
from ytb_playlist.core.models import CoverSource, MediaFormat
from ytb_playlist.core.playlists import (
    PLAYLISTS_FILE,
    PlaylistEntry,
    PlaylistsError,
    TagSettings,
    add_playlist,
    fetch_options,
    find_entry,
    load_playlists,
    remove_playlist,
    save_playlists,
    tag_settings,
)

URL = "https://www.youtube.com/playlist?list=PLone"
ENTRY = PlaylistEntry("Show", URL, "PLone", MediaFormat.MP3)
FULL = PlaylistEntry(
    'Émission "spéciale"',
    "https://www.youtube.com/playlist?list=PLtwo",
    "PLtwo",
    MediaFormat.MP4,
    album='Album "quoted"\\ here',
    genre="Radio",
    cover=CoverSource.PLAYLIST,
    max_height=720,
)
CONFIG = Config(Path("/root"), {}, genre="Global", max_height=1080, sleep_min=1, sleep_max=2)


def test_no_file_means_no_playlists(tmp_path: Path) -> None:
    assert load_playlists(tmp_path) == {}


def test_round_trip_keeps_every_field_and_awkward_text(tmp_path: Path) -> None:
    entries = {ENTRY.name: ENTRY, FULL.name: FULL}
    save_playlists(tmp_path, entries)
    assert load_playlists(tmp_path) == entries


def test_save_creates_the_folder(tmp_path: Path) -> None:
    save_playlists(tmp_path / "new", {ENTRY.name: ENTRY})
    assert (tmp_path / "new" / PLAYLISTS_FILE).exists()


def test_failed_save_keeps_the_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_playlists(tmp_path, {ENTRY.name: ENTRY})

    def refuse(*_: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        save_playlists(tmp_path, {})
    monkeypatch.undo()
    assert load_playlists(tmp_path) == {ENTRY.name: ENTRY}
    assert [p.name for p in tmp_path.iterdir()] == [PLAYLISTS_FILE]


@pytest.mark.parametrize(
    "content",
    [
        "broken = [",
        '[playlists.a]\nurl = "x"\n',
        '[playlists.a]\nurl = "x"\nplaylist_id = "p"\nformat = "ogg"\n',
        '[playlists.a]\nurl = "x"\nplaylist_id = "p"\nformat = "mp3"\nmax_height = "tall"\n',
        '[playlists.a]\nurl = "x"\nplaylist_id = "p"\nformat = "mp3"\nmax_height = true\n',
        '[playlists.a]\nurl = "x"\nplaylist_id = "p"\nformat = "mp3"\ncover = "wide"\n',
        '[playlists.a]\nurl = 3\nplaylist_id = "p"\nformat = "mp3"\n',
        'playlists = "x"\n',
    ],
)
def test_damaged_file_is_an_error_and_is_left_alone(tmp_path: Path, content: str) -> None:
    (tmp_path / PLAYLISTS_FILE).write_text(content)
    with pytest.raises(PlaylistsError, match=PLAYLISTS_FILE):
        load_playlists(tmp_path)
    assert (tmp_path / PLAYLISTS_FILE).read_text() == content


def test_add_saves_the_entry(tmp_path: Path) -> None:
    add_playlist(tmp_path, ENTRY)
    assert load_playlists(tmp_path) == {"Show": ENTRY}


def test_add_refuses_a_name_already_in_use(tmp_path: Path) -> None:
    add_playlist(tmp_path, ENTRY)
    with pytest.raises(PlaylistsError, match="Show"):
        add_playlist(tmp_path, FULL.__class__("Show", FULL.url, "PLtwo", MediaFormat.MP3))


def test_add_refuses_a_playlist_saved_under_another_name(tmp_path: Path) -> None:
    add_playlist(tmp_path, ENTRY)
    with pytest.raises(PlaylistsError, match="already saved as Show"):
        add_playlist(tmp_path, PlaylistEntry("Other", URL, "PLone", MediaFormat.MP3))


def test_remove_deletes_only_that_entry(tmp_path: Path) -> None:
    save_playlists(tmp_path, {ENTRY.name: ENTRY, FULL.name: FULL})
    remove_playlist(tmp_path, ENTRY.name)
    assert load_playlists(tmp_path) == {FULL.name: FULL}


def test_remove_of_an_unknown_name_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(PlaylistsError, match="no saved playlist"):
        remove_playlist(tmp_path, "Nope")


def test_options_come_from_the_config_by_default() -> None:
    options = fetch_options(CONFIG, MediaFormat.MP3, ENTRY)
    assert options.format == MediaFormat.MP3
    assert options.output_root == Path("/root")
    assert (options.max_height, options.sleep_min, options.sleep_max) == (1080, 1, 2)
    assert options.cover == CoverSource.EPISODE


def test_playlist_settings_beat_the_config() -> None:
    options = fetch_options(CONFIG, MediaFormat.MP4, FULL)
    assert (options.format, options.max_height) == (MediaFormat.MP4, 720)
    assert options.cover == CoverSource.PLAYLIST


def test_cli_values_beat_the_playlist_settings() -> None:
    options = fetch_options(
        CONFIG, MediaFormat.MP4, FULL, max_height=480, cover=CoverSource.EPISODE
    )
    assert (options.max_height, options.cover) == (480, CoverSource.EPISODE)


def test_retry_failed_is_passed_on() -> None:
    assert fetch_options(CONFIG, MediaFormat.MP3, retry_failed=True).retry_failed


def test_output_root_override() -> None:
    options = fetch_options(CONFIG, MediaFormat.MP3, output_root=Path("/o"))
    assert options.output_root == Path("/o")


def test_options_work_without_a_saved_playlist() -> None:
    options = fetch_options(CONFIG, MediaFormat.MP4)
    assert (options.format, options.max_height) == (MediaFormat.MP4, 1080)


def test_entry_is_found_by_playlist_id() -> None:
    assert find_entry({ENTRY.name: ENTRY, FULL.name: FULL}, "PLtwo") == FULL
    assert find_entry({ENTRY.name: ENTRY}, "PLnone") is None


def test_tag_settings_come_from_the_config_without_an_entry() -> None:
    assert tag_settings(CONFIG, None) == TagSettings(None, "Global", CoverSource.EPISODE)


def test_tag_settings_prefer_the_saved_playlist() -> None:
    settings = tag_settings(CONFIG, FULL)
    assert settings == TagSettings(FULL.album, "Radio", CoverSource.PLAYLIST)
