"""Spike: what do --progress-template and exit codes give us, including when things fail?"""

import subprocess
import time

from _common import OUT, PLAYLIST, first_video_id, ytdlp

TEMPLATE = (
    "download:PROGRESS %(progress.status)s|%(progress.downloaded_bytes)s|"
    "%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress._percent)s|"
    "%(progress.speed)s|%(progress.eta)s|%(info.id)s"
)
MAX_LINES = 40


def stream(label: str, *args: str) -> None:
    """Run until MAX_LINES progress lines, then terminate, as a user interrupt would."""
    dest = OUT / f"progress-{label}"
    dest.mkdir(parents=True, exist_ok=True)
    command = [
        "yt-dlp", "--ignore-config", "--newline", "--progress",
        "--progress-template", TEMPLATE,
        "-o", str(dest / "%(id)s.%(ext)s"),
        *args,
    ]  # fmt: skip
    with subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    ) as process:
        seen = other = 0
        samples = []
        for line in process.stdout:
            if line.startswith("PROGRESS "):
                seen += 1
                if seen <= 3 or seen == MAX_LINES:
                    samples.append(line.strip())
                if seen >= MAX_LINES:
                    process.terminate()
                    break
            else:
                other += 1
                if other <= 8:
                    print(f"  other: {line.strip()[:110]}")
    time.sleep(1)
    print(f"{label}: {seen} progress lines, {other} others, exit {process.returncode}")
    print("\n".join(f"  {sample}" for sample in samples))
    print("  left behind:", sorted(p.name for p in dest.iterdir()))


def complete(*args: str) -> None:
    """Let a small download finish, to see progress and --print on one stream."""
    dest = OUT / "progress-complete"
    dest.mkdir(parents=True, exist_ok=True)
    result = ytdlp(
        "--newline", "--progress", "--progress-template", TEMPLATE,
        "--progress-template", "postprocess:POSTPROCESS %(progress.status)s|%(progress.postprocessor)s",
        "--print", "after_move:FINAL %(filepath)s",
        "-o", str(dest / "%(id)s.%(ext)s"),
        *args,
        timeout=590,
    )  # fmt: skip
    lines = result.stdout.splitlines()
    print(
        f"complete: exit {result.returncode}, {len(lines)} lines, stderr {result.stderr[-200:]!r}"
    )
    print("  line kinds:", sorted({line.split(" ", 1)[0] for line in lines}))
    print("\n".join(f"  {line[:120]}" for line in lines[:2] + lines[-4:]))


def failure(label: str, *args: str) -> None:
    result = ytdlp(*args, timeout=120)
    tail = [line for line in result.stderr.splitlines() if line.strip()][-2:]
    print(f"{label}: exit {result.returncode}, stdout {result.stdout.strip()[:60]!r}")
    print("\n".join(f"  {line[:170]}" for line in tail))


video_id = first_video_id()
good = f"https://www.youtube.com/watch?v={video_id}"
missing = "https://www.youtube.com/watch?v=aaaaaaaaaaa"
print("video:", video_id)

stream("plain", "-f", "wa", good)
complete("-x", "--audio-format", "mp3", "-f", "wa", good)
stream("sections", "-f", "wa", "--download-sections", "*0-300", good)

failure("missing video", "--skip-download", missing)
failure(
    "missing playlist",
    "--skip-download",
    "https://www.youtube.com/playlist?list=PLaaaaaaaaaaaaaaaaaaaa",
)
failure("no compatible format", "--skip-download", "-f", "bv*[vcodec^=nonexistent]", good)
failure("network down", "--skip-download", "--proxy", "http://127.0.0.1:9", "--retries", "0",
        "--socket-timeout", "5", "--extractor-retries", "0", good)  # fmt: skip
failure("batch, good then missing", "--skip-download", "--print", "id", good, missing)
failure("batch, missing then good", "--skip-download", "--print", "id", missing, good)
failure("batch, abort on error", "--skip-download", "--abort-on-error", "--print", "id", missing, good)  # fmt: skip
failure("playlist item range past end", "--skip-download", "--print", "id",
        "--playlist-items", "9000", PLAYLIST)  # fmt: skip
