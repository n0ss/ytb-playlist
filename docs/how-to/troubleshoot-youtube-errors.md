# Troubleshoot YouTube errors

YouTube changes often, and most breakage is fixed by updating yt-dlp. Start here:

```bash
uv run ytb-playlist doctor
brew upgrade yt-dlp
```

After an upgrade, run the network test. `doctor` notices the new version until a test passes on it:

```bash
uv run pytest -m network -q
```

## Failures are sorted into two kinds

Yt-dlp exits with the same code for every failure, so this tool reads its error text. Text it doesn't recognise counts as temporary, so nothing is written off by mistake.

| Kind | Examples | What happens |
| --- | --- | --- |
| Permanent | `This video is unavailable`, `Private video`, `Requested format is not available` | Skipped on later runs and counted as skipped. Exit code unaffected. |
| Temporary | Timeouts, `HTTP Error 403`, bot checks, anything unrecognised | Retried on the next run. Exit code 1. |

The reason and date for each failure are in `.ytb-playlist/state.json`. To try permanent failures again:

```bash
uv run ytb-playlist sync NAME --retry-failed
```

## Common messages

**`Sign in to confirm you're not a bot`**: YouTube is limiting this connection. Wait, then retry in smaller batches with `--items 1:10`, or raise `sleep_min` and `sleep_max` in the config. This tool doesn't use browser cookies.

**`HTTP Error 403`**: often temporary. Run the same command again, because partial files resume. If it persists, upgrade yt-dlp.

**`Requested format is not available`**: the item has no H.264 and AAC stream at or below the height cap. Try `--max-height 1080`, or `--quality max`, which also accepts formats the Apple apps may refuse.

**`HTTP Error 400` on a playlist**: check the URL. A mistyped or deleted playlist gives this error rather than a clear "not found". It exits 4.

**`not a YouTube URL` or `no playlist in this URL`**: the tool takes playlists only, so a plain video link is refused. Open the playlist and copy its URL.

**`YouTube auto-mixes aren't supported`**: lists starting `RD` are generated per viewer and change over time.

**`not found: deno`**: since late 2025, YouTube extraction needs a JavaScript runtime. Run `brew install deno`.

**`this playlist is kept as mp3`**: each playlist keeps one format, because the archive tracks IDs rather than formats. To get both, use a separate `--out` folder.

## A tool works in the terminal but not from an app

Apps opened from Finder don't inherit your shell's `PATH`. The tool also looks in `/opt/homebrew/bin`, and you can set exact paths under `[binaries]`. See `docs/reference/config.md`.
