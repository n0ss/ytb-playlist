# SPDX-License-Identifier: GPL-3.0-only
"""Shared helpers for the throwaway phase 1a spikes."""

import subprocess
from pathlib import Path

PLAYLIST = "https://www.youtube.com/playlist?list=PL9wDNu3ZrVQ63LOO81qh8-Ycq6-vIEqcg"
OUT = Path(__file__).parent / "output"


def ytdlp(*args: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["yt-dlp", "--ignore-config", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def first_video_id() -> str:
    result = ytdlp("--flat-playlist", "--playlist-items", "1", "--print", "id", PLAYLIST)
    return result.stdout.strip()
