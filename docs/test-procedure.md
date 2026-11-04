# Test procedure

## Automated
```bash
uv run pytest -q              # offline: unit and component tests from recorded fixtures
uv run ruff check
uv run pytest -m network -q   # opt-in: run before merging fetch or sync work, and after each yt-dlp upgrade
```

The network test uses the first 3 items of the test playlist, clipped to about 60 seconds. It records the last yt-dlp version it passed.
