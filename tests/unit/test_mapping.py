# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path

import pytest

from ytb_playlist.tagging.mapping import TrackTags, map_tags

FIXTURES = Path(__file__).parent.parent / "fixtures"


def info(**fields: object) -> dict[str, object]:
    return {
        "id": "abc",
        "title": "Title",
        "upload_date": "20241023",
        "channel": "Channel",
        "playlist_title": "Playlist",
        "playlist_uploader": "Owner",
        "playlist_index": 7,
        "description": "About",
        "webpage_url": "https://www.youtube.com/watch?v=abc",
    } | fields


def test_recorded_item_maps_to_the_planned_tags() -> None:
    item = json.loads((FIXTURES / "PiZNuhbUERY.info.json").read_text())
    tags = map_tags(item)
    assert tags == TrackTags(
        title="2024-10-23 - L'été dernier, l'essai du 20 octobre",
        artist="Radio Exemple",
        album='Les essais de "L\'été"',
        album_artist="Radio Exemple",
        track=1,
        date="2024-10-23",
        genre="YouTube",
        description=item["description"],
        url="https://www.youtube.com/watch?v=PiZNuhbUERY",
        video_id="PiZNuhbUERY",
    )


@pytest.mark.parametrize(
    ("fields", "artist"),
    [
        ({}, "Channel"),
        ({"channel": None, "uploader": "Uploader"}, "Uploader"),
        ({"channel": "Some Band - Topic"}, "Some Band"),
        ({"channel": None}, ""),
    ],
)
def test_artist(fields: dict[str, object], artist: str) -> None:
    assert map_tags(info(**fields)).artist == artist


def test_album_override_wins() -> None:
    assert map_tags(info(), album="My show").album == "My show"


def test_album_artist_is_the_playlist_owner_without_topic() -> None:
    assert map_tags(info(playlist_uploader="Owner - Topic")).album_artist == "Owner"


def test_album_artist_falls_back_to_the_artist() -> None:
    assert map_tags(info(playlist_uploader=None)).album_artist == "Channel"


def test_genre_override() -> None:
    assert map_tags(info(), genre="Radio").genre == "Radio"


def test_release_date_wins_over_upload_date() -> None:
    assert map_tags(info(release_date="20250314")).date == "2025-03-14"


def test_unknown_date_has_no_date_tag() -> None:
    tags = map_tags(info(upload_date=None))
    assert tags.date is None
    assert tags.title == "0000-00-00 - Title"


@pytest.mark.parametrize("index", [None, 0, -1, "7", True])
def test_unusable_track_number_is_left_out(index: object) -> None:
    assert map_tags(info(playlist_index=index)).track is None


def test_description_is_cut_at_4000_characters() -> None:
    assert len(map_tags(info(description="é" * 5000)).description) == 4000


def test_description_keeps_its_line_breaks() -> None:
    assert map_tags(info(description="one\ntwo\n")).description == "one\ntwo"


@pytest.mark.parametrize(
    "field", ["channel", "playlist_title", "playlist_uploader", "description", "webpage_url"]
)
def test_broken_characters_are_removed(field: str) -> None:
    tags = map_tags(info(**{field: "a\ud83d\x07\u202eb"}))
    values = (tags.artist, tags.album, tags.album_artist, tags.description, tags.url)
    assert all(not set("\ud83d\x07\u202e") & set(value) for value in values)
    assert "ab" in values


@pytest.mark.parametrize("field", ["channel", "playlist_title", "description"])
def test_values_of_the_wrong_type_become_empty(field: str) -> None:
    map_tags(info(**{field: 42}))
