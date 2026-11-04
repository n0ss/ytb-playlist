# Technical decisions

## 1. 2026-11-04 — Project bootstrap
- **Decision:** full profile. Python CLI with a GUI-agnostic core. Base skills only, with no repo-scope plugins and no skill search.
- **Why:** long-lived tool with a metadata pipeline and a possible GUI. No specific need is unmet by the base set and user-level rules.
- **Alternatives considered:** light profile; `npx skills find` for Python and CLI skills.

## 2. 2026-11-04 — Python 3.14 and Typer 0.27.x
- **Decision:** target Python 3.14 and Typer 0.27.x.
- **Why:** 3.14 is already the default `python3`, and all dependencies, PySide6 included, resolved wheels-only for macOS arm64. The plan's Typer 0.24.x was out of date; uv resolved 0.27.3. Nothing has been installed or run on 3.14 yet.
- **Alternatives considered:** 3.13 had no real case. 3.15 also resolves, but it's newer and gives this project nothing it needs.

## 3. 2026-11-04 — Use the installed yt-dlp through a subprocess
- **Decision:** run the Homebrew `yt-dlp` as a subprocess with `-J`, `--print` and `--progress-template`. It isn't a Python dependency. The `Backend` protocol stays only as the test seam.
- **Why:** it matches the original request and leaves one copy to update with `brew upgrade yt-dlp`, which also manages Deno and `yt-dlp-ejs`. yt-dlp's README recommends these options for external programs. The plan's claim that a subprocess loses progress reporting was wrong.
- **Alternatives considered:** pinned `yt-dlp[default]` library, which gives cleaner errors and a lockfile but a second copy and a project-level upgrade step. Homebrew's library can't be imported directly, because it lives in a private Python 3.15 environment.
- **Accepted risk:** `brew upgrade` can change behaviour with no lockfile. The network test records the last version it passed, and `doctor` flags any other version.

## 4. 2026-11-04 — Git workflow
- **Decision:** local repository, one branch per phase, one commit per completed task on the user's go-ahead, and a thermo-nuclear review of the whole branch before merging. No remote until v0.1.0, then GitLab.
- **Why:** small commits protect work in progress, and each branch gives the review a diff.
- **Alternatives considered:** one commit per phase; a private GitLab repository after phase 0.
- **Accepted risk:** until v0.1.0 the code exists only on this Mac, so backups must cover `~/projects`.

## 5. 2026-11-04 — Documentation scope
- **Decision:** generated CLI reference, reference pages for `config`, `naming`, `tags` and `exit-codes`, and two how-tos. Decisions go in this file, not an ADR folder. CHANGELOG uses dated entries, with the version in the heading from 0.1.0.
- **Why:** a one-user tool doesn't need the full Diátaxis tree, and this matches the bootstrap templates. Pages get added when a real need appears.
- **Alternatives considered:** the full tree with 11 hand-written pages; Keep a Changelog.

## 6. 2026-11-04 — State and folders
- **Decision:** `archive.txt` owns "downloaded"; `state.json` owns "tagged" and failures, and is written atomically. Anything in the archive but not tagged is retried. Folders are found by playlist ID, and two matches stop the run with an error. Each playlist has one format, and `fetch` refuses a different one. yt-dlp downloads to a temp folder as `%(id)s.%(ext)s`, and `naming.py` sets the final name.
- **Why:** one record per fact avoids disagreement after a crash. Lookup by ID stops a renamed playlist from re-downloading everything. The temp folder gives one naming path, keeps titles out of yt-dlp's file paths, and leaves no partial files in the playlist folder.
- **Alternatives considered:** `state.json` tracking every stage; rebuilding the folder name from the current title; several formats per playlist.

## 7. 2026-11-04 — Failure handling
- **Decision:** failed items are recorded with their reason and date. Permanent failures (no compatible format, private, deleted) are skipped on later runs and listed in a summary without affecting the exit code. Temporary or unrecognised failures are retried and exit 1. `sync --retry-failed` retries everything.
- **Why:** retrying an item that can't succeed adds traffic to YouTube, and a permanent exit 1 would hide new failures.
- **Alternatives considered:** retrying everything on each run.
- **Accepted risk:** classifying failures means parsing yt-dlp's error text, which can change. Anything unrecognised counts as temporary.

