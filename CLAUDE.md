# YouTube Playlist Archiver (`ytarchive`)

**Goal:** CLI (later GUI) that downloads YouTube playlists through yt-dlp into one folder per playlist, as MP3 or MP4, named by date and fully tagged for Apple Music import.
Product details: `PRODUCT.md`. Decisions: `docs/tech-decisions.md`. Tests: `docs/test-procedure.md`. Full plan: `docs/plan.md`.

## Target architecture
- `src/ytarchive/core/`: sync engine, models, typed events. GUI-agnostic: `sync(playlist, options, on_event)`.
- `src/ytarchive/cli/`: Typer app, renders events with Rich. Textual, then PySide6, come later as thin shells on the same events.
- `src/ytarchive/backends/ytdlp_proc.py`: runs the Homebrew `yt-dlp` as a subprocess. The `Backend` protocol exists only as the test seam.
- `urls.py`, `naming.py`, `cover.py`, `config.py`, `deps.py`, `tagging/`: pure or narrow modules.
- Downloads go to a temp folder as `%(id)s.%(ext)s`; `naming.py` sets the final name, then mutagen and Pillow tag from the saved `.info.json`.
- Per-playlist state lives in `<playlist>/.ytarchive/`. `archive.txt` owns "downloaded"; `state.json` owns "tagged" and failures.

## Commands
Not available until phase 0 creates the uv project.
```bash
uv run pytest -q              # offline tests
uv run pytest -m network -q   # opt-in, uses the test playlist
uv run ruff check
uv run ruff format
```

## Maintenance procedure
- yt-dlp, ffmpeg and deno are Homebrew system dependencies, not project dependencies. When YouTube breaks extraction: `brew upgrade yt-dlp`.
- After a yt-dlp upgrade, run the network test. It records the last version passed, and `doctor` flags any other installed version.
- Python dependencies: `uv lock --upgrade`, then the full test suite.

## Design references
- Current phase and phase plan: `docs/plan.md`, section "Research, development and testing plan".
- Filename, tag, format and cover rules: `docs/plan.md`. Why they are that way: `docs/tech-decisions.md`.

## Project-specific rules
- Git: local repository, commits authorised on the user's go-ahead, so `~/.claude/rules/version-control-fallback.md` does not apply here. One branch per phase, one commit per completed task. No remote until v0.1.0, then GitLab.
- Before merging a phase branch, suggest `/thermo-nuclear-code-quality-review` on the whole branch. Also suggest it before any commit that is non-trivial on its own.
- Run yt-dlp with argument lists only. Never pass video metadata into `--exec` or a shell string. Treat `.info.json` content as untrusted.
- Take titles and dates from per-item metadata, never from `--flat-playlist` listings.
- Never commit media files.
