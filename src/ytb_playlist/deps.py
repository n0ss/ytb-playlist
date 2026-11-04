"""Find the system tools, read their versions and report on them for `doctor`."""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ytb_playlist.config import TOOLS, Config

HOMEBREW_BIN = Path("/opt/homebrew/bin")
LAST_PASS_FILE = "last-network-pass.txt"
# The release that fixes the CVEs listed in decision 15.
YTDLP_SECURITY_BASELINE = date(2026, 7, 4)

VERSION_FLAGS = {"yt-dlp": "--version", "ffmpeg": "-version", "deno": "--version"}
VERSION_PATTERNS = {
    "yt-dlp": re.compile(r"(\d{4}\.\d+\.\d+(?:\.\d+)?)$"),
    "ffmpeg": re.compile(r"ffmpeg version (\S+)"),
    "deno": re.compile(r"deno (\S+)"),
}
VERSION_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class Dependency:
    name: str
    path: Path | None
    version: str | None


@dataclass(frozen=True)
class Report:
    dependencies: dict[str, Dependency]
    problems: list[str]
    notices: list[str]


def find_binary(name: str, configured: Path | None = None) -> Path | None:
    """A configured path is final, so a typo there isn't hidden by another copy."""
    if configured is not None:
        return configured if shutil.which(configured) else None
    found = shutil.which(name) or shutil.which(name, path=str(HOMEBREW_BIN))
    return Path(found) if found else None


def read_version(name: str, binary: Path) -> str | None:
    try:
        result = subprocess.run(
            [str(binary), VERSION_FLAGS[name]],
            check=True,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=VERSION_TIMEOUT_SECONDS,
        )
    except OSError, subprocess.SubprocessError:
        return None
    first_line = result.stdout.partition("\n")[0].strip()
    match = VERSION_PATTERNS[name].match(first_line)
    return match.group(1) if match else None


def ytdlp_release_date(version: str) -> date | None:
    """yt-dlp versions are dates; nightly builds add a fourth part."""
    try:
        year, month, day = (int(part) for part in version.split(".")[:3])
        return date(year, month, day)
    except ValueError:
        return None


def can_write(folder: Path) -> bool:
    """Check the folder, or its nearest existing parent, without creating anything."""
    while not folder.exists():
        folder = folder.parent
    return os.access(folder, os.W_OK | os.X_OK)


def check(config: Config, state_dir: Path, today: date) -> Report:
    dependencies = {}
    problems = []
    for name in TOOLS:
        binary = find_binary(name, config.binaries.get(name))
        version = read_version(name, binary) if binary else None
        dependencies[name] = Dependency(name, binary, version)
        if binary is None:
            problems.append(f"{name} not found")
        elif version is None:
            problems.append(f"{name} at {binary} did not report a version")
    if not can_write(config.output_root):
        problems.append(f"{config.output_root} is not writable")
    return Report(dependencies, problems, _ytdlp_notices(dependencies["yt-dlp"], state_dir, today))


def _ytdlp_notices(ytdlp: Dependency, state_dir: Path, today: date) -> list[str]:
    if ytdlp.version is None:
        return []
    notices = []
    released = ytdlp_release_date(ytdlp.version)
    if released is not None:
        notices.append(f"yt-dlp is {(today - released).days} days old")
        if released < YTDLP_SECURITY_BASELINE:
            baseline = YTDLP_SECURITY_BASELINE
            notices.append(
                f"yt-dlp is older than {baseline.year}.{baseline.month}.{baseline.day}: "
                "run brew upgrade yt-dlp"
            )
    last_pass = state_dir / LAST_PASS_FILE
    if not last_pass.exists():
        notices.append("last yt-dlp version to pass the network test: not recorded yet")
        return notices
    try:
        passed = last_pass.read_text().strip()
    except OSError, UnicodeDecodeError:
        notices.append(f"{last_pass} is unreadable: run the network test again")
        return notices
    if passed != ytdlp.version:
        notices.append(f"the network test last passed on yt-dlp {passed}: run it again")
    return notices
