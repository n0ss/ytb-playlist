# ytb-playlist — Plan

Nov 4, 2026 · @Yohan

## Summary and key decisions

Build a Python 3.14 CLI (`ytb-playlist`) on uv + Typer, driving your installed yt-dlp as a subprocess, tagging with mutagen, and keeping the core GUI-agnostic so a Textual TUI and later a PySide6 app are thin shells. Profile: **full** (long-lived tool, future GUI, metadata pipeline).

| Decision | Choice | Why |
| --- | --- | --- |
| Language / tooling | Python 3.14, uv, ruff, pytest | mutagen, Pillow and the GUI options are Python; all dependencies, PySide6 included, resolve wheels-only on macOS arm64 for 3.14 (checked Nov 4, 2026) |
| yt-dlp integration | Your Homebrew `yt-dlp` run as a subprocess with `-J`, `--print` and `--progress-template` | The interface yt-dlp's README recommends for external programs. One copy on your Mac, updated with `brew upgrade yt-dlp`. Homebrew also manages Deno and `yt-dlp-ejs`. A small `Backend` protocol stays only as the test seam, replaying recorded output |
| JS runtime | Deno on PATH (mandatory in practice) | Since 2025.11.12, YouTube without an external JS runtime is deprecated; only Deno is enabled by default |
| Media tools | ffmpeg (Homebrew) | Audio extraction, remux, thumbnail conversion |
| CLI | Typer 0.27.x + Rich | Type-hint CLI, completion, `--help` generated from code |
| Tagging | mutagen 1.48.x, own tagging pass after yt-dlp | Full control of ID3v2.3 frames and MP4 atoms for Apple Music |
| Images | Pillow | Square crop / resize of covers |
| VCS | Local git, no remote until v0.1.0, then GitLab; one commit per completed task, each on your go-ahead; one branch per phase | Each branch gives the thermo-nuclear review a diff to work from |

Prerequisites check on the M4:

```bash
yt-dlp --version && ffmpeg -version | head -1 && deno --version
brew install yt-dlp deno ffmpeg uv   # whatever is missing
```

## GUI benchmark

Recommendation: Textual TUI first (days, reuses the core, runs in your terminal), then PySide6 if you want a real Mac app. SwiftUI only if you accept a Mac-only app calling the CLI's `--json` output as a subprocess, which would be added at that point.

| Option | Language | Reuses Python core | macOS feel | Footprint | Packaging / licence | Effort | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Textual | Python | In-process | Terminal UI | Tiny | pip / MIT | Low | Step 1 |
| PySide6 (Qt 6) | Python | In-process | Good (styled native) | \~30–150 MB bundle | PyInstaller or Briefcase / LGPL | Medium | Step 2, recommended desktop |
| NiceGUI | Python | In-process | Web page in browser | Small + local server | pip / MIT | Low | Fine for a local dashboard, not a Mac app |
| Flet | Python | In-process | Material/Cupertino, Flutter-drawn | Large Flutter runtime | flet build / Apache-2.0 | Low–medium | Only if mobile matters |
| Tauri 2 | Rust + TS | Subprocess / sidecar | WKWebView | <10 MB shell + Python sidecar | tauri bundle / MIT-Apache | High (3 languages) | Not worth it here |
| SwiftUI | Swift | Subprocess (`--json`) | Best, native | Smallest | Xcode, notarisation | High (new language) | Mac-only polish option |

Design rule that keeps all options open: the core exposes `sync(playlist, options, on_event)` and emits typed events (queued, progress, tagged, done, error). The CLI renders them with Rich, Textual and Qt subscribe to the same stream. A `--json` NDJSON output can be added when a non-Python GUI needs it; v1 doesn't include it.

Packaging trap for any GUI launched from Finder: macOS apps do not inherit your shell PATH, so `yt-dlp`, `deno` and `ffmpeg` disappear. Resolve absolute paths at startup (config + `/opt/homebrew/bin` fallback) and show them in a `doctor` command.

## CLI structure

