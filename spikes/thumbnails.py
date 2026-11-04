"""Spike: which thumbnails does YouTube offer, and what does yt-dlp save as JPEG?"""

import json

from _common import OUT, PLAYLIST, ytdlp
from PIL import Image

ITEMS = "1:3"
dest = OUT / "thumbs"
dest.mkdir(parents=True, exist_ok=True)

result = ytdlp("-J", "--playlist-items", ITEMS, PLAYLIST)
result.check_returncode()
for entry in json.loads(result.stdout)["entries"]:
    thumbs = entry["thumbnails"]
    sized = [t for t in thumbs if t.get("width")]
    print(
        f"{entry['id']}: {len(thumbs)} listed, {len(sized)} with a size, chosen {entry['thumbnail']}"
    )
    for t in thumbs[-4:]:
        print(
            f"  {t.get('id')} pref={t.get('preference')} {t.get('width')}x{t.get('height')} {t['url']}"
        )

result = ytdlp(
    "--skip-download",
    "--write-thumbnail",
    "--convert-thumbnails", "jpg",
    "--playlist-items", ITEMS,
    "-o", str(dest / "%(id)s.%(ext)s"),
    PLAYLIST,
)  # fmt: skip
print("save exit code:", result.returncode)
for path in sorted(dest.iterdir()):
    with Image.open(path) as image:
        print(f"{path.name}: {image.format} {image.size} {image.mode} {path.stat().st_size} bytes")
