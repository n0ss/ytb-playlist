# SPDX-License-Identifier: GPL-3.0-only
"""Turn untrusted item metadata into the tags to write, as pure functions."""

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

from ytb_playlist.naming import MISSING_DATE, clean_title, item_date

DEFAULT_GENRE = "YouTube"
MAX_DESCRIPTION = 4000
TOPIC_SUFFIX = " - Topic"
# Like naming.UNSAFE, but a description keeps its line breaks and tabs.
UNSAFE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff\u202a-\u202e\u2066-\u2069]")


@dataclass(frozen=True)
class TrackTags:
    title: str
    artist: str
    album: str
    album_artist: str
    track: int | None
    date: str | None
    genre: str
    description: str
    url: str
    video_id: str


def _text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return UNSAFE.sub("", unicodedata.normalize("NFC", value)).strip()


def _person(value: object) -> str:
    return _text(value).removesuffix(TOPIC_SUFFIX)


def _track(value: object) -> int | None:
    is_number = isinstance(value, int) and not isinstance(value, bool)
    return value if is_number and value > 0 else None


def map_tags(
    info: Mapping[str, object], album: str | None = None, genre: str = DEFAULT_GENRE
) -> TrackTags:
    day = item_date(info)
    artist = _person(info.get("channel")) or _person(info.get("uploader"))
    return TrackTags(
        title=f"{day} - {clean_title(info.get('title'))}",
        artist=artist,
        album=_text(album or info.get("playlist_title")),
        album_artist=_person(info.get("playlist_uploader")) or artist,
        track=_track(info.get("playlist_index")),
        date=None if day == MISSING_DATE else day,
        genre=genre,
        description=_text(info.get("description"))[:MAX_DESCRIPTION],
        url=_text(info.get("webpage_url")),
        video_id=_text(info.get("id")),
    )
