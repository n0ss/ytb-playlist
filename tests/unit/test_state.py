# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path

import pytest

from ytb_playlist.core import state as state_module
from ytb_playlist.core.models import Failure, FailureKind, MediaFormat
from ytb_playlist.core.state import (
    FolderConflictError,
    FormatChangeError,
    PlaylistState,
    StateError,
    find_folder,
    load_state,
    save_state,
)

PLAYLIST_ID = "PL9wDNu3ZrVQ63LOO81qh8-Ycq6-vIEqcg"


def new_state() -> PlaylistState:
    return PlaylistState(PLAYLIST_ID, MediaFormat.MP3)


def failure(kind: FailureKind) -> Failure:
    return Failure(kind, "some reason", "2026-11-04")


def test_no_output_root_means_no_folder(tmp_path: Path) -> None:
    assert find_folder(tmp_path / "missing", PLAYLIST_ID) is None


def test_folder_is_found_by_id_after_a_rename_on_youtube(tmp_path: Path) -> None:
    folder = tmp_path / f"Old title [{PLAYLIST_ID}]"
    folder.mkdir()
    assert find_folder(tmp_path, PLAYLIST_ID) == folder


def test_title_with_brackets_does_not_confuse_the_lookup(tmp_path: Path) -> None:
    folder = tmp_path / f"Show [2024] * ? [{PLAYLIST_ID}]"
    folder.mkdir()
    assert find_folder(tmp_path, PLAYLIST_ID) == folder


def test_another_playlist_is_not_matched(tmp_path: Path) -> None:
    (tmp_path / f"Other [x{PLAYLIST_ID}]").mkdir()
    (tmp_path / "Other [PLdifferent]").mkdir()
    assert find_folder(tmp_path, PLAYLIST_ID) is None


def test_a_file_with_a_matching_name_is_ignored(tmp_path: Path) -> None:
    (tmp_path / f"Title [{PLAYLIST_ID}]").write_text("not a folder")
    assert find_folder(tmp_path, PLAYLIST_ID) is None


def test_two_matching_folders_stop_with_an_error_naming_both(tmp_path: Path) -> None:
    first = tmp_path / f"First [{PLAYLIST_ID}]"
    second = tmp_path / f"Second [{PLAYLIST_ID}]"
    first.mkdir()
    second.mkdir()
    with pytest.raises(FolderConflictError) as error:
        find_folder(tmp_path, PLAYLIST_ID)
    assert first.name in str(error.value)
    assert second.name in str(error.value)


def test_state_round_trip(tmp_path: Path) -> None:
    state = new_state()
    state.tagged.add("abc")
    state.failures["def"] = failure(FailureKind.PERMANENT)
    save_state(tmp_path, state)
    assert load_state(tmp_path) == state


def test_no_state_file_is_none(tmp_path: Path) -> None:
    assert load_state(tmp_path) is None


def test_save_creates_the_state_folder(tmp_path: Path) -> None:
    save_state(tmp_path / "playlist", new_state())
    assert (tmp_path / "playlist" / ".ytb-playlist" / "state.json").exists()


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "[]",
        "{}",
        '{"version": 99, "playlist_id": "x", "format": "mp3", "tagged": [], "failures": {}}',
        '{"version": 1, "playlist_id": "x", "format": "ogg", "tagged": [], "failures": {}}',
        '{"version": 1, "playlist_id": "x", "format": "mp3", "tagged": 3, "failures": {}}',
        '{"version": 1, "playlist_id": "x", "format": "mp3", "tagged": [], "failures": {"a": 1}}',
    ],
)
def test_damaged_state_is_an_error_and_is_left_in_place(tmp_path: Path, content: str) -> None:
    path = tmp_path / ".ytb-playlist" / "state.json"
    path.parent.mkdir()
    path.write_text(content)
    with pytest.raises(StateError, match="state.json"):
        load_state(tmp_path)
    assert path.read_text() == content


def test_undecodable_state_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / ".ytb-playlist" / "state.json"
    path.parent.mkdir()
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(StateError):
        load_state(tmp_path)


def test_failed_save_keeps_the_previous_state_and_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_state(tmp_path, new_state())
    changed = new_state()
    changed.tagged.add("abc")

    def refuse(*_: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(state_module.os, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        save_state(tmp_path, changed)
    monkeypatch.undo()

    assert load_state(tmp_path) == new_state()
    assert [p.name for p in (tmp_path / ".ytb-playlist").iterdir()] == ["state.json"]


def test_saved_file_is_plain_json_with_stable_order(tmp_path: Path) -> None:
    state = new_state()
    state.tagged.update({"b", "a"})
    save_state(tmp_path, state)
    data = json.loads((tmp_path / ".ytb-playlist" / "state.json").read_text())
    assert data["tagged"] == ["a", "b"]
    assert data["format"] == "mp3"


def test_same_format_is_accepted() -> None:
    new_state().require_format(MediaFormat.MP3)


def test_format_change_is_refused() -> None:
    with pytest.raises(FormatChangeError, match="mp3"):
        new_state().require_format(MediaFormat.MP4)


def test_permanent_failures_are_listed_and_temporary_ones_are_not() -> None:
    state = new_state()
    state.failures["gone"] = failure(FailureKind.PERMANENT)
    state.failures["flaky"] = failure(FailureKind.TEMPORARY)
    assert state.permanent_failures() == {"gone"}