Noun-light, verb-first commands; one playlist = one folder, in one format; every run is idempotent thanks to per-playlist state.

```text
ytb-playlist
├── doctor                     # check yt-dlp, ffmpeg, deno, versions, PATHs, write access
├── info    URL                # playlist title, id, count, date range; no download
├── fetch   URL... --format mp3|mp4 [--out DIR] [--items 1:10] [--dry-run]
├── sync    [NAME|--all] [--retry-failed]   # re-run saved playlists, download only new entries
├── playlist
│   ├── add    URL --format mp3|mp4 [--name NAME]   # register in config
│   ├── list
│   └── remove NAME
├── tag     PATH... [--from-info-json] [--cover square|wide]   # (re)tag existing files
├── cover   PATH... [--refetch]                         # (re)extract and embed cover
├── rename  PATH... [--dry-run]                         # apply naming convention to existing files
└── config  show|path|edit

Global: --config FILE  -v/-q  --no-color  --version
```

| Concern | Choice |
| --- | --- |
| Config | TOML at `~/Library/Application Support/ytb-playlist/config.toml` (or XDG on Linux), overridable by `--config` and `YTB_PLAYLIST_*` env vars |
| Per-playlist state | `<playlist folder>/.ytb-playlist/` holding `archive.txt` (yt-dlp `--download-archive`), `*.info.json`, original thumbnails, `state.json`. `archive.txt` owns "downloaded"; `state.json` records "tagged" and failed items with reason and date, is written atomically (temp file, then rename), and anything in the archive but not tagged is retried. Permanent failures (no compatible format, private, deleted) are skipped on later runs and listed in a summary without affecting the exit code; temporary or unrecognised failures are retried and exit 1; `sync --retry-failed` retries everything |
| Folder lookup | Always by `* [<playlist_id>]`, never rebuilt from the current title, so a playlist renamed on YouTube keeps its folder and state. Two matching folders stop the run with an error listing both |
| Format changes | The format is fixed per playlist; `fetch` refuses a different format on an existing playlist, because the archive tracks IDs, not formats |
| URL handling | Normalised before use: tracking parameters stripped, `youtube.com/show/VL<id>` rewritten to `playlist?list=<id>` (yt-dlp gets HTTP 400 on the `/show/` form) |
| Exit codes | 0 ok · 1 partial (some items failed) · 2 usage error · 3 missing dependency · 4 network/extractor error |
| Safety | `--dry-run` on every write command; never delete user files; `rename` writes an undo log |
| Politeness | Default `sleep_interval` 3–8 s between items, configurable; no cookies unless `--cookies-from-browser` is passed explicitly |

Module layout the CLI sits on:

```text
src/ytb_playlist/
  cli/        # Typer app, one module per command, Rich rendering
  core/       # sync engine, events, models (pydantic or dataclasses)
  backends/   # ytdlp_proc.py behind a small Protocol; tests replay recorded output
  urls.py     # URL normalisation
  naming.py   # filename/folder builder + sanitiser
  tagging/    # id3.py, mp4.py, mapping.py
  cover.py    # thumbnail pick, convert, crop
  config.py   # load/merge/validate
  deps.py     # binary discovery for doctor
```

## CLI documentation structure

Single source of truth is the Typer code: help text lives in docstrings and option `help=`, and the CLI reference is generated, never hand-written. Other docs stay small for v0.1.0: reference pages for contracts the code must honour and two how-tos. Add pages when a real need appears.

```text
README.md                 # what it is, prerequisites, install, 3 example commands
PRODUCT.md                # from the project-bootstrap template
CHANGELOG.md              # dated entries linking to decisions; version in the heading from 0.1.0
docs/
  tech-decisions.md       # every decision, including spike results
  test-procedure.md
  how-to/
    import-into-apple-music.md
    troubleshoot-youtube-errors.md   # deno, bot checks, update yt-dlp
  reference/
    cli.md                # GENERATED from Typer
    config.md             # every TOML key, type, default, env var
    naming.md             # the convention below, with examples
    tags.md               # field → ID3 frame → MP4 atom mapping table
    exit-codes.md
```

