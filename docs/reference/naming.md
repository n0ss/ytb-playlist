# Naming reference

```text
<output_root>/<Playlist title> [<playlist_id>]/<YYYY-MM-DD> - <Title> [<video_id>].<mp3|mp4>
```

For example:

```text
Music/YouTube/Lofi Sessions [PLx9a]/2025-03-14 - Rainy Night Mix [dQw4w9WgXcQ].mp3
```

Finder sorts these by date, because the date comes first. Playlist position is left out, so reordering on YouTube never renames a file; it goes in the track tag instead.

## Date

The date is `release_date`, or `upload_date` if that's missing. With neither, it's `0000-00-00`, which sorts first and stands out.

## Title

Names come from untrusted metadata, so titles are cleaned in this order:

1. Normalised to NFC.
2. Whitespace becomes a space. Control characters, broken surrogates and bidirectional controls are removed.
3. `/`, `\` and `:` become ` - `.
4. `"`, `*`, `?`, `<`, `>` and `|` are removed.
5. Repeated spaces collapse, and dots and spaces are stripped from both ends.
6. A title with nothing left becomes `Untitled`.

## Length

A name is at most 200 bytes. Only the title is shortened, on a character boundary, so the date and ID always survive.

## IDs

A video or playlist ID may contain only letters, digits, `_` and `-`. Anything else stops with an error rather than being cleaned, because the ID is how items and folders are identified.

## Folders

A playlist's folder is found by its ` [<playlist_id>]` ending, so renaming a playlist on YouTube keeps the same folder. Two folders with the same ID stop the run with an error naming both.

## Inside a playlist folder

`.ytb-playlist/` is hidden in Finder and holds:

| Path | Owner | Purpose |
| --- | --- | --- |
| `archive.txt` | yt-dlp | Which items are downloaded |
| `state.json` | this tool | Format, tagged items, failures |
| `<id>.info.json` | yt-dlp | Saved metadata, used for tagging |
| `thumbs/` | yt-dlp | Saved thumbnails |
| `tmp/` | this tool | Downloads in progress; partial files resume on the next run |
| `rename-log.jsonl` | this tool | Old and new names, written before each rename |
