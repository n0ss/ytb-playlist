# SPDX-License-Identifier: GPL-3.0-only
"""Tag one media file from its metadata and thumbnail."""

import os
import shutil
import subprocess
from collections.abc import Callable, Mapping
from enum import StrEnum
from pathlib import Path

from mutagen import MutagenError

from ytb_playlist.cover import Cover, CoverError, square_cover, wide_cover
from ytb_playlist.tagging.id3 import replace_id3_cover, write_id3
from ytb_playlist.tagging.mapping import map_tags
from ytb_playlist.tagging.mp4 import replace_mp4_cover, write_mp4

Tagger = Callable[[Path, Mapping[str, object], Path | None], tuple[str, ...]]


class TaggingError(Exception):
    """The file couldn't be tagged. It's left as it was."""


class CoverMode(StrEnum):
    SQUARE = "square"
    WIDE = "wide"


WRITERS = {".mp3": write_id3, ".mp4": write_mp4}
COVER_WRITERS = {".mp3": replace_id3_cover, ".mp4": replace_mp4_cover}
DEFAULT_MODES = {".mp3": CoverMode.SQUARE, ".mp4": CoverMode.WIDE}
BUILDERS = {CoverMode.SQUARE: square_cover, CoverMode.WIDE: wide_cover}
TAG_ERRORS = (MutagenError, OSError, ValueError)


def _clone(source: Path, target: Path) -> None:
    """An APFS clone is instant and takes no space; any other disk gets a plain copy."""
    try:
        subprocess.run(
            ["/bin/cp", "-c", str(source.absolute()), str(target.absolute())],
            check=True,
            capture_output=True,
        )
    except OSError, subprocess.SubprocessError:
        shutil.copy2(source, target)


def _write_safely(path: Path, write: Callable[[Path], None]) -> None:
    """Mutagen shifts audio data in place, so an interrupted write could damage the file.

    Tag a copy beside it instead, then swap it in with an atomic rename.
    """
    temp = path.with_name(f".{path.name}.tagging")
    try:
        _clone(path, temp)
        write(temp)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _require_supported(path: Path) -> None:
    if path.suffix not in WRITERS:
        raise TaggingError(f"unsupported file: {path.name}")


def _build(path: Path, thumbnail: Path, mode: CoverMode | None) -> Cover:
    return BUILDERS[mode or DEFAULT_MODES[path.suffix]](thumbnail)


def tag_file(
    path: Path,
    info: Mapping[str, object],
    thumbnail: Path | None,
    mode: CoverMode | None = None,
) -> tuple[str, ...]:
    """Write every tag. A cover problem is a warning, because the tags still matter."""
    _require_supported(path)
    warnings = []
    data = None
    if thumbnail is None:
        warnings.append(f"no thumbnail for {path.name}: tagged without a cover")
    else:
        try:
            cover = _build(path, thumbnail, mode)
        except CoverError as error:
            warnings.append(f"{error}: tagged without a cover")
        else:
            data = cover.data
            if cover.over_budget:
                warnings.append(f"cover of {path.name} is over the size budget")
    tags = map_tags(info)
    write = WRITERS[path.suffix]
    try:
        _write_safely(path, lambda temp: write(temp, tags, data))
    except TAG_ERRORS as error:
        raise TaggingError(f"{path.name}: {error}") from error
    return tuple(warnings)


def replace_cover(path: Path, thumbnail: Path, mode: CoverMode | None = None) -> None:
    """Change only the cover, keeping every other tag."""
    _require_supported(path)
    write = COVER_WRITERS[path.suffix]
    try:
        data = _build(path, thumbnail, mode).data
        _write_safely(path, lambda temp: write(temp, data))
    except (CoverError, *TAG_ERRORS) as error:
        raise TaggingError(f"{path.name}: {error}") from error
