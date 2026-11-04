# SPDX-License-Identifier: GPL-3.0-only
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from mutagen.id3 import ID3
from mutagen.mp4 import MP4, MP4Cover

from ytb_playlist.tagging.id3 import write_id3
from ytb_playlist.tagging.mapping import TrackTags
from ytb_playlist.tagging.mp4 import write_mp4

TAGS = TrackTags(
    title="2024-10-23 - La dernière",
    artist="Radio Nova",
    album='Les intégrales de "La dernière"',
    album_artist="Le Label",
    track=7,
    date="2024-10-23",
    genre="YouTube",
    description="Été 🎵\nsecond line",
    url="https://www.youtube.com/watch?v=abc",
    video_id="abc",
)
BARE = TrackTags("T", "", "", "", None, None, "", "", "", "abc")


def still_decodes(path: Path) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], check=True)


def test_id3_round_trip(media_file: Callable[[str], Path], jpeg: bytes) -> None:
    path = media_file("mp3")
    write_id3(path, TAGS, jpeg)
    tags = ID3(path, translate=False)
    assert str(tags["TIT2"]) == TAGS.title
    assert str(tags["TPE1"]) == "Radio Nova"
    assert str(tags["TALB"]) == TAGS.album
    assert str(tags["TPE2"]) == "Le Label"
    assert str(tags["TRCK"]) == "7"
    assert str(tags["TYER"]) == "2024"
    assert str(tags["TDAT"]) == "2310"
    assert str(tags["TCON"]) == "YouTube"
    assert tags.getall("COMM")[0].text == [TAGS.description]
    assert tags.getall("COMM")[0].lang == "eng"
    assert tags.getall("WOAS")[0].url == TAGS.url
    assert tags.getall("TXXX:YOUTUBE_ID")[0].text == ["abc"]
    picture = tags.getall("APIC")[0]
    assert (picture.type, picture.mime, picture.data) == (3, "image/jpeg", jpeg)
    still_decodes(path)


def test_id3_is_version_2_3_without_id3v1(media_file: Callable[[str], Path], jpeg: bytes) -> None:
    path = media_file("mp3")
    with path.open("ab") as file:
        file.write(b"TAG".ljust(128, b"\0"))
    write_id3(path, TAGS, jpeg)
    data = path.read_bytes()
    assert data[:4] == b"ID3\x03"
    assert data[-128:-125] != b"TAG"
    assert "TDRC" not in ID3(path, translate=False)


def test_id3_replaces_what_ffmpeg_wrote(media_file: Callable[[str], Path]) -> None:
    path = media_file("mp3")
    assert "ffmpeg title" in str(ID3(path).get("TIT2"))
    write_id3(path, TAGS, None)
    assert "TSSE" not in ID3(path, translate=False)
    assert str(ID3(path)["TIT2"]) == TAGS.title


def test_id3_leaves_out_empty_values(media_file: Callable[[str], Path]) -> None:
    path = media_file("mp3")
    write_id3(path, BARE, None)
    assert sorted(key.split(":")[0] for key in ID3(path, translate=False)) == ["TIT2", "TXXX"]


def test_id3_retag_keeps_a_single_set_of_frames(
    media_file: Callable[[str], Path], jpeg: bytes
) -> None:
    path = media_file("mp3")
    write_id3(path, TAGS, jpeg)
    write_id3(path, TAGS, jpeg)
    assert len(ID3(path, translate=False).getall("APIC")) == 1


def test_mp4_round_trip(media_file: Callable[[str], Path], jpeg: bytes) -> None:
    path = media_file("mp4")
    write_mp4(path, TAGS, jpeg)
    tags = MP4(path)
    assert tags["\xa9nam"] == [TAGS.title]
    assert tags["\xa9ART"] == ["Radio Nova"]
    assert tags["\xa9alb"] == [TAGS.album]
    assert tags["aART"] == ["Le Label"]
    assert tags["trkn"] == [(7, 0)]
    assert tags["\xa9day"] == ["2024-10-23"]
    assert tags["\xa9gen"] == ["YouTube"]
    assert tags["desc"] == [TAGS.description]
    assert tags["ldes"] == [TAGS.description]
    assert bytes(tags["----:com.apple.iTunes:URL"][0]).decode() == TAGS.url
    assert bytes(tags["----:com.apple.iTunes:YOUTUBE_ID"][0]) == b"abc"
    assert bytes(tags["covr"][0]) == jpeg
    assert tags["covr"][0].imageformat == MP4Cover.FORMAT_JPEG
    still_decodes(path)


def test_mp4_has_no_media_kind(media_file: Callable[[str], Path]) -> None:
    path = media_file("mp4")
    write_mp4(path, TAGS, None)
    assert "stik" not in MP4(path)


def test_mp4_short_description_is_cut_and_long_one_is_whole(
    media_file: Callable[[str], Path],
) -> None:
    path = media_file("mp4")
    long = TrackTags(*(TAGS.__dict__ | {"description": "x" * 4000}).values())
    write_mp4(path, long, None)
    assert len(MP4(path)["desc"][0]) == 255
    assert len(MP4(path)["ldes"][0]) == 4000


def test_mp4_replaces_what_ffmpeg_wrote(media_file: Callable[[str], Path]) -> None:
    path = media_file("mp4")
    assert "\xa9too" in MP4(path)
    write_mp4(path, BARE, None)
    assert sorted(MP4(path).keys()) == ["----:com.apple.iTunes:YOUTUBE_ID", "\xa9nam"]


@pytest.mark.parametrize(("kind", "write"), [("mp3", write_id3), ("mp4", write_mp4)])
def test_writers_accept_every_character_mapping_lets_through(
    media_file: Callable[[str], Path], kind: str, write
) -> None:
    write(media_file(kind), TAGS, None)
