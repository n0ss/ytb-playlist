# SPDX-License-Identifier: GPL-3.0-only
from importlib.metadata import version
from pathlib import Path

import pytest
from conftest import write_stub
from typer.testing import CliRunner

from ytb_playlist.cli.app import app

runner = CliRunner()


def test_doctor_exits_0_when_everything_is_present(install_tools) -> None:
    install_tools()
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    for expected in ("yt-dlp", "2026.10.26", "ffmpeg", "9.0.2", "deno", "2.9.8"):
        assert expected in result.output


@pytest.mark.parametrize("name", ["yt-dlp", "ffmpeg", "deno"])
def test_doctor_exits_3_when_a_tool_is_missing(install_tools, name: str) -> None:
    install_tools(name)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 3
    assert f"{name} not found" in result.output


def test_doctor_exits_3_when_a_tool_does_not_run(install_tools) -> None:
    install_tools(deno="garbage")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 3
    assert "deno" in result.output


def test_doctor_exits_2_on_an_invalid_config(install_tools, tmp_path: Path) -> None:
    install_tools()
    bad = tmp_path / "bad.toml"
    bad.write_text("output_root = [")
    result = runner.invoke(app, ["--config", str(bad), "doctor"])
    assert result.exit_code == 2
    assert "invalid TOML" in result.output


def test_config_error_goes_to_stderr_on_one_line(
    install_tools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_tools()
    monkeypatch.setenv("COLUMNS", "40")
    bad = tmp_path / "bad.toml"
    bad.write_text("output_root = [")
    result = runner.invoke(app, ["--config", str(bad), "doctor"])
    assert result.stdout == ""
    assert str(bad) in result.stderr


def test_doctor_uses_the_binary_from_the_config(install_tools, bin_dir, tmp_path: Path) -> None:
    install_tools("deno")
    custom = tmp_path / "custom"
    custom.mkdir()
    stub = write_stub(custom, "deno", "deno 3.0.0 (stable)")
    config = tmp_path / "c.toml"
    config.write_text(f'[binaries]\ndeno = "{stub}"\n')
    result = runner.invoke(app, ["--config", str(config), "doctor"])
    assert result.exit_code == 0, result.output
    assert "3.0.0" in result.output


def test_doctor_creates_nothing(install_tools, home: Path) -> None:
    install_tools()
    runner.invoke(app, ["doctor"])
    assert list(home.iterdir()) == []


def test_version_option_prints_the_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == version("ytb-playlist")
