"""Opt-in: `uv run pytest -m network -q`. Downloads 3 items of the test playlist, clipped."""

from datetime import date
from pathlib import Path

import pytest

from ytb_playlist import deps
from ytb_playlist.backends.ytdlp_proc import YtDlpBackend
from ytb_playlist.config import default_config_dir
from ytb_playlist.core.fetch import fetch
from ytb_playlist.core.models import (
    Event,
    FetchDone,
    FetchOptions,
    MediaFormat,
)

pytestmark = pytest.mark.network

URL = "https://www.youtube.com/playlist?list=PL9wDNu3ZrVQ63LOO81qh8-Ycq6-vIEqcg"
FIRST_IDS = ("PiZNuhbUERY", "LYCiEm4JEkU", "4oEFyaR6uiM")
CLIP_SECONDS = 60


def backend() -> YtDlpBackend:
    return YtDlpBackend(*(deps.find_binary(name) for name in ("yt-dlp", "ffmpeg", "deno")))


def record_passing_version() -> None:
    version = deps.read_version("yt-dlp", deps.find_binary("yt-dlp"))
    state_dir = default_config_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / deps.LAST_PASS_FILE).write_text(f"{version}\n")


def test_three_clipped_items_then_a_rerun_downloads_nothing(tmp_path: Path) -> None:
    # tmp_path keeps this archive away from real playlists: a clip is archived as if complete.
    real = backend()
    info = real.playlist_info(URL)
    assert info.item_ids[:3] == FIRST_IDS, "fixture playlist changed"

    options = FetchOptions(MediaFormat.MP3, tmp_path, items="1:3", clip_seconds=CLIP_SECONDS)
    events: list[Event] = []
    fetch(URL, options, real, events.append, date.today())
    assert events[-1] == FetchDone(saved=3, failed=0, skipped=0)

    folder = next(tmp_path.iterdir())
    media = sorted(folder.glob("*.mp3"))
    assert len(media) == 3
    assert all(path.name.startswith("20") for path in media)
    assert all(f"[{video_id}]" in " ".join(p.name for p in media) for video_id in FIRST_IDS)
    state_dir = folder / ".ytb-playlist"
    assert len(list(state_dir.glob("*.info.json"))) == 3
    assert len(list((state_dir / "thumbs").glob("*.jpg"))) == 3
    assert not (state_dir / "tmp").exists()

    rerun: list[Event] = []
    fetch(URL, options, real, rerun.append, date.today())
    assert rerun[-1] == FetchDone(saved=0, failed=0, skipped=0)

    record_passing_version()