```bash
# regenerate CLI reference (Typer built-in)
uv run typer ytb_playlist.cli.app utils docs --name ytb-playlist --output docs/reference/cli.md
```

A test fails if `docs/reference/cli.md` is stale (regenerate in a temp file and diff), so help text and docs cannot drift. Shell completion: `ytb-playlist --install-completion zsh`.

## Naming convention

ISO date first, then title, then the video ID: Finder's name sort is then by date, and the ID guarantees uniqueness and traceability. There is no time suffix, because it would make a filename depend on other items.

```text
<root>/<Playlist Title> [<playlist_id>]/<YYYY-MM-DD> - <Title> [<video_id>].<mp3|mp4>

Music/YouTube/Lofi Sessions [PLx9a…]/2025-03-14 - Rainy Night Mix [dQw4w9WgXcQ].mp3
```

| Element | Source field | Rule |
| --- | --- | --- |
| Date | `release_date`, else `upload_date` | `release_date` is the premiere/live air date; `upload_date` otherwise. Missing → `0000-00-00` so it sorts first and is visible. `upload_date` is the date YouTube shows on the video page. It can differ from the broadcast date (3 days later on all 7 test-playlist items compared); accepted for v1 |
| Title | `title` | NFC-normalised; `"` removed; `/ \ :` become ` - `; `* ? < > \|` removed; double spaces collapsed; trailing dots/spaces stripped; truncated so the full name stays ≤ 200 bytes (APFS limit is 255 bytes UTF-8) |
| Separator | `-` | Readable; never appears inside the date |
| ID | `id` | Always kept, in brackets |
| Folder | `playlist_title` + `playlist_id` | Title taken at creation; later runs find the folder by ID, so it survives playlist renames on YouTube |

yt-dlp output template equivalent (useful for the first spike, before `naming.py` owns it):

```bash
yt-dlp -o "%(playlist_title)s [%(playlist_id)s]/%(release_date>%Y-%m-%d,upload_date>%Y-%m-%d|0000-00-00)s - %(title)s [%(id)s].%(ext)s" URL
```

Caveats: do not take dates or titles from `--flat-playlist` listings; fetch full metadata per item. Dates there are approximate, and titles can be auto-translated (the test playlist's listing mixes English and French, while per-item metadata gives the original French). Playlist position is deliberately **not** in the name; it goes in the track-number tag instead, so reordering on YouTube never renames files.

## Tagging plan for Apple Music (iTunes) import

yt-dlp downloads and converts; a separate mutagen pass writes the final tags from the saved `.info.json`, so files can be re-tagged offline at any time. MP3 gets ID3v2.3 (UTF-16), MP4 gets iTunes atoms.

| Field | Source (info.json) | MP3 – ID3v2.3 frame | MP4 atom |
| --- | --- | --- | --- |
| Title | `<date> - <sanitised title>`, the filename without `[id]` | TIT2 | ©nam |
| Artist | `channel` → `uploader`, with any ` - Topic` suffix stripped | TPE1 | ©ART |
| Album | per-playlist `album` in config, else `playlist_title` | TALB | ©alb |
| Album artist | playlist owner (`playlist_uploader`) | TPE2 | aART |
| Track | `playlist_index`, set once at tagging; no total, no refresh on `sync` | TRCK `n` | trkn |
| Date | date (naming rule) | TYER + TDAT (v2.3 has no TDRC) | ©day `YYYY-MM-DD` |
| Genre | config per playlist (default "YouTube") | TCON | ©gen |
| Description | `description` (first 4 000 chars) | COMM (lang `eng`) | desc + ldes |
| Source URL | `webpage_url` | WOAS | ----:com.apple.iTunes:URL (freeform) |
| Video ID | `id` | TXXX:YOUTUBE\_ID | ----:…:YOUTUBE\_ID |
| Cover | see next section | APIC type 3 (front), JPEG | covr (JPEG) |
| Media kind | — | — | stik (music video = 6; to verify) |

Steps:

1. Spike: tag one MP3 as v2.3 and one as v2.4, import both in Music.app on macOS, check every field and the cover. This replaces the forum folklore that iTunes mishandles v2.4 with a real result on your machine.
2. Write `tagging/mapping.py` as pure functions (info dict → neutral `TrackTags` model) — 100 % unit-testable.
3. `tagging/id3.py` and `tagging/mp4.py` serialise `TrackTags` with mutagen; strip ffmpeg-written tags first so only yours remain.
4. Round-trip tests: write → read back with mutagen → compare model.
5. Import test checklist in `docs/how-to/import-into-apple-music.md` (manual; Music.app is not scriptable enough to automate reliably).

MP4 compatibility: Music/TV apps import H.264 + AAC in MP4 reliably. YouTube's best streams are often VP9/AV1 + Opus, so the default format selector accepts only `avc1` + `m4a`, capped at 1080p or a lower per-playlist `max_height` (720p is about 72 % smaller on the test playlist's first episode). YouTube serves no H.265 on the sampled items, so there is no re-encoding, and MP4 stays the container because Music and TV don't import MKV. If no compatible stream exists, the item fails with a clear report rather than silently producing a file the Apple apps refuse. `--quality max` is the opt-in that adds `bv*+ba` and lifts the cap:

