# Changelog

## 2026-11-04
- Project bootstrapped: full profile, Python 3.14 + uv + Typer CLI on the Homebrew yt-dlp, base skills only. See [decision 1](docs/tech-decisions.md).
- Plan reviewed and moved to `docs/plan.md`. See decisions [2](docs/tech-decisions.md) to [14](docs/tech-decisions.md).
- Phase 0: uv project on Python 3.14, runtime and development dependencies, pytest and ruff configured. Security check in [decision 15](docs/tech-decisions.md), install method in [decision 16](docs/tech-decisions.md).
- Project renamed `ytb-playlist`. See [decision 17](docs/tech-decisions.md).
- Phase 1a: tool spikes in `spikes/` for thumbnails, clipped download, progress and failures. See decisions [18](docs/tech-decisions.md), [19](docs/tech-decisions.md) and [20](docs/tech-decisions.md).
- Phase 1b: Music.app import checked by the owner; ID3v2.3 kept and the MP4 media kind dropped. See [decision 21](docs/tech-decisions.md).
