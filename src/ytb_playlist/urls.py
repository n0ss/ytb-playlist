# SPDX-License-Identifier: GPL-3.0-only
"""Turn a pasted YouTube URL into its one canonical playlist URL."""

from urllib.parse import parse_qs, urlsplit

from ytb_playlist.naming import is_safe_id

HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
SCHEMES = {"http", "https"}
SHOW_PREFIX = "/show/VL"
AUTO_MIX_PREFIX = "RD"


class UnsupportedUrlError(ValueError):
    """The URL isn't a usable YouTube playlist."""


def playlist_url(url: str) -> str:
    return f"https://www.youtube.com/playlist?list={playlist_id(url)}"


def playlist_id(url: str) -> str:
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError as error:
        raise UnsupportedUrlError(f"not a YouTube URL: {url}") from error
    if parts.scheme not in SCHEMES or host not in HOSTS:
        raise UnsupportedUrlError(f"not a YouTube URL: {url}")

    if parts.path.startswith(SHOW_PREFIX):
        found = parts.path.removeprefix(SHOW_PREFIX)
    else:
        found = parse_qs(parts.query).get("list", [""])[0]

    if not found:
        raise UnsupportedUrlError(f"no playlist in this URL: {url}")
    if found.startswith(AUTO_MIX_PREFIX):
        raise UnsupportedUrlError(f"YouTube auto-mixes aren't supported: {url}")
    if not is_safe_id(found):
        raise UnsupportedUrlError(f"invalid playlist ID in this URL: {url}")
    return found
