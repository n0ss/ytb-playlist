# SPDX-License-Identifier: GPL-3.0-only
"""Turn a saved thumbnail into embeddable cover art. Thumbnails are untrusted input."""

import io
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

MAX_SQUARE_SIDE = 1000
MAX_COVER_BYTES = 500_000
QUALITIES = (90, 85, 80, 75)
# yt-dlp converts to JPEG, but keeps the original if the conversion fails.
THUMBNAIL_SUFFIXES = (".jpg", ".webp", ".png")


class CoverError(Exception):
    """The thumbnail can't be used."""


@dataclass(frozen=True)
class Cover:
    data: bytes
    quality: int
    over_budget: bool


def find_thumbnail(folder: Path, video_id: str) -> Path | None:
    for suffix in THUMBNAIL_SUFFIXES:
        path = folder / f"{video_id}{suffix}"
        if path.exists():
            return path
    return None


def square_cover(source: Path) -> Cover:
    """Centre crop to the shorter side, capped, for the album art grid. Never upscales."""
    image = _open(source)
    side = min(image.size)
    left, top = (image.width - side) // 2, (image.height - side) // 2
    square = image.crop((left, top, left + side, top + side))
    if side > MAX_SQUARE_SIDE:
        square = square.resize((MAX_SQUARE_SIDE, MAX_SQUARE_SIDE), Image.Resampling.LANCZOS)
    return _encode(square)


def wide_cover(source: Path) -> Cover:
    return _encode(_open(source))


def _open(source: Path) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source) as image:
                return image.convert("RGB")
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
        raise CoverError(f"unusable thumbnail {source.name}: {error}") from error
    except Image.DecompressionBombWarning as error:
        raise CoverError(f"thumbnail too large: {source.name}") from error


def _encode(image: Image.Image) -> Cover:
    """Pillow only copies metadata it's given, so the result carries no EXIF."""
    for quality in QUALITIES:
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=quality)
        if buffer.tell() <= MAX_COVER_BYTES:
            return Cover(buffer.getvalue(), quality, False)
    return Cover(buffer.getvalue(), QUALITIES[-1], True)
