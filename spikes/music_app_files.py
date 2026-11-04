"""Spike: build the Music.app test files in a dedicated export folder."""

import io
import json
import shutil
from datetime import datetime
from pathlib import Path

from _common import OUT
from mutagen.id3 import (
    APIC,
    COMM,
    ID3,
    TALB,
    TCON,
    TDAT,
    TDRC,
    TIT2,
    TPE1,
    TPE2,
    TRCK,
    TXXX,
    TYER,
    WOAS,
)
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm
from PIL import Image

VIDEO_ID = "PiZNuhbUERY"
PLAYLIST_ID = "PL9wDNu3ZrVQ63LOO81qh8-Ycq6-vIEqcg"
ALBUM = "ytb-playlist 1b spike"
DEST = Path.home() / "Music" / "ytb-playlist-export"
UTF16 = 1


def load(kind: str) -> dict:
    info = json.loads((OUT / f"clip-{kind}" / f"{VIDEO_ID}.info.json").read_text())
    date = datetime.strptime(info["upload_date"], "%Y%m%d")
    return {
        "title": info["title"].replace('"', "").strip(),
        "artist": info["channel"],
        "album_artist": info["playlist_uploader"],
        "date": date,
        "description": info["description"][:4000],
        "url": info["webpage_url"],
    }


def jpeg(source: Path, square: bool) -> bytes:
    with Image.open(source) as image:
        rgb = image.convert("RGB")
    if square:
        side = min(rgb.size)
        left, top = (rgb.width - side) // 2, (rgb.height - side) // 2
        rgb = rgb.crop((left, top, left + side, top + side))
    buffer = io.BytesIO()
    rgb.save(buffer, "JPEG", quality=90)
    print(f"  cover {rgb.size}, {buffer.tell()} bytes")
    return buffer.getvalue()


def tag_mp3(name: str, label: str, track: int, version: int, cover: bytes) -> None:
    meta = load("mp3")
    path = DEST / name
    shutil.copy2(OUT / "clip-mp3" / f"{VIDEO_ID}.mp3", path)
    day = meta["date"].strftime("%Y-%m-%d")
    tags = ID3()
    tags.add(TIT2(encoding=UTF16, text=[f"{label} {day} - {meta['title']}"]))
    tags.add(TPE1(encoding=UTF16, text=[meta["artist"]]))
    tags.add(TALB(encoding=UTF16, text=[ALBUM]))
    tags.add(TPE2(encoding=UTF16, text=[meta["album_artist"]]))
    tags.add(TRCK(encoding=UTF16, text=[str(track)]))
    if version == 3:
        tags.add(TYER(encoding=UTF16, text=[meta["date"].strftime("%Y")]))
        tags.add(TDAT(encoding=UTF16, text=[meta["date"].strftime("%d%m")]))
    else:
        tags.add(TDRC(encoding=UTF16, text=[day]))
    tags.add(TCON(encoding=UTF16, text=["YouTube"]))
    tags.add(COMM(encoding=UTF16, lang="eng", desc="", text=[meta["description"]]))
    tags.add(WOAS(url=meta["url"]))
    tags.add(TXXX(encoding=UTF16, desc="YOUTUBE_ID", text=[VIDEO_ID]))
    tags.add(APIC(encoding=UTF16, mime="image/jpeg", type=3, desc="", data=cover))
    tags.save(path, v1=0, v2_version=version)


def tag_mp4(name: str, label: str, track: int, stik: int | None, cover: bytes) -> None:
    meta = load("mp4")
    path = DEST / name
    shutil.copy2(OUT / "clip-mp4" / f"{VIDEO_ID}.mp4", path)
    day = meta["date"].strftime("%Y-%m-%d")
    audio = MP4(path)
    audio.delete()
    audio = MP4(path)
    audio["\xa9nam"] = [f"{label} {day} - {meta['title']}"]
    audio["\xa9ART"] = [meta["artist"]]
    audio["\xa9alb"] = [ALBUM]
    audio["aART"] = [meta["album_artist"]]
    audio["trkn"] = [(track, 0)]
    audio["\xa9day"] = [day]
    audio["\xa9gen"] = ["YouTube"]
    audio["desc"] = [meta["description"][:255]]
    audio["ldes"] = [meta["description"]]
    audio["----:com.apple.iTunes:URL"] = [MP4FreeForm(meta["url"].encode())]
    audio["----:com.apple.iTunes:YOUTUBE_ID"] = [MP4FreeForm(VIDEO_ID.encode())]
    audio["covr"] = [MP4Cover(cover, imageformat=MP4Cover.FORMAT_JPEG)]
    if stik is not None:
        audio["stik"] = [stik]
    audio.save()


def build() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    thumbs = OUT / "thumbs"
    episode_square = jpeg(thumbs / f"{VIDEO_ID}.jpg", square=True)
    playlist_square = jpeg(thumbs / f"{PLAYLIST_ID}.jpg", square=True)
    episode_wide = jpeg(thumbs / f"{VIDEO_ID}.jpg", square=False)
    tag_mp3("A-v23-episode.mp3", "[A v2.3]", 1, 3, episode_square)
    tag_mp3("B-v24-episode.mp3", "[B v2.4]", 2, 4, episode_square)
    tag_mp3("C-v23-playlist-cover.mp3", "[C playlist cover]", 3, 3, playlist_square)
    tag_mp4("D-stik6.mp4", "[D stik 6]", 4, 6, episode_wide)
    tag_mp4("E-no-stik.mp4", "[E no stik]", 5, None, episode_wide)


build()