## 8. 2026-11-04 — File naming
- **Decision:** `<YYYY-MM-DD> - <Title> [<id>].<ext>` in `<Playlist> [<playlist_id>]/`. The date is `release_date`, else `upload_date`. No time suffix. `"` is removed, `/ \ :` become ` - `, and `* ? < > |` are removed.
- **Why:** `upload_date` is the date YouTube shows on the video page, and `release_date` only exists for premieres and live streams. A time suffix would make a filename depend on other items, and the ID already guarantees uniqueness.
- **Alternatives considered:** per-playlist parsing of the broadcast date from titles. On the test playlist, the upload is 3 days after the title's date on all 7 items compared. Parsing could be added later, and `rename` could fix existing files.

## 9. 2026-11-04 — Apple Music tags
- **Decision:** artist is the channel, minus any ` - Topic` suffix. Album artist is the playlist owner. Album is a per-playlist config override, else the playlist title. Song title is `<YYYY-MM-DD> - <Title>`, without the ID. Track is the playlist position, set once at tagging, with no total and no refresh.
- **Why:** this is the owner's scheme: simple to sort, and it fits radio shows and series. Album artist keeps mixed-channel playlists in one album. The date prefix sorts songs by name and keeps the full date visible.
- **Alternatives considered:** `artist` metadata with fallbacks; `n/N` track numbers refreshed by `sync`, which would rewrite every file on each sync and may not reach Music's library anyway.
- **To verify in phase 1b:** whether Music.app re-reads changed tags after import, and how it displays the date.

## 10. 2026-11-04 — Video format
- **Decision:** H.264 + AAC in MP4, capped at 1080p or a lower per-playlist `max_height`, with no re-encoding. If no compatible stream exists, the item fails with a clear report. `--quality max` is the opt-in that lifts the cap and allows other codecs.
- **Why:** H.264 is the most compatible option, and Music and TV don't import MKV. YouTube serves no H.265 on the sampled episodes, so H.265 would mean re-encoding, with quality loss and extra time. 720p is the better way to save space: about 402 MB of video against 1,410 MB at 1080p on the first test episode.
- **Alternatives considered:** H.265 by default; MKV; falling back to `bv*+ba`.

## 11. 2026-11-04 — Cover art
- **Decision:** square covers are centre-cropped to the shorter side, capped at 1000×1000, and never upscaled. MP4 keeps the source size. JPEG quality steps down from 90 to 75 until under 500 KB; if it still doesn't fit, keep the quality-75 version and log a warning. Per-playlist `cover = "episode" | "playlist"`, default `episode`.
- **Why:** the test playlist serves 1920×1080 thumbnails, so fixed 720×720 and 1280×720 sizes were wrong. A heavy cover shouldn't fail a track.
- **Alternatives considered:** fixed sizes; `--cover playlist` as a flag only, which `sync` wouldn't remember.

## 12. 2026-11-04 — Test strategy
- **Decision:** the test playlist is Radio Nova's "Les intégrales de La dernière". Network tests are opt-in and use its first 3 items, clipped to about 60 seconds. Cases it can't exercise get hand-edited `info.json` fixtures. If the playlist changes, the test fails with a clear "fixture playlist changed" message.
- **Why:** episodes run about 1h40, so full downloads would be slow and heavy.
- **Alternatives considered:** a second playlist for edge cases.
- **To verify in phase 1a:** that clipped downloads work. If they don't, network tests download one full episode as MP3.

## 13. 2026-11-04 — v0.1.0 scope and phase order
- **Decision:** `--json` output is out of v1, and the typed events stay. Minimal config moves to phase 2, `rename` to phase 5, and phase 1 splits into tool spikes (1a) and Music.app spikes (1b). Pre-commit is dropped.
- **Why:** only a non-Python GUI needs `--json`. Each phase has to end on a test it can actually pass. Pre-commit duplicates the user-level hooks, although those only cover Claude's edits and commits.
- **Alternatives considered:** keeping `--json` in v1; the original phase order.

## 14. 2026-11-04 — Use of third-party content
- **Decision:** private personal use only, with no redistribution features, and media files are never committed.
- **Why:** the test playlist is third-party content, and YouTube's terms restrict downloading regardless of use. This records the risk, and doesn't remove it.

