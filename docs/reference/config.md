# Configuration reference

The config file is `~/Library/Application Support/ytb-playlist/config.toml` on macOS, or `$XDG_CONFIG_HOME/ytb-playlist/config.toml` elsewhere (`~/.config` when that variable is unset). It's optional. `ytb-playlist config path` shows the file in use, and `ytb-playlist config show` shows the merged result.

Each setting takes the first value it finds, in this order:

1. A command-line flag, where one exists
2. The saved playlist's own setting
3. A `YTB_PLAYLIST_*` environment variable
4. `config.toml`, or the file passed with `--config`
5. The default

An unknown key is an error, so a typo can't silently do nothing.

| Key | Environment variable | Type | Default | Meaning |
| --- | --- | --- | --- | --- |
| `output_root` | `YTB_PLAYLIST_OUTPUT_ROOT` | absolute path, `~` allowed | `~/Music/YouTube` | Folder that holds the playlist folders |
| `genre` | `YTB_PLAYLIST_GENRE` | text | `YouTube` | Genre tag |
| `cover` | `YTB_PLAYLIST_COVER` | `episode` or `playlist` | `episode` | Each track's own thumbnail, or the playlist's image on every track |
| `max_height` | `YTB_PLAYLIST_MAX_HEIGHT` | whole number, at least 1 | `1080` | Height cap for MP4 video |
| `sleep_min` | `YTB_PLAYLIST_SLEEP_MIN` | whole number, at least 0 | `3` | Shortest wait before each download, in seconds |
| `sleep_max` | `YTB_PLAYLIST_SLEEP_MAX` | whole number, at least 0 | `8` | Longest wait, in seconds; can't be below `sleep_min` |
| `binaries` | none | table of absolute paths | found automatically | Paths for `yt-dlp`, `ffmpeg` and `deno` |

Without a configured path, a tool is looked for on `PATH`, then in `/opt/homebrew/bin`. A configured path that doesn't work is reported, not replaced by another copy.

```toml
output_root = "~/Music/YouTube"
genre = "Radio"
max_height = 720

[binaries]
yt-dlp = "/opt/homebrew/bin/yt-dlp"
```

## Saved playlists

`ytb-playlist playlist add` writes `playlists.toml` in the default config folder, even when `--config` points elsewhere. It's a generated file: hand edits to its values are kept, but comments aren't.

| Key | Required | Meaning |
| --- | --- | --- |
| `url` | yes | The playlist's canonical URL |
| `playlist_id` | yes | Finds this entry from `fetch`, `tag` and `cover` |
| `format` | yes | `mp3` or `mp4`, fixed once a folder exists |
| `album` | no | Album tag, instead of the playlist title |
| `genre` | no | Genre tag |
| `cover` | no | `episode` or `playlist` |
| `max_height` | no | Height cap for this playlist |

`fetch`, `sync`, `tag` and `cover` all use these settings, so tags don't depend on which command ran.

## Machine state

`last-network-pass.txt` sits in the same folder. It records the last yt-dlp version to pass the network test, and `doctor` flags any other version.
