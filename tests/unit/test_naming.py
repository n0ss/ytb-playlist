import unicodedata

import pytest

from ytb_playlist.naming import MAX_NAME_BYTES, UnsafeIdError, clean_title, file_name, folder_name

VIDEO_ID = "PiZNuhbUERY"
PLAYLIST_ID = "PL9wDNu3ZrVQ63LOO81qh8-Ycq6-vIEqcg"


def info(**fields: object) -> dict[str, object]:
    return {"id": VIDEO_ID, "title": "Title", "upload_date": "20241023", **fields}


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ('"La dernière", l\'intégrale du 20 octobre', "La dernière, l'intégrale du 20 octobre"),
        ("AC/DC: Live", "AC - DC - Live"),
        ("back\\slash", "back - slash"),
        ("a*b?c<d>e|f", "abcdef"),
        ("too   many    spaces", "too many spaces"),
        ("trailing dots... ", "trailing dots"),
        ("...hidden", "hidden"),
        ("  .. spaced", "spaced"),
        ("line\nbreak\ttab", "line break tab"),
        ("bell\x07 and null\x00", "bell and null"),
        ("../../etc/passwd", "- .. - etc - passwd"),
        ("???", "Untitled"),
        ('""', "Untitled"),
        ("...", "Untitled"),
        ("", "Untitled"),
    ],
)
def test_clean_title(title: str, expected: str) -> None:
    assert clean_title(title) == expected


def test_clean_title_composes_accents() -> None:
    decomposed = unicodedata.normalize("NFD", "dernière")
    assert clean_title(decomposed) == "dernière"


def test_clean_title_keeps_emoji_and_curly_quotes() -> None:
    assert clean_title("“Live” 🎵 été") == "“Live” 🎵 été"


def test_file_name_on_a_real_item() -> None:
    item = info(title='"La dernière", l\'intégrale du 20 octobre', release_date=None)
    assert file_name(item, "mp3") == (
        f"2024-10-23 - La dernière, l'intégrale du 20 octobre [{VIDEO_ID}].mp3"
    )


@pytest.mark.parametrize(
    ("fields", "date"),
    [
        ({"release_date": "20250314"}, "2025-03-14"),
        ({"release_date": None}, "2024-10-23"),
        ({"release_date": "unknown"}, "2024-10-23"),
        ({"release_date": "20251340"}, "2024-10-23"),
        ({"release_date": 20250314}, "2024-10-23"),
        ({"upload_date": None}, "0000-00-00"),
        ({"upload_date": "2024"}, "0000-00-00"),
    ],
)
def test_file_name_date(fields: dict[str, object], date: str) -> None:
    assert file_name(info(**fields), "mp3") == f"{date} - Title [{VIDEO_ID}].mp3"


def test_missing_title_is_untitled() -> None:
    item = info()
    del item["title"]
    assert file_name(item, "mp3") == f"2024-10-23 - Untitled [{VIDEO_ID}].mp3"


def test_short_name_is_not_truncated() -> None:
    title = "x" * 150
    assert title in file_name(info(title=title), "mp3")


def test_long_title_fits_the_byte_limit_and_keeps_the_id() -> None:
    name = file_name(info(title="x" * 500), "mp4")
    assert len(name.encode()) == MAX_NAME_BYTES
    assert name.endswith(f" [{VIDEO_ID}].mp4")


def test_truncation_never_splits_a_multibyte_character() -> None:
    name = file_name(info(title="é" * 500), "mp3")
    assert len(name.encode()) <= MAX_NAME_BYTES
    assert "�" not in name
    assert name.endswith(f"é [{VIDEO_ID}].mp3")


def test_truncation_leaves_no_trailing_space() -> None:
    # The cut falls on the space in the title, right before the ID.
    prefix_and_suffix = len(f"2024-10-23 - TITLE [{VIDEO_ID}].mp3") - len("TITLE")
    keep = MAX_NAME_BYTES - prefix_and_suffix - 1
    name = file_name(info(title="x" * keep + " yyyy"), "mp3")
    assert f"x [{VIDEO_ID}]" in name


def test_sorted_names_follow_date_order() -> None:
    items = [
        info(title="Zebra", upload_date="20240102"),
        info(title="apple", upload_date="20251231"),
        info(title="Mango", upload_date=None),
        info(title="Kiwi", upload_date="20240101"),
    ]
    names = sorted(file_name(item, "mp3") for item in items)
    assert [name[:10] for name in names] == [
        "0000-00-00",
        "2024-01-01",
        "2024-01-02",
        "2025-12-31",
    ]


def test_folder_name_on_a_real_playlist() -> None:
    assert folder_name('Les intégrales de "La dernière"', PLAYLIST_ID) == (
        f"Les intégrales de La dernière [{PLAYLIST_ID}]"
    )


def test_folder_name_cannot_be_hidden() -> None:
    assert folder_name(".Foo", PLAYLIST_ID) == f"Foo [{PLAYLIST_ID}]"


def test_long_folder_name_fits_the_byte_limit() -> None:
    name = folder_name("é" * 500, PLAYLIST_ID)
    assert len(name.encode()) <= MAX_NAME_BYTES
    assert name.endswith(f" [{PLAYLIST_ID}]")


@pytest.mark.parametrize("bad_id", ["../evil", "a/b", "a b", "", "a.b", "id\n", None, 123])
def test_unsafe_video_id_is_refused(bad_id: object) -> None:
    with pytest.raises(UnsafeIdError):
        file_name(info(id=bad_id), "mp3")


def test_missing_video_id_is_refused() -> None:
    item = info()
    del item["id"]
    with pytest.raises(UnsafeIdError):
        file_name(item, "mp3")


@pytest.mark.parametrize("bad_id", ["../evil", "a/b", ""])
def test_unsafe_playlist_id_is_refused(bad_id: str) -> None:
    with pytest.raises(UnsafeIdError):
        folder_name("Title", bad_id)
