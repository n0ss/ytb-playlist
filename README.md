# ytb-playlist

`ytb-playlist` is a command-line tool that downloads YouTube playlists through [yt-dlp](https://github.com/yt-dlp/yt-dlp) as MP3 or MP4, into one folder per playlist, ready to import into Apple Music. Files are named by date, so Finder sorts them chronologically, and they're fully tagged with cover art.

Rerunning is safe: only new items download, and an interrupted download picks up where it stopped.

## Personal use only
This tool is for your own private use. YouTube's terms restrict downloading, and you're responsible for what you download and how you use it, including third-party content. It has no redistribution features.

## Prerequisites
macOS on Apple silicon is the tested platform. Python 3.14 is fetched by [uv](https://docs.astral.sh/uv/) as needed.

```bash
brew install yt-dlp deno ffmpeg uv
```

## Install
```bash
git clone https://github.com/n0ss/ytb-playlist.git
cd ytb-playlist
uv sync
uv run ytb-playlist doctor
```

`doctor` checks the tools, their versions and the output folder. The commands below use `uv run ytb-playlist` from this folder. To type `ytb-playlist` from anywhere instead:

```bash
uv tool install --editable .
```

## Usage
Replace `URL` with a playlist link. Files go to `~/Music/YouTube` unless you set `output_root` or pass `--out`.

```bash
uv run ytb-playlist info URL                         # title, ID and item count
uv run ytb-playlist fetch URL --format mp3 --dry-run # see what's new, write nothing
uv run ytb-playlist fetch URL --format mp3 --items 1:3
```

To keep a playlist up to date, save it once and sync it from then on:

```bash
uv run ytb-playlist playlist add URL --format mp3 --name Show
uv run ytb-playlist sync Show --dry-run
uv run ytb-playlist sync Show
uv run ytb-playlist sync --all
```

MP4 is H.264 and AAC, capped at 1080p. On long videos that adds up: about 1.5 GB per 100 minutes at 1080p. Use `--max-height 720`, or MP3, to save space. Check with `--dry-run` before a first sync.

For files already in a playlist folder, nothing needs downloading:

```bash
uv run ytb-playlist tag PATH            # write tags and the cover again
uv run ytb-playlist cover PATH          # embed the saved thumbnail again
uv run ytb-playlist rename PATH --dry-run
```

## Documentation
- `docs/reference/cli.md`: every command and flag, generated from the code
- `docs/reference/config.md`: settings, environment variables, saved playlists
- `docs/reference/naming.md`: file and folder names
- `docs/reference/tags.md`: tags and cover art
- `docs/reference/exit-codes.md`
- `docs/how-to/troubleshoot-youtube-errors.md`
- `docs/tech-decisions.md`: every decision, with its reason
- `docs/plan.md`: the original plan and phases

## Development
```bash
uv run pytest -q              # offline tests
uv run pytest -m network -q   # opt-in, uses a public test playlist
uv run ruff check
uv run ruff format
```

See `docs/test-procedure.md`.

Run yt-dlp with argument lists only, and treat `.info.json` content as untrusted. See `CLAUDE.md`.

## Structure
```
src/ytb_playlist/
  core/       fetch engine, state, saved playlists, typed events
  cli/        Typer commands, rendered with Rich
  backends/   runs yt-dlp as a subprocess
  tagging/    tag mapping, and MP3 and MP4 writers
  naming.py   urls.py   cover.py   config.py   deps.py
tests/
  unit/  component/  network/  fixtures/
docs/
```

## Technologies
- yt-dlp: https://github.com/yt-dlp/yt-dlp
- uv: https://docs.astral.sh/uv/
- Typer: https://typer.tiangolo.com/
- Rich: https://rich.readthedocs.io/
- mutagen: https://mutagen.readthedocs.io/
- Pillow: https://pillow.readthedocs.io/
- pytest: https://docs.pytest.org/
- ruff: https://docs.astral.sh/ruff/

## Claude Code setup
- Base set (user scope): superpowers, task-observer, hookify, security-guidance, claude-md-management, context7, project-bootstrap, thermo-nuclear-code-quality-review
- Project plugins and skills: none

## License
GNU General Public License v3.0 only. See `LICENSE`. Source files carry an SPDX identifier.