## 15. 2026-11-04 — yt-dlp security baseline
- **Decision:** treat 2026.10.26 as the current baseline. GitHub's advisories and NVD agree on the five 2026 CVEs: CVE-2026-26331, CVE-2026-50019, CVE-2026-50023, CVE-2026-50574 and CVE-2026-55404. GitHub also lists GHSA-69qj-pvh9-c5wg, with no CVE. All are fixed by 2026.7.4.
- **Why:** the plan cited these without IDs. The design also avoids the affected paths: no `--exec`, `--netrc-cmd`, `--write-link`, or external downloaders such as aria2c and curl, and `naming.py` sets final filenames.
- **Also checked:** yt-dlp's 2026.10.26 changelog names two critical dependency advisories, GHSA-9v8h-qqgm-4m35 (`brotli`, CVE-2026-111497) and GHSA-6q48-6c7w-9gw2 (`certifi`). Its note covers the release binaries, so the Homebrew environment was checked directly: `brotli` 1.2.1 and `certifi` 2026.10.23, both at or above the fixed versions. The project venv contains neither.

## 16. 2026-11-04 — Installing the command
- **Decision:** install with `uv tool install --editable .` once the CLI is useful, around phase 6. Until then, use `uv run ytb-playlist`.
- **Why:** an editable install follows the source, which suits a one-user tool. `uv tool install --help` shows no `--locked` option, so this install resolves from `pyproject.toml`, not `uv.lock`. That matters less now that yt-dlp isn't a Python dependency.
- **Alternatives considered:** wrapper script; a standalone build.

## 17. 2026-11-04 — Project name
- **Decision:** rename the project `ytb-playlist`: folder, distribution and command `ytb-playlist`, Python module `ytb_playlist`, per-playlist state in `.ytb-playlist/`, environment prefix `YTB_PLAYLIST_`.
- **Why:** owner's choice. Hyphens aren't valid in Python module names, hence the underscore.
- **Alternatives considered:** `ytarchive`, the working name.

## 18. 2026-11-04 — Spike: thumbnails
- **Decision:** read a cover's size from the saved file, never from the `.info.json`. Pass `--no-write-playlist-metafiles`, unless `cover = "playlist"` needs the playlist image.
- **Why:** yt-dlp lists `maxresdefault.webp` as 1920×1080, but the file is 1280×720. All 3 items tested saved as 1280×720 JPEGs of about 86 KB, and the first item's `.webp` was also measured directly. That first item's `hqdefault` is 480×360 and `sddefault` 640×480, both 4:3. So the 1000×1000 square cover is about 720×720 on this playlist, because `cover.py` never upscales. The size budget of 500 KB is far from being reached.
- **Also found:** `--write-thumbnail` also saves the playlist's own image, 336×188 on this playlist. That is very small for `cover = "playlist"`, so spike 1b should judge it at that size.

## 19. 2026-11-04 — Spike: clipped download
- **Decision:** the network test clips with `--download-sections "*0-60"` and must use its own throwaway archive, never a real playlist's `archive.txt`.
- **Why:** on the first item, MP4 gave format `137+140` (H.264 1080p, AAC), 60.06 s, 15.3 MB in 40.7 s. MP3 gave 60.01 s, 1.4 MB in 38.1 s. The `%(id)s.%(ext)s` name is unchanged by clipping. A rerun exits 0 in 0.9 s and prints nothing, so an empty `--print after_move:` result means "nothing new". The archive line holds only the ID, so a clipped item looks fully downloaded and would never be fetched in full.
- **Limit:** the 3-item run is still phase 4's job; this spike used one item.

