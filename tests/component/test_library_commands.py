# SPDX-License-Identifier: GPL-3.0-only
import io
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from mutagen.id3 import ID3
from PIL import Image
from typer.testing import CliRunner

from ytb_playlist.cli.app import app
from ytb_playlist.core.models import MediaFormat
from ytb_playlist.core.state import PlaylistState, load_state, save_state

runner = CliRunner()
INFO = {"id": "abc", "title": "New name", "upload_date": "20241023", "channel": "Radio Nova"}
FINAL = "2024-10-23 - New name [abc].mp3"


class Library:
    def __init__(self, folder: Path, source: Path) -> None:
        self.folder = folder
        self.state_dir = folder / ".ytb-playlist"
        self.source = source

    def add(self, name: str = "2024-10-23 - Old name [abc].mp3", info: dict = INFO) -> Path:
        path = self.folder / name
        path.write_bytes(self.source.read_bytes())
        video_id = info["id"]
        (self.state_dir / f"{video_id}.info.json").write_text(json.dumps(info))
        return path

    def thumbnail(self, video_id: str = "abc") -> None:
        Image.new("RGB", (1280, 720), "blue").save(self.state_dir / "thumbs" / f"{video_id}.jpg")


@pytest.fixture
def library(
    tmp_path: Path, media_file: Callable[[str], Path], monkeypatch: pytest.MonkeyPatch
) -> Library:
    monkeypatch.setenv("COLUMNS", "200")
    folder = tmp_path / "Show [PLx]"
    (folder / ".ytb-playlist" / "thumbs").mkdir(parents=True)
    save_state(folder, PlaylistState("PLx", MediaFormat.MP3))
    return Library(folder, media_file("mp3"))


def cover_size(path: Path) -> tuple[int, int]:
    return Image.open(io.BytesIO(ID3(path).getall("APIC")[0].data)).size


def test_tag_writes_tags_and_records_them(library: Library) -> None:
    path = library.add()
    library.thumbnail()
    result = runner.invoke(app, ["tag", str(path)])
    assert result.exit_code == 0, result.output
    assert str(ID3(path)["TPE1"]) == "Radio Nova"
    assert cover_size(path) == (720, 720)
    assert load_state(library.folder).tagged == {"abc"}


def test_tag_accepts_a_folder(library: Library) -> None:
    path = library.add()
    assert runner.invoke(app, ["tag", str(library.folder)]).exit_code == 0
    assert str(ID3(path)["TPE1"]) == "Radio Nova"


def test_tag_cover_option_changes_the_shape(library: Library) -> None:
    path = library.add()
    library.thumbnail()
    runner.invoke(app, ["tag", str(path), "--cover", "wide"])
    assert cover_size(path) == (1280, 720)


def test_tag_shows_warnings(library: Library) -> None:
    result = runner.invoke(app, ["tag", str(library.add())])
    assert result.exit_code == 0
    assert "no thumbnail" in result.output


def test_tag_continues_past_a_bad_file_and_exits_1(library: Library) -> None:
    good = library.add()
    bad = library.folder / "not ours.mp3"
    bad.write_bytes(library.source.read_bytes())
    result = runner.invoke(app, ["tag", str(bad), str(good)])
    assert result.exit_code == 1
    assert "not ours.mp3" in result.stderr
    assert str(ID3(good)["TPE1"]) == "Radio Nova"


def test_tag_without_saved_metadata_exits_1(library: Library) -> None:
    path = library.folder / "2024-10-23 - T [zzz].mp3"
    path.write_bytes(library.source.read_bytes())
    result = runner.invoke(app, ["tag", str(path)])
    assert result.exit_code == 1
    assert "no saved metadata" in result.stderr


def test_metadata_for_another_item_is_refused(library: Library) -> None:
    path = library.add()
    (library.state_dir / "abc.info.json").write_text('{"id": "other"}')
    assert runner.invoke(app, ["tag", str(path)]).exit_code == 1


def test_damaged_metadata_is_refused(library: Library) -> None:
    path = library.add()
    (library.state_dir / "abc.info.json").write_text("{broken")
    assert runner.invoke(app, ["tag", str(path)]).exit_code == 1


def test_file_that_is_not_media_exits_1(library: Library) -> None:
    path = library.add()
    path.write_bytes(b"not media")
    assert runner.invoke(app, ["tag", str(path)]).exit_code == 1


def test_missing_path_exits_2(library: Library) -> None:
    assert runner.invoke(app, ["tag", str(library.folder / "gone.mp3")]).exit_code == 2


def test_folder_without_media_exits_2(library: Library) -> None:
    result = runner.invoke(app, ["tag", str(library.folder)])
    assert result.exit_code == 2
    assert "no MP3 or MP4" in result.stderr


def test_cover_replaces_only_the_cover(library: Library) -> None:
    path = library.add()
    runner.invoke(app, ["tag", str(path)])
    library.thumbnail()
    result = runner.invoke(app, ["cover", str(path)])
    assert result.exit_code == 0, result.output
    assert cover_size(path) == (720, 720)
    assert str(ID3(path)["TPE1"]) == "Radio Nova"


def test_cover_without_a_thumbnail_exits_1(library: Library) -> None:
    result = runner.invoke(app, ["cover", str(library.add())])
    assert result.exit_code == 1
    assert "no saved thumbnail" in result.stderr


def test_rename_dry_run_changes_nothing(library: Library) -> None:
    path = library.add()
    result = runner.invoke(app, ["rename", str(path), "--dry-run"])
    assert result.exit_code == 0
    assert FINAL in result.output
    assert path.exists()
    assert not (library.state_dir / "rename-log.jsonl").exists()


def test_rename_applies_the_naming_rules(library: Library) -> None:
    path = library.add()
    assert runner.invoke(app, ["rename", str(path)]).exit_code == 0
    assert not path.exists()
    assert (library.folder / FINAL).exists()


def test_rename_writes_an_undo_log(library: Library) -> None:
    path = library.add()
    runner.invoke(app, ["rename", str(path)])
    entry = json.loads((library.state_dir / "rename-log.jsonl").read_text())
    assert entry["from"] == path.name
    assert entry["to"] == FINAL


def test_rename_leaves_a_correct_name_alone(library: Library) -> None:
    library.add(FINAL)
    result = runner.invoke(app, ["rename", str(library.folder)])
    assert result.exit_code == 0
    assert "already named" in result.output
    assert not (library.state_dir / "rename-log.jsonl").exists()


def test_rename_never_overwrites(library: Library) -> None:
    path = library.add()
    target = library.folder / FINAL
    target.write_bytes(b"yours")
    result = runner.invoke(app, ["rename", str(path)])
    assert result.exit_code == 1
    assert path.exists()
    assert target.read_bytes() == b"yours"


def test_rename_stays_in_the_folder_with_a_hostile_title(library: Library) -> None:
    info = INFO | {"title": "../../escape"}
    path = library.add(info=info)
    assert runner.invoke(app, ["rename", str(path)]).exit_code == 0
    names = [p.name for p in library.folder.iterdir() if p.suffix == ".mp3"]
    assert len(names) == 1
    assert "/" not in names[0]
