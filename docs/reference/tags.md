# Tags reference

MP3 files get ID3v2.3 with no ID3v1 tag. Text frames use UTF-16. MP4 files get iTunes atoms. Tags from ffmpeg are replaced, and an empty value is left out.

| Field | Source | MP3 frame | MP4 atom |
| --- | --- | --- | --- |
| Title | `<date> - <cleaned title>` | `TIT2` | `©nam` |
| Artist | `channel`, else `uploader`, minus any ` - Topic` | `TPE1` | `©ART` |
| Album | Saved playlist `album`, else `playlist_title` | `TALB` | `©alb` |
| Album artist | `playlist_uploader`, else the artist | `TPE2` | `aART` |
| Track | `playlist_index`, set once | `TRCK` | `trkn` |
| Date | The date from the name, if known | `TYER` and `TDAT` | `©day` |
| Genre | Saved playlist `genre`, else config `genre` | `TCON` | `©gen` |
| Description | `description`, first 4,000 characters | `COMM` | `desc` (255 characters) and `ldes` |
| Source URL | `webpage_url` | `WOAS` | `----:com.apple.iTunes:URL` |
| Video ID | `id` | `TXXX:YOUTUBE_ID` | `----:com.apple.iTunes:YOUTUBE_ID` |
| Cover | See below | `APIC` type 3 | `covr` |

Music.app shows only the year, which is why the full date is also in the title. MP4 files set no media kind, because they land in Music Videos without one.

## Covers

- MP3 uses `square`: a centre crop to the shorter side, capped at 1000×1000, never upscaled.
- MP4 uses `wide`: the source size.
- `tag` and `cover` accept `--cover square` or `--cover wide` to change the shape.
- The MP3 cover frame uses Latin-1 for its label, unlike the other frames, because Music.app can't read a UTF-16 picture frame.
- All covers are JPEG with no EXIF. Quality steps down from 90 to 75 until the image fits in 500 KB. If it still doesn't fit, it's kept at 75 with a warning.
- The `cover = "playlist"` setting uses the playlist's image for every track, falling back to the episode's thumbnail if there isn't one.

A missing or damaged thumbnail gives a warning, and the other tags are still written.

## Safe writes

Tags are written to a copy beside the file, which then replaces it in one atomic step. An interrupted write can't damage a finished file.