```bash
-f "bv*[vcodec^=avc1][height<=1080]+ba[ext=m4a]/b[ext=mp4][vcodec^=avc1][height<=1080]" --merge-output-format mp4
```

MP3: `-x --audio-format mp3 --audio-quality 0` (VBR V0). Note that YouTube audio is already lossy (Opus/AAC), so MP3 is a second lossy generation; AAC/M4A would be better quality-per-byte if you ever relax the MP3 requirement.

## Cover art from YouTube thumbnails

Let yt-dlp fetch the best thumbnail and convert it to JPEG, then crop and embed it ourselves: square for MP3 (album art grid), 16:9 untouched for MP4 (video poster).

1. **Fetch:** `--write-thumbnail --convert-thumbnails jpg` (YouTube often serves WebP, which ID3 APIC and MP4 covr don't reliably accept). yt-dlp picks the highest-preference thumbnail from the info dict, usually `maxresdefault` (1280×720, or 1920×1080 as on the test playlist); fall back to `hqdefault` (480×360) when absent.
2. **Store:** original kept in `.ytb-playlist/thumbs/<id>.jpg` so re-tagging never refetches.
3. **Transform (Pillow, `cover.py`):**
   - MP3, mode `square` (default): centre crop to the shorter side, capped at 1000×1000, never upscaling. Mode `pad`: 16:9 image letterboxed on a blurred square background, for thumbnails with text at the edges.
   - MP4, mode `wide`: keep the source size.
   - Re-encode JPEG, strip EXIF, and step quality down from 90 to 75 until the image is under 500 KB. If it still doesn't fit, keep the quality-75 version and log a warning.
4. **Embed:** in the mutagen pass (APIC type 3 / covr), not with `--embed-thumbnail`, so one code path handles both formats and retagging.
5. **Option:** per-playlist `cover = "episode" | "playlist"` in config, default `episode`, with `--cover playlist` as the one-off flag. `playlist` uses the playlist thumbnail for every track, giving a uniform album in Music.app; the Music.app spike compares the two.

Tests: fixtures of 1920×1080, 1280×720, 480×360 and 4:3 letterboxed JPEGs → assert output size, mode, quality stepping and the over-budget warning; embedding round-trip asserts the APIC/covr bytes match.

For quick manual testing before the code exists:

```bash
yt-dlp -x --audio-format mp3 --embed-thumbnail --convert-thumbnails jpg \
  --ppa "EmbedThumbnail+ffmpeg_o:-c:v mjpeg -vf crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'" URL
```

## Research, development and testing plan

Eight small phases (0–7, with phase 1 in two parts), each ending with a test that passes before the next starts. Network tests are opt-in (`pytest -m network`) against the test playlist below, on its first 3 items clipped to about 60 seconds; everything else runs offline from recorded `info.json` fixtures.

| # | Phase | Deliverable | Done when (test) |
| --- | --- | --- | --- |
| 0 | Bootstrap | Project files from `/project-bootstrap`, uv project, `src/` layout, ruff, pytest, local `git init` on your go-ahead. Open checks done: decisions 15 and 16 | `uv run pytest` green on an empty test; `ruff check` clean |
| 1a | Tool spikes (Claude) | `spikes/` scripts: thumbnail sizes; clipped download with `--download-sections`; progress parsing and failure handling from `--progress-template` and exit codes | One entry per spike in `docs/tech-decisions.md` |
| 1b | Music.app spikes (you and Claude) | v2.3 vs v2.4; whether Music.app re-reads changed tags after import; how it displays the date; avc1 MP4 import; episode vs playlist cover | One entry per spike in `docs/tech-decisions.md` |
| 2 | Deps + config + `doctor` | Minimal `config.py` (load, binary paths), binary discovery, version checks, `doctor` command | Unit tests with faked PATH; config load tests; `doctor` exit 3 when yt-dlp or deno missing; notice when yt-dlp differs from the last version the network test passed |
| 3 | Naming + URLs | `naming.py`, `urls.py` | Table-driven tests: dates/fallbacks, Unicode, 255-byte limit, forbidden chars including leading quotes, `/show/VL…` URLs; sorted list == date order |
| 4 | Fetch engine | `info`, `fetch` (mp3/mp4), archive, `state.json`, folder lookup by ID, temp-folder download moved to its final name, events | Offline: fake backend replays recorded yt-dlp output and emits expected events; a renamed playlist reuses its folder; two matching folders stop with an error; a format change is refused; permanent failures are skipped on later runs; an interrupted download leaves nothing in the playlist folder. Network: 3 clipped items download, rerun downloads 0 |
| 5 | Tagging + cover + existing files | mapping, id3, mp4, cover; `tag`, `cover`, `rename` commands | Round-trip tag tests; image size tests; `rename --dry-run` tests; an untagged download is retried; manual Music.app import checklist signed off |
| 6 | Sync + full config | `playlist add/list/remove`, `sync --all`, full TOML config | Config merge precedence tests; sync adds only new items; `--retry-failed` retries permanent failures |
| 7 | Docs + polish | Generated CLI reference, how-tos, CHANGELOG 0.1.0 | Docs-staleness test green; README commands copy-paste-run |

Each phase runs on its own local branch, with one commit per completed task on your go-ahead, and ends with `/thermo-nuclear-code-quality-review` (review only, no edits until you approve the findings) before any request to merge into `main`.

Test playlist: [Les intégrales de "La dernière"](https://www.youtube.com/playlist?list=PL9wDNu3ZrVQ63LOO81qh8-Ycq6-vIEqcg) (Radio Nova): public, 83 items at last check, about 1h40 each on the items sampled. The first episode is about 1.5 GB as 1080p H.264 + AAC, of which 94 MB is the AAC stream, hence the clipped network tests. Sampled items also make useful fixtures: null `release_date`, null `artist`, quotes at the start of the title, and French accents. If the playlist changes, the network test fails with a clear "fixture playlist changed" message.

Cases this playlist can't exercise get hand-edited `info.json` fixtures in `tests/fixtures/`: `release_date` present, a ` - Topic` channel, permanent failures, album artist different from artist, and the `hqdefault` fallback.

Then GUI: Textual shell over the event stream (phase 8), PySide6 prototype (phase 9) only after the CLI has been used for real for a few weeks.

Test pyramid: \~80 % unit (pure functions: naming, mapping, config), \~15 % component (mutagen/Pillow on fixture files, mocked backend), \~5 % network smoke. Record fixtures once with `yt-dlp -J URL > tests/fixtures/<id>.info.json` and scrub personal fields.

## Risks and open questions

| Risk | Impact | Mitigation |
| --- | --- | --- |
| YouTube changes break extraction | Downloads fail without warning | `doctor` shows yt-dlp age; documented update path (`brew upgrade yt-dlp`) |
| `brew upgrade` changes yt-dlp behaviour | No lockfile protects the tool; offline tests won't notice | The network test records the last yt-dlp version it passed; `doctor` flags any other installed version so you know to re-run it |
| Bot checks / rate limiting | 403s, "sign in to confirm" | Sleep intervals, small batches; cookies only on explicit flag, and only from a throwaway account (account flagging risk) |
| yt-dlp security issues (2026: CVE-2026-26331, CVE-2026-50019, CVE-2026-50023, CVE-2026-50574, CVE-2026-55404, GHSA-69qj-pvh9-c5wg, all fixed by 2026.7.4; see decision 15) | Code execution / odd files | Stay current; run yt-dlp with argument lists only, never pass metadata into `--exec` or shell strings; yt-dlp downloads to a temp folder as `%(id)s.%(ext)s`, and `naming.py` sets the final name |
| yt-dlp/Deno/ffmpeg missing when launched from a GUI | Silent format loss | Absolute paths in config, checked at startup |
| Copyright / YouTube ToS | Legal exposure | Private personal use only, including third-party content such as the test playlist; YouTube's terms restrict downloading regardless; no redistribution features; media files are never committed |
| Double lossy MP3 | Audible artefacts on some sources | Document it; consider AAC option later |
| Long episodes | About 1.5 GB per MP4 episode on the test playlist, so roughly 125 GB for all 83 | Clipped network tests; MP3 or `max_height` for long spoken playlists |

Decisions confirmed Nov 4, 2026:

- Backend: installed Homebrew yt-dlp through a subprocess, no library dependency.
- Root output folder: `~/Music/YouTube`.
- Music.app import: manual for v1.
- Formats: one per playlist.
- Same-day items: no time suffix.
- MP4: H.264 + AAC, capped at 1080p, no re-encoding; no fallback to formats the Apple apps refuse, unless `--quality max` is passed.

## Bootstrap brief for /project-bootstrap

Paste into Claude Code. Skills: everything in your catalog's base set applies; no repository-specific entry fits and no specific need is unmet, so the `npx skills find` search is skipped.

```markdown
Goal: CLI (later GUI) that downloads YouTube playlists via yt-dlp into one folder per playlist, as MP3 or MP4, named by date and fully tagged (ID3v2.3 / MP4 atoms + cover) for Apple Music import.
Users: me, on a MacBook M4 (macOS, Apple silicon).
Profile: full.
Stack: Python 3.14, uv, Typer 0.27.x + Rich, mutagen 1.48.x, Pillow, pytest, ruff. System deps (Homebrew): yt-dlp (run as a subprocess), ffmpeg, deno.
Repo: local git, no remote until v0.1.0, then GitLab. Never commit without my go-ahead. One branch per phase, one commit per completed task.
Layout: src/ytb_playlist/{cli,core,backends,tagging}/, urls.py, naming.py, cover.py, config.py, deps.py; tests/{unit,component,network}/ + fixtures/; docs/ (tech-decisions.md, test-procedure.md, how-to/, reference/); spikes/.
Skills: catalog base set (superpowers, task-observer, hookify, security-guidance, claude-md-management, context7, project-bootstrap, thermo-nuclear-code-quality-review). No repo-scope entries. No skill search.
Conventions: filename '<YYYY-MM-DD> - <Title> [<id>].<ext>' in '<Playlist> [<playlist_id>]/'; date = release_date else upload_date, no time suffix; state in '<playlist>/.ytb-playlist/'; folder found by playlist ID; one format per playlist.
Tags: artist = channel (minus " - Topic"); album artist = playlist owner; album = config override else playlist title; title = '<YYYY-MM-DD> - <Title>'; track = playlist position, no total.
Test playlist: https://www.youtube.com/playlist?list=PL9wDNu3ZrVQ63LOO81qh8-Ycq6-vIEqcg (83 long episodes: network tests use 3 clipped items).
Each phase: own branch, thermo-nuclear review of the whole branch before asking to merge.
Full plan: docs/plan.md (move this plan file there).
Decisions: seed docs/tech-decisions.md with the decisions from the Nov 4, 2026 plan review, each with its reason; the first CHANGELOG entry links to it.
.gitignore: also *.mp3, *.mp4, *.m4a, *.webm, *.part, .ruff_cache/, .venv/. Recorded info.json fixtures stay tracked, scrubbed of personal fields.
Plan with tests:
0 Bootstrap: uv project, ruff, pytest, git init on go-ahead; check CVE IDs, how ytb-playlist gets on PATH → empty test green.
1a Tool spikes: thumbnails, clipped download, progress and failure parsing → entries in docs/tech-decisions.md.
1b Music.app spikes: ID3 v2.3 vs v2.4, tag re-reading, date display, avc1 MP4 import, episode vs playlist cover → entries in docs/tech-decisions.md.
2 minimal config + deps + doctor → faked-PATH unit tests, config load tests, exit 3 without yt-dlp or deno.
3 naming + URL normalisation → table-driven tests incl. Unicode, 255-byte limit, /show/VL URLs.
4 info/fetch engine + archive + state.json + lookup by ID + temp-folder download + events → fake-backend tests; opt-in network test on 3 clipped items (rerun downloads 0).
5 tagging + cover + tag/cover/rename commands → round-trip tests, image tests, untagged retry, manual Music.app checklist.
6 playlist add/list/remove + sync + TOML config → precedence tests, --retry-failed.
7 docs generated from Typer + staleness test; CHANGELOG 0.1.0.
```

Baseline note: the "resolve absolute paths for Homebrew binaries" helper and the "opt-in network test marker" convention would serve other Python tools too; consider moving them into `~/.claude/rules/` rather than this repo.

## Sources

All updated within the last 12 months (Nov 2025 – Nov 2026), read via web search results. Older forum threads on iTunes and ID3v2.4 were excluded; that question is instead a test in phase 1.

- [yt-dlp releases (2026.08.19 latest seen; Python 3.10 drop, 2026 CVEs)](https://github.com/yt-dlp/yt-dlp/releases)
- [yt-dlp issue #15012 — external JS runtime required, Deno default](https://github.com/yt-dlp/yt-dlp/issues/15012)
- [GIGAZINE — yt-dlp needs Deno, Nov 2025](https://www.gigazine.net/gsc_news/en/20251113-yt-dlp-required-deno-javascript-runtime)
- [ArcDLP v1.3.7 release — Deno missing from PATH in Finder-launched apps, May 2026](https://github.com/archisvaze/arcdlp/releases/tag/v1.3.7)
- [yt-dlp man page, openSUSE Leap 16 — archive and break options](https://manpages.opensuse.org/Leap-16.0/yt-dlp/yt-dlp.1.en.html)
- [Python GUIs — which Python GUI library, 2026](https://www.pythonguis.com/faq/which-python-gui-library/)
- [Unite.AI — best Python GUI libraries, reviewed Jul 2026](https://www.unite.ai/?p=396359)
- [Desktop app frameworks 2026 comparison, May 2026](https://www.youngju.dev/blog/culture/2026-05-14-desktop-app-frameworks-2026-tauri-electron-wails-compose-multiplatform-maui-flutter-comparison-deep-dive-2026.en)
- [Tauri vs Electron vs SwiftUI for macOS, Jan 2026](https://jlw-newsletter.pages.dev/jlw-2026-01-31-desktop-frameworks.html)
- [Typer on PyPI — 0.27.3 resolved with uv, Nov 2026](https://pypi.org/project/typer/)
- [Fedora python-mutagen 1.48.1, Jun 2026](https://packages.fedoraproject.org/pkgs/python-mutagen/python3-mutagen/fedora-45.html)
- [Getting started with uv, 2026](https://www.bitdoze.com/uv-get-start/)
- [MusicBrainz Picard — ID3 compatibility options](https://picard-docs.musicbrainz.org/en/config/options_tags_compatibility_id3.html)
