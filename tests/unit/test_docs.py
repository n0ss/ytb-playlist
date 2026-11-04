# SPDX-License-Identifier: GPL-3.0-only
"""Docs that must follow the code. The CLI reference is generated, never edited by hand."""

import subprocess
import sys
from pathlib import Path

import pytest

from ytb_playlist.cli import exit_codes
from ytb_playlist.config import FILE_KEYS

ROOT = Path(__file__).parent.parent.parent
REFERENCE = ROOT / "docs" / "reference"


def generate_cli_reference(output: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "typer", "ytb_playlist.cli.app", "utils", "docs",
         "--name", "ytb-playlist", "--output", str(output)],
        check=True,
        capture_output=True,
    )  # fmt: skip


def test_cli_reference_is_current(tmp_path: Path) -> None:
    fresh = tmp_path / "cli.md"
    generate_cli_reference(fresh)
    message = "stale: run the command in docs/test-procedure.md to regenerate it"
    assert (REFERENCE / "cli.md").read_text() == fresh.read_text(), message


@pytest.mark.parametrize("command", ["doctor", "info", "fetch", "sync", "tag", "cover", "rename"])
def test_cli_reference_covers_every_command(command: str) -> None:
    assert f"`ytb-playlist {command}`" in (REFERENCE / "cli.md").read_text()


@pytest.mark.parametrize("key", sorted(FILE_KEYS))
def test_config_reference_covers_every_setting(key: str) -> None:
    assert f"`{key}`" in (REFERENCE / "config.md").read_text()


@pytest.mark.parametrize("key", sorted(FILE_KEYS - {"binaries"}))
def test_config_reference_names_every_environment_variable(key: str) -> None:
    assert f"`YTB_PLAYLIST_{key.upper()}`" in (REFERENCE / "config.md").read_text()


@pytest.mark.parametrize(
    "code",
    [
        0,
        exit_codes.PARTIAL,
        exit_codes.USAGE_ERROR,
        exit_codes.MISSING_DEPENDENCY,
        exit_codes.NETWORK_ERROR,
    ],
)
def test_exit_code_reference_covers_every_code(code: int) -> None:
    assert f"| {code} |" in (REFERENCE / "exit-codes.md").read_text()
