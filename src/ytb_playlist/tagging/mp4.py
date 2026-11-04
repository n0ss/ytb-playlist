# SPDX-License-Identifier: GPL-3.0-only
"""Write iTunes MP4 atoms, replacing whatever ffmpeg left in the file."""

from pathlib import Path

from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm

from ytb_playlist.tagging.mapping import TrackTags

FREEFORM = "----:com.apple.iTunes:"
MAX_SHORT_DESCRIPTION = 255
TEXT_ATOMS = (
    ("\xa9nam", "title"),
    ("\xa9ART", "artist"),
    ("\xa9alb", "album"),
    ("aART", "album_artist"),
    ("\xa9day", "date"),
    ("\xa9gen", "genre"),
)


def write_mp4(path: Path, tags: TrackTags, cover: bytes | None) -> None:
    MP4(path).delete()
    atoms = MP4(path)
    for atom, field in TEXT_ATOMS:
        value = getattr(tags, field)
        if value:
            atoms[atom] = [value]
    if tags.track is not None:
        atoms["trkn"] = [(tags.track, 0)]
    if tags.description:
        atoms["desc"] = [tags.description[:MAX_SHORT_DESCRIPTION]]
        atoms["ldes"] = [tags.description]
    if tags.url:
        atoms[f"{FREEFORM}URL"] = [MP4FreeForm(tags.url.encode())]
    atoms[f"{FREEFORM}YOUTUBE_ID"] = [MP4FreeForm(tags.video_id.encode())]
    if cover is not None:
        atoms["covr"] = [MP4Cover(cover, imageformat=MP4Cover.FORMAT_JPEG)]
    atoms.save()
