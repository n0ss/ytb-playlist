# SPDX-License-Identifier: GPL-3.0-only
"""Spike: does --download-sections give a usable clip, and does the archive stop a rerun?"""

import json
import subprocess
import time

from _common import OUT, PLAYLIST, ytdlp

FORMATS = {
    "mp4": [
        "-f", "bv*[vcodec^=avc1][height<=1080]+ba[ext=m4a]/b[ext=mp4][vcodec^=avc1][height<=1080]",
        "--merge-output-format", "mp4",
    ],
    "mp3": ["-x", "--audio-format", "mp3", "--audio-quality", "0"],
}  # fmt: skip


def probe(path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return json.loads(result.stdout)


for name, options in FORMATS.items():
    dest = OUT / f"clip-{name}"
    dest.mkdir(parents=True, exist_ok=True)
    args = [
        *options,
        "--playlist-items", "1",
        "--download-sections", "*0-60",
        "--write-info-json",
        "--download-archive", str(dest / "archive.txt"),
        "-o", str(dest / "%(id)s.%(ext)s"),
        "--print", "after_move:filepath",
        PLAYLIST,
    ]  # fmt: skip
    for run in ("first", "rerun"):
        start = time.monotonic()
        result = ytdlp(*args, timeout=590)
        elapsed = time.monotonic() - start
        print(f"{name} {run}: exit {result.returncode}, {elapsed:.1f}s, printed {result.stdout!r}")
        if result.returncode:
            print(result.stderr[-1000:])
    print("files:", sorted(p.name for p in dest.iterdir()))
    print("archive:", (dest / "archive.txt").read_text().strip())
    for path in dest.glob(f"*.{name}"):
        print(f"{path.name}: {path.stat().st_size} bytes, {probe(path)}")
