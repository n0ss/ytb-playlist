# SPDX-License-Identifier: GPL-3.0-only
import io
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from PIL import Image

from ytb_playlist import cover
from ytb_playlist.tagging import apply
from ytb_playlist.tagging.apply import CoverMode, TaggingError, replace_cover, tag_file

INFO = {"id": "abc", "title": "Title", "upload_date": "20241023", "channel": "Radio Nova"}


def thumbnail(tmp_path: Path, size: tuple[int, int] = (1280, 720)) -> Path:
    path = tmp_path / "abc.jpg"
    Image.new("RGB", size, "blue").save(path)
    return path


def embedded_size(path: Path) -> tuple[int, int]:
    if path.suffix == ".mp3":
        data = ID3(path).getall("APIC")[0].data
    else:
        data = bytes(MP4(path)["covr"][0])
    return Image.open(io.BytesIO(data)).size


@pytest.mark.parametrize(("kind", "size"), [("mp3", (720, 720)), ("mp4", (1280, 720))])
def test_each_format_gets_its_cover_shape(
    media_file: Callable[[str], Path], tmp_path: Path, kind: str, size: tuple[int, int]
) -> None:
    path = media_file(kind)
    assert tag_file(path, INFO, thumbnail(tmp_path)) == ()
    assert embedded_size(path) == size


def test_cover_mode_overrides_the_default(
    media_file: Callable[[str], Path], tmp_path: Path
) -> None:
    path = media_file("mp3")
    tag_file(path, INFO, thumbnail(tmp_path), CoverMode.WIDE)
    assert embedded_size(path) == (1280, 720)


def test_missing_thumbnail_tags_without_a_cover_and_warns(
    media_file: Callable[[str], Path],
) -> None:
    path = media_file("mp3")
    warnings = tag_file(path, INFO, None)
    assert "no thumbnail" in warnings[0]
    assert str(ID3(path)["TPE1"]) == "Radio Nova"
    assert ID3(path).getall("APIC") == []


def test_damaged_thumbnail_tags_without_a_cover_and_warns(
    media_file: Callable[[str], Path], tmp_path: Path
) -> None:
    bad = tmp_path / "abc.jpg"
    bad.write_bytes(b"not an image")
    path = media_file("mp4")
    warnings = tag_file(path, INFO, bad)
    assert "unusable" in warnings[0]
    assert MP4(path)["\xa9ART"] == ["Radio Nova"]


def test_over_budget_cover_warns(
    media_file: Callable[[str], Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cover, "MAX_COVER_BYTES", 10)
    warnings = tag_file(media_file("mp3"), INFO, thumbnail(tmp_path))
    assert "budget" in warnings[0]


def test_unsupported_file_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "a.webm"
    path.write_bytes(b"x")
    with pytest.raises(TaggingError, match="webm"):
        tag_file(path, INFO, None)


@pytest.mark.parametrize("name", ["a.mp3", "a.mp4"])
def test_file_that_is_not_media_is_an_error(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_bytes(b"not media at all")
    with pytest.raises(TaggingError):
        tag_file(path, INFO, None)


def test_missing_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(TaggingError):
        tag_file(tmp_path / "gone.mp3", INFO, None)


@pytest.mark.parametrize("kind", ["mp3", "mp4"])
def test_replace_cover_changes_only_the_cover(
    media_file: Callable[[str], Path], tmp_path: Path, kind: str
) -> None:
    path = media_file(kind)
    tag_file(path, INFO, None)
    replace_cover(path, thumbnail(tmp_path))
    assert embedded_size(path) == ((720, 720) if kind == "mp3" else (1280, 720))
    artist = str(ID3(path)["TPE1"]) if kind == "mp3" else MP4(path)["\xa9ART"][0]
    assert artist == "Radio Nova"


def test_replace_cover_keeps_id3_version_2_3(
    media_file: Callable[[str], Path], tmp_path: Path
) -> None:
    path = media_file("mp3")
    tag_file(path, INFO, None)
    replace_cover(path, thumbnail(tmp_path))
    assert path.read_bytes()[:4] == b"ID3\x03"
    assert "TYER" in ID3(path, translate=False)


def test_replace_cover_needs_a_usable_thumbnail(
    media_file: Callable[[str], Path], tmp_path: Path
) -> None:
    bad = tmp_path / "abc.jpg"
    bad.write_bytes(b"nope")
    with pytest.raises(TaggingError):
        replace_cover(media_file("mp3"), bad)


def partial_write(path: Path, *_: object) -> None:
    with path.open("r+b") as file:
        file.write(b"half written")
    raise KeyboardInterrupt


@pytest.mark.parametrize("kind", ["mp3", "mp4"])
def test_interrupted_tagging_leaves_the_original_intact(
    media_file: Callable[[str], Path], monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    path = media_file(kind)
    before = path.read_bytes()
    monkeypatch.setitem(apply.WRITERS, path.suffix, partial_write)
    with pytest.raises(KeyboardInterrupt):
        tag_file(path, INFO, None)
    assert path.read_bytes() == before
    assert [p.name for p in path.parent.iterdir() if p.name.startswith(".")] == []


def test_failed_tagging_leaves_the_original_intact(
    media_file: Callable[[str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = media_file("mp3")
    before = path.read_bytes()

    def fail(target: Path, *_: object) -> None:
        target.write_bytes(b"damaged")
        raise OSError("disk full")

    monkeypatch.setitem(apply.WRITERS, ".mp3", fail)
    with pytest.raises(TaggingError):
        tag_file(path, INFO, None)
    assert path.read_bytes() == before


def test_interrupted_cover_change_leaves_the_original_intact(
    media_file: Callable[[str], Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = media_file("mp3")
    before = path.read_bytes()
    monkeypatch.setitem(apply.COVER_WRITERS, ".mp3", partial_write)
    with pytest.raises(KeyboardInterrupt):
        replace_cover(path, thumbnail(tmp_path))
    assert path.read_bytes() == before


def test_tagging_works_without_clone_support(
    media_file: Callable[[str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_clone(*_: object, **__: object) -> None:
        raise subprocess.CalledProcessError(1, "cp")

    monkeypatch.setattr(apply.subprocess, "run", no_clone)
    path = media_file("mp3")
    tag_file(path, INFO, None)
    assert str(ID3(path)["TPE1"]) == "Radio Nova"


def test_relative_name_starting_with_a_dash_is_safe(
    media_file: Callable[[str], Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = media_file("mp3").rename(tmp_path / "- odd name.mp3")
    monkeypatch.chdir(tmp_path)
    tag_file(Path(path.name), INFO, None)
    assert str(ID3(path)["TPE1"]) == "Radio Nova"
