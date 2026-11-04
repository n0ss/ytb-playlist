# ytb-playlist

`ytb-playlist` is a personal command-line tool that downloads YouTube playlists through yt-dlp into one folder per playlist, as MP3 or MP4, named by date and tagged for Apple Music import. It's in early development: the project is set up, and the features aren't built yet.

## Structure
```
CLAUDE.md             project instructions for Claude Code
PRODUCT.md            what the tool is for and its constraints
CHANGELOG.md
LICENSE               GNU GPL v3.0
pyproject.toml        uv project, dependencies, pytest and ruff settings
src/ytb_playlist/     the package
spikes/               throwaway experiments behind decisions 18 to 21
docs/
  plan.md             full plan and phases
  tech-decisions.md   every decision, with its reason
  test-procedure.md
tests/
  unit/  component/  network/  fixtures/
```

## Prerequisites
```bash
yt-dlp --version && ffmpeg -version | head -1 && deno --version
brew install yt-dlp deno ffmpeg uv   # whatever is missing
```

## Usage
```bash
uv run ytb-playlist doctor   # check yt-dlp, ffmpeg, deno and the output folder
uv run ytb-playlist info URL # playlist title, ID and item count
uv run ytb-playlist fetch URL --format mp3 --items 1:3 --dry-run
uv run ytb-playlist tag PATH    # write tags and cover from the saved metadata
uv run ytb-playlist cover PATH  # embed the saved thumbnail again
uv run ytb-playlist rename PATH --dry-run
uv run ytb-playlist playlist add URL --format mp3 --name Show
uv run ytb-playlist sync Show --dry-run   # or: sync --all
uv run ytb-playlist config show
``` The planned interface is in `docs/plan.md`.

## Tests
```bash
uv run pytest -q
```
See `docs/test-procedure.md`.

## Conventions applied
- User-level rules: python, shell, yaml (`~/.claude/rules/`)
- Project-specific rules: see `CLAUDE.md`

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
