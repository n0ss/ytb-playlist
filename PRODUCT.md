# ytb-playlist — product

| | |
|---|---|
| Platform | macOS on Apple silicon (MacBook M4) |
| Stack | Python 3.14, uv, Typer + Rich, mutagen, Pillow; Homebrew yt-dlp, ffmpeg, deno |
| Users | One: the owner |
| Purpose | Keep YouTube playlists as local files, ready to import into Apple Music |
| Positioning | Personal tool, not a distributed product |
| Operating context | Runs by hand from the terminal; files go to `~/Music/YouTube` |

## Capabilities
Planned for v0.1.0. Built so far: `doctor`, `info` and untagged `fetch`.
- Download a playlist as MP3 or MP4 into its own folder, one format per playlist.
- Re-run safely: only new items download, and untagged items are retried.
- Name files by the date YouTube shows, so Finder sorts them by date.
- Tag files for Apple Music: channel as artist, show as album, date-prefixed song names, embedded cover.
- Report failed items, and skip permanent failures until `--retry-failed`.
- Check dependencies with `doctor`.

## Constraints
- Private personal use only. No redistribution features, and media files are never committed.
- YouTube's terms restrict downloading regardless of use.
- Depends on yt-dlp keeping up with YouTube changes.
- Default video is H.264 + AAC in MP4, capped at 1080p, because Apple Music imports it reliably.
- Never deletes user files.

## Product principles
- Delete complexity rather than build for needs that don't exist yet.
- Fail clearly rather than silently produce a file Apple Music refuses.
- One naming path, one record of each fact.
