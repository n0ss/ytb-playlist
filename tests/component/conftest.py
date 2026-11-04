# SPDX-License-Identifier: GPL-3.0-only
"""Real media, generated at test time because media files are never committed."""

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image


def generate(path: Path, *codec: str) -> Path:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=duration=1", *codec, str(path)],
        check=True,
    )
    return path


@pytest.fixture(scope="session")
def media(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is needed to generate test media")
    folder = tmp_path_factory.mktemp("media")
    return {
        "mp3": generate(folder / "source.mp3", "-metadata", "title=ffmpeg title"),
        "mp4": generate(folder / "source.mp4", "-c:a", "aac", "-metadata", "title=ffmpeg title"),
    }


@pytest.fixture
def media_file(media: dict[str, Path], tmp_path: Path) -> Callable[[str], Path]:
    def copy(kind: str) -> Path:
        return Path(shutil.copy(media[kind], tmp_path / f"item.{kind}"))

    return copy


@pytest.fixture
def jpeg(tmp_path: Path) -> bytes:
    path = tmp_path / "cover.jpg"
    Image.new("RGB", (64, 64), "red").save(path)
    return path.read_bytes()
