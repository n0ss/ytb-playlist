"""Build file and folder names. Titles, dates and IDs come from untrusted metadata."""

import re
import unicodedata
from collections.abc import Mapping
from datetime import date

MAX_NAME_BYTES = 200
MISSING_DATE = "0000-00-00"
EMPTY_TITLE = "Untitled"

SAFE_ID = re.compile(r"[A-Za-z0-9_-]+")
DATE_DIGITS = re.compile(r"(\d{4})(\d{2})(\d{2})")
WHITESPACE = re.compile(r"\s")
UNSAFE = re.compile("[\x00-\x1f\x7f-\x9f\ud800-\udfff\u202a-\u202e\u2066-\u2069]")
SPACES = re.compile(r" {2,}")
EDGES = " ."
REPLACEMENTS = str.maketrans({"/": " - ", "\\": " - ", ":": " - "})
REMOVED = str.maketrans(dict.fromkeys('"*?<>|'))


class UnsafeIdError(ValueError):
    """A video or playlist ID can't be used in a path."""


def is_safe_id(value: object) -> bool:
    return isinstance(value, str) and SAFE_ID.fullmatch(value) is not None


def clean_title(title: object) -> str:
    text = unicodedata.normalize("NFC", title) if isinstance(title, str) else ""
    text = UNSAFE.sub("", WHITESPACE.sub(" ", text))
    text = text.translate(REPLACEMENTS).translate(REMOVED)
    return SPACES.sub(" ", text).strip(EDGES) or EMPTY_TITLE


def file_name(info: Mapping[str, object], ext: str) -> str:
    return _fit(
        f"{_item_date(info)} - ",
        info.get("title"),
        f" [{_checked_id(info.get('id'))}].{ext}",
    )


def folder_name(title: object, playlist_id: str) -> str:
    return _fit("", title, f" [{_checked_id(playlist_id)}]")


def _checked_id(value: object) -> str:
    if not is_safe_id(value):
        raise UnsafeIdError(f"unsafe ID: {value!r}")
    return str(value)


def _item_date(info: Mapping[str, object]) -> str:
    for field in ("release_date", "upload_date"):
        parsed = _parse_date(info.get(field))
        if parsed:
            return parsed
    return MISSING_DATE


def _parse_date(value: object) -> str | None:
    match = DATE_DIGITS.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        return None
    try:
        return date(*(int(part) for part in match.groups())).isoformat()
    except ValueError:
        return None


def _fit(prefix: str, title: object, suffix: str) -> str:
    """Shorten only the title, on a character boundary, so the name fits the limit."""
    budget = MAX_NAME_BYTES - len(prefix.encode()) - len(suffix.encode())
    cut = clean_title(title).encode()[:budget].decode(errors="ignore")
    return f"{prefix}{cut.rstrip(EDGES)}{suffix}"
