# SPDX-License-Identifier: GPL-3.0-only
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from ytb_playlist import deps

VERSION_OUTPUT = {
    "yt-dlp": "2026.10.26",
    "ffmpeg": "ffmpeg version 9.0.2 Copyright (c) 2000-2026 the FFmpeg developers",
    "deno": "deno 2.9.8 (stable, release, aarch64-apple-darwin)",
}


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must not depend on settings exported in the developer's shell."""
    for name in os.environ:
        if name.startswith("YTB_PLAYLIST_"):
            monkeypatch.delenv(name)


def write_stub(directory: Path, name: str, output: str, status: int = 0) -> Path:
    stub = directory / name
    stub.write_text(f"#!/bin/sh\necho '{output}'\nexit {status}\n")
    stub.chmod(0o755)
    return stub


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "home"
    path.mkdir()
    monkeypatch.setenv("HOME", str(path))
    return path


@pytest.fixture
def bin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, home: Path) -> Path:
    """An isolated PATH, with the Homebrew fallback pointing at an empty folder."""
    path = tmp_path / "bin"
    path.mkdir()
    empty = tmp_path / "no-homebrew"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(path))
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setattr(deps, "HOMEBREW_BIN", empty)
    return path


@pytest.fixture
def install_tools(bin_dir: Path) -> Callable[..., None]:
    def install(*skip: str, **versions: str) -> None:
        for name, output in VERSION_OUTPUT.items():
            if name not in skip:
                write_stub(bin_dir, name, versions.get(name.replace("-", "_"), output))

    return install
