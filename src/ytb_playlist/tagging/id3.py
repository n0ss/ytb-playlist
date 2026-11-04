# SPDX-License-Identifier: GPL-3.0-only
"""Write ID3v2.3 tags, replacing whatever ffmpeg left in the file."""

from pathlib import Path

from mutagen.id3 import (
    APIC,
    COMM,
    ID3,
    TALB,
    TCON,
    TDAT,
    TIT2,
    TPE1,
    TPE2,
    TRCK,
    TXXX,
    TYER,
    WOAS,
)
from mutagen.mp3 import MP3

from ytb_playlist.tagging.mapping import TrackTags

UTF16 = 1
FRONT_COVER = 3
TEXT_FRAMES = (
    (TIT2, "title"),
    (TPE1, "artist"),
    (TALB, "album"),
    (TPE2, "album_artist"),
    (TCON, "genre"),
)


def _picture(cover: bytes) -> APIC:
    return APIC(encoding=UTF16, mime="image/jpeg", type=FRONT_COVER, desc="", data=cover)


def write_id3(path: Path, tags: TrackTags, cover: bytes | None) -> None:
    MP3(path)  # Refuses a file that isn't MP3; ID3 alone would tag anything.
    frames = ID3()
    for frame, field in TEXT_FRAMES:
        value = getattr(tags, field)
        if value:
            frames.add(frame(encoding=UTF16, text=[value]))
    if tags.track is not None:
        frames.add(TRCK(encoding=UTF16, text=[str(tags.track)]))
    if tags.date is not None:
        year, month, day = tags.date.split("-")
        frames.add(TYER(encoding=UTF16, text=[year]))
        frames.add(TDAT(encoding=UTF16, text=[f"{day}{month}"]))
    if tags.description:
        frames.add(COMM(encoding=UTF16, lang="eng", desc="", text=[tags.description]))
    if tags.url:
        frames.add(WOAS(url=tags.url))
    frames.add(TXXX(encoding=UTF16, desc="YOUTUBE_ID", text=[tags.video_id]))
    if cover is not None:
        frames.add(_picture(cover))
    frames.save(path, v1=0, v2_version=3)


def replace_id3_cover(path: Path, cover: bytes) -> None:
    frames = ID3(path, translate=False)
    frames.setall("APIC", [_picture(cover)])
    frames.save(path, v1=0, v2_version=3)
