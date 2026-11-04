# SPDX-License-Identifier: GPL-3.0-only
from datetime import date
from pathlib import Path

import pytest
from conftest import VERSION_OUTPUT, write_stub

from ytb_playlist import deps
from ytb_playlist.config import Config


def config(tmp_path: Path, **binaries: Path) -> Config:
    return Config(output_root=tmp_path / "out", binaries=binaries)


def test_configured_path_wins_over_path(bin_dir: Path, tmp_path: Path) -> None:
    write_stub(bin_dir, "deno", "on path")
    custom = tmp_path / "custom"
    custom.mkdir()
    configured = write_stub(custom, "deno", "configured")
    assert deps.find_binary("deno", configured) == configured


def test_broken_configured_path_does_not_fall_back_to_path(bin_dir: Path, tmp_path: Path) -> None:
    write_stub(bin_dir, "deno", "on path")
    assert deps.find_binary("deno", tmp_path / "gone") is None


def test_binary_is_found_on_path(bin_dir: Path) -> None:
    stub = write_stub(bin_dir, "deno", "x")
    assert deps.find_binary("deno") == stub


def test_homebrew_folder_is_the_fallback_when_path_lacks_it(bin_dir: Path) -> None:
    stub = write_stub(deps.HOMEBREW_BIN, "deno", "x")
    assert deps.find_binary("deno") == stub


def test_missing_binary_is_none(bin_dir: Path) -> None:
    assert deps.find_binary("deno") is None


@pytest.mark.parametrize(
    ("name", "expected"), [("yt-dlp", "2026.10.26"), ("ffmpeg", "9.0.2"), ("deno", "2.9.8")]
)
def test_version_is_read_from_real_output(bin_dir: Path, name: str, expected: str) -> None:
    stub = write_stub(bin_dir, name, VERSION_OUTPUT[name])
    assert deps.read_version(name, stub) == expected


def test_version_of_a_failing_binary_is_none(bin_dir: Path) -> None:
    stub = write_stub(bin_dir, "deno", VERSION_OUTPUT["deno"], status=1)
    assert deps.read_version("deno", stub) is None


def test_version_of_unexpected_output_is_none(bin_dir: Path) -> None:
    stub = write_stub(bin_dir, "ffmpeg", "something else")
    assert deps.read_version("ffmpeg", stub) is None


def test_version_of_undecodable_output_is_none(bin_dir: Path) -> None:
    stub = bin_dir / "deno"
    stub.write_text("#!/bin/sh\nprintf '\\377\\376'\n")
    stub.chmod(0o755)
    assert deps.read_version("deno", stub) is None


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("2026.10.26", date(2026, 10, 26)),
        ("2026.7.4", date(2026, 7, 4)),
        ("2026.10.26.232323", date(2026, 10, 26)),
        ("not-a-date", None),
        ("2026.13.40", None),
    ],
)
def test_ytdlp_release_date(version: str, expected: date | None) -> None:
    assert deps.ytdlp_release_date(version) == expected


def test_existing_folder_is_writable(tmp_path: Path) -> None:
    assert deps.can_write(tmp_path)


def test_missing_folder_checks_the_nearest_parent_and_creates_nothing(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b"
    assert deps.can_write(target)
    assert not (tmp_path / "a").exists()


def test_read_only_parent_is_not_writable(tmp_path: Path) -> None:
    tmp_path.chmod(0o555)
    try:
        assert not deps.can_write(tmp_path / "out")
    finally:
        tmp_path.chmod(0o755)


def test_check_reports_each_tool(tmp_path: Path, install_tools) -> None:
    install_tools()
    report = deps.check(config(tmp_path), tmp_path, today=date(2026, 11, 4))
    assert {name: d.version for name, d in report.dependencies.items()} == {
        "yt-dlp": "2026.10.26",
        "ffmpeg": "9.0.2",
        "deno": "2.9.8",
    }
    assert report.problems == []


def test_check_shows_ytdlp_age(tmp_path: Path, install_tools) -> None:
    install_tools()
    report = deps.check(config(tmp_path), tmp_path, today=date(2026, 11, 4))
    assert "yt-dlp is 9 days old" in report.notices


def test_check_warns_below_the_security_baseline(tmp_path: Path, install_tools) -> None:
    install_tools(yt_dlp="2026.7.3")
    report = deps.check(config(tmp_path), tmp_path, today=date(2026, 11, 4))
    assert report.problems == []
    assert any("older than 2026.7.4" in notice for notice in report.notices)


def test_check_is_silent_at_the_security_baseline(tmp_path: Path, install_tools) -> None:
    install_tools(yt_dlp="2026.7.4")
    report = deps.check(config(tmp_path), tmp_path, today=date(2026, 11, 4))
    assert not any("older than" in notice for notice in report.notices)


def test_check_says_when_no_network_pass_is_recorded(tmp_path: Path, install_tools) -> None:
    install_tools()
    report = deps.check(config(tmp_path), tmp_path, today=date(2026, 11, 4))
    assert any("not recorded yet" in notice for notice in report.notices)


def test_check_flags_a_version_other_than_the_last_passed(tmp_path: Path, install_tools) -> None:
    install_tools()
    (tmp_path / deps.LAST_PASS_FILE).write_text("2026.9.1\n")
    report = deps.check(config(tmp_path), tmp_path, today=date(2026, 11, 4))
    assert any("2026.9.1" in notice for notice in report.notices)


def test_check_is_silent_when_the_last_passed_version_matches(
    tmp_path: Path, install_tools
) -> None:
    install_tools()
    (tmp_path / deps.LAST_PASS_FILE).write_text("2026.10.26\n")
    report = deps.check(config(tmp_path), tmp_path, today=date(2026, 11, 4))
    assert not any("network test" in notice for notice in report.notices)


def test_check_survives_an_unreadable_last_pass_file(tmp_path: Path, install_tools) -> None:
    install_tools()
    (tmp_path / deps.LAST_PASS_FILE).write_bytes(b"\xff\xfe")
    report = deps.check(config(tmp_path), tmp_path, today=date(2026, 11, 4))
    assert report.problems == []
    assert any("unreadable" in notice for notice in report.notices)


def test_check_reports_an_unwritable_output_root(tmp_path: Path, install_tools) -> None:
    install_tools()
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o555)
    try:
        cfg = Config(output_root=locked / "out", binaries={})
        report = deps.check(cfg, tmp_path, today=date(2026, 11, 4))
    finally:
        locked.chmod(0o755)
    assert any("not writable" in problem for problem in report.problems)
