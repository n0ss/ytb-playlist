# Exit codes

| Code | Meaning | Examples |
| --- | --- | --- |
| 0 | Success | Everything saved, or nothing new; permanent failures alone don't change this |
| 1 | Partial | A temporary failure, a failed tag, or a bad file among several |
| 2 | Usage error | Bad URL or flag, invalid config, a format change, two folders for one playlist, damaged state |
| 3 | Machine not ready | Missing tool, unusable output folder, full disk |
| 4 | Network or extractor error | The playlist couldn't be read, or yt-dlp stopped unexpectedly |

With several URLs, or `sync --all`, every playlist still runs and the highest code wins. Interrupting a run with Ctrl-C exits with a non-zero code and leaves partial files in `tmp/` for the next run.
