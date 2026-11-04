import pytest

from ytb_playlist.urls import UnsupportedUrlError, playlist_url

PLAYLIST_ID = "PL9wDNu3ZrVQ63LOO81qh8-Ycq6-vIEqcg"
CANONICAL = f"https://www.youtube.com/playlist?list={PLAYLIST_ID}"


@pytest.mark.parametrize(
    "url",
    [
        CANONICAL,
        f"http://www.youtube.com/playlist?list={PLAYLIST_ID}",
        f"https://youtube.com/playlist?list={PLAYLIST_ID}",
        f"https://m.youtube.com/playlist?list={PLAYLIST_ID}",
        f"https://music.youtube.com/playlist?list={PLAYLIST_ID}",
        f"https://WWW.YouTube.com/playlist?list={PLAYLIST_ID}",
        f"https://www.youtube.com/playlist?list={PLAYLIST_ID}&si=abc123&utm_source=share",
        f"https://www.youtube.com/playlist?si=abc123&list={PLAYLIST_ID}#top",
        f"https://www.youtube.com/watch?v=PiZNuhbUERY&list={PLAYLIST_ID}&index=3",
        f"https://youtu.be/PiZNuhbUERY?list={PLAYLIST_ID}",
        f"https://www.youtube.com/show/VL{PLAYLIST_ID}",
        f"https://www.youtube.com/show/VL{PLAYLIST_ID}?si=abc123",
        f"  {CANONICAL}\n",
    ],
)
def test_playlist_urls_normalise_to_one_form(url: str) -> None:
    assert playlist_url(url) == CANONICAL


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("https://www.youtube.com/watch?v=PiZNuhbUERY", "no playlist"),
        ("https://youtu.be/PiZNuhbUERY", "no playlist"),
        ("https://www.youtube.com/playlist", "no playlist"),
        ("https://www.youtube.com/playlist?list=", "no playlist"),
        ("https://www.youtube.com/show/other", "no playlist"),
        ("https://www.youtube.com/watch?v=PiZNuhbUERY&list=RDPiZNuhbUERY", "auto-mix"),
        ("https://www.youtube.com/watch?v=x&list=RDMM", "auto-mix"),
        ("https://vimeo.com/playlist?list=PL1", "not a YouTube"),
        ("https://www.youtube.com.evil.example/playlist?list=PL1", "not a YouTube"),
        ("https://www.youtube.com@evil.example/playlist?list=PL1", "not a YouTube"),
        ("ftp://www.youtube.com/playlist?list=PL1", "not a YouTube"),
        ("youtube.com/playlist?list=PL1", "not a YouTube"),
        ("not a url", "not a YouTube"),
        ("http://[bad", "not a YouTube"),
        ("", "not a YouTube"),
        ("https://www.youtube.com/playlist?list=../evil", "invalid playlist ID"),
        ("https://www.youtube.com/playlist?list=PL1%26x%3D1", "invalid playlist ID"),
    ],
)
def test_unsupported_urls_are_rejected(url: str, message: str) -> None:
    with pytest.raises(UnsupportedUrlError, match=message):
        playlist_url(url)