## 20. 2026-11-04 — Spike: progress and failures
- **Decision:** parse progress from stdout lines with our own prefix, and report the final path with `--print after_move:`. Compute percent from `downloaded_bytes` and `total_bytes_estimate`, capped so it never moves backwards. Classify failures from the `ERROR:` text on stderr, with unknown text treated as transient. Treat an empty result from a playlist or range as an explicit outcome, not as success.
- **Why, progress:** on the sampled HLS audio format, `total_bytes` is `NA` until the `finished` line, the estimate moves, and `_percent` jumps from 100 to 0.26 in the first lines. `--print` and `--progress-template download:` share stdout, but the `postprocess:` template lines arrive on stderr. With `--download-sections`, yt-dlp hands over to ffmpeg: one `finished` line, and ffmpeg's own output, so clipped runs show no live progress.
- **Why, failures:** every failure tested exits 1: missing video, missing playlist, no compatible format, network down, and a batch with one bad item. So the exit code can't separate permanent from transient. A batch still processes its good items and exits 1, unless `--abort-on-error` is passed. A range past the end of a playlist exits 0 with no output. A missing playlist shows as `HTTP Error 400`, which reads like a transient error, so the classifier needs a test case for it.
- **Interrupts:** `SIGTERM` exits -15 and leaves `.part`, `.part-Frag6` and `.ytdl` files, which supports the temp-folder download.
- **Not tested:** two-stream MP4 progress, which should restart per stream, and resuming from `.part` files. Phase 4 covers both. The error strings belong to yt-dlp and can change, so `tests/fixtures/` will record them.
- **Also found:** YouTube warns that 2 unavailable videos are hidden on the test playlist, so a listing can silently omit items.

## 21. 2026-11-04 — Spike: Music.app import
- **Decision:** keep ID3v2.3 with TYER + TDAT as planned. Write no MP4 media kind (`stik`). Keep the date in the title, as in `docs/plan.md`. Keep `cover = "episode"` as the default, with `"playlist"` as a usable option.
- **Why:** imported by the owner in Music.app. v2.3 and v2.4 files looked identical in Get Info, so v2.3 stays the wider-compatibility choice. Music.app shows only the year, so the full date survives only in the title and filename. The H.264 + AAC MP4s imported and landed in Music Videos, in the same album as the MP3s, so `stik` buys nothing. The 188×188 playlist cover was judged acceptable.
- **Not tested:** whether Music.app re-reads tags changed after import. The owner imports files and manages the library, so behaviour after import is out of scope. The test files were one 60-second clip of one episode.
- **Consequence:** the planned import how-to and the phase 5 Music.app checklist are removed, so phase 5 ends at the automated tag round-trip tests, and the docs hold one how-to rather than the two in decision 5.

## 22. 2026-11-04 — `doctor` and minimal config
- **Decision:** ffmpeg, yt-dlp and deno are all required: a missing tool, or one that reports no version, exits 3, and so does an output folder that can't be written. An invalid config exits 2. A yt-dlp older than 2026.7.4, the fix release from decision 15, is a notice only, with exit 0. Binaries are looked up in the config, then `PATH`, then `/opt/homebrew/bin`, and a configured path that doesn't work is reported rather than replaced by another copy.
- **Why:** both formats need ffmpeg, for MP3 conversion and for merging MP4 streams, although the plan first named only yt-dlp and deno. An old yt-dlp can still run, so the owner decides when to upgrade. The exit-code list has no separate code for an unwritable folder, and 3 already means "this machine isn't ready".
- **State:** the last yt-dlp version to pass the network test lives in `last-network-pass.txt` beside the config, not in the repo: it describes this machine, and `doctor` must find it wherever it runs. The network test writes it from phase 4, and until then `doctor` says it's not recorded yet.
- **Deferred:** `YTB_PLAYLIST_*` environment variables wait for phase 6, with the merge precedence tests. Phase 2 reads only the config file and `--config`.

## 23. 2026-11-04 — Naming and URL safety
- **Decision:** beyond the plan's title rules, also strip leading dots and spaces, remove control characters (whitespace ones become a space), and use `Untitled` when nothing is left. A video or playlist ID that isn't only letters, digits, `_` and `-` stops with an error rather than being cleaned. `urls.py` keeps only the playlist ID and returns `https://www.youtube.com/playlist?list=<id>`. It rejects URLs with no playlist, non-YouTube URLs and YouTube auto-mixes (`list=RD…`).
- **Why:** names come from untrusted `.info.json` data. A leading dot would hide a playlist folder in Finder, and `..` must never reach a path. The ID is how items and folders are identified, so a changed ID would be a different item. A hostname check on the parsed URL also refuses look-alikes such as `www.youtube.com.evil.example`. Auto-mixes are generated per viewer and change, so they don't suit a kept folder.
- **Note for phase 4:** titles can contain `[` and `]`, so the folder lookup must compare the ` [<id>]` suffix, not use the name as a glob pattern.
