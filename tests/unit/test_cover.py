# SPDX-License-Identifier: GPL-3.0-only
import io
import os
from pathlib import Path

import pytest
from PIL import Image

from ytb_playlist import cover
from ytb_playlist.cover import CoverError, square_cover, wide_cover


def write_image(path: Path, size: tuple[int, int], mode: str = "RGB", **options: object) -> Path:
    Image.new(mode, size, "red" if mode == "RGB" else (255, 0, 0, 128)).save(path, **options)
    return path


def write_noise(path: Path, size: tuple[int, int]) -> Path:
    raw = os.urandom(size[0] * size[1] * 3)
    Image.frombytes("RGB", size, raw).save(path, "PNG")
    return path


def read(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ((1920, 1080), (1000, 1000)),
        ((1280, 720), (720, 720)),
        ((480, 360), (360, 360)),
        ((336, 188), (188, 188)),
        ((720, 1280), (720, 720)),
    ],
)
def test_square_cover_crops_caps_and_never_upscales(
    tmp_path: Path, size: tuple[int, int], expected: tuple[int, int]
) -> None:
    source = write_image(tmp_path / "t.jpg", size)
    result = square_cover(source)
    assert read(result.data).size == expected
    assert read(result.data).format == "JPEG"


def test_square_crop_is_centred(tmp_path: Path) -> None:
    image = Image.new("RGB", (300, 100), "black")
    image.paste("white", (100, 0, 200, 100))
    source = tmp_path / "t.png"
    image.save(source)
    cropped = read(square_cover(source).data).convert("L")
    assert cropped.getpixel((5, 50)) > 240
    assert cropped.getpixel((94, 50)) > 240


@pytest.mark.parametrize("size", [(1920, 1080), (1280, 720), (480, 360)])
def test_wide_cover_keeps_the_source_size(tmp_path: Path, size: tuple[int, int]) -> None:
    source = write_image(tmp_path / "t.jpg", size)
    assert read(wide_cover(source).data).size == size


def test_webp_source_becomes_jpeg(tmp_path: Path) -> None:
    source = write_image(tmp_path / "t.webp", (640, 360))
    assert read(square_cover(source).data).format == "JPEG"


def test_transparent_source_becomes_rgb(tmp_path: Path) -> None:
    source = write_image(tmp_path / "t.png", (100, 100), "RGBA")
    assert read(square_cover(source).data).mode == "RGB"


def test_exif_is_stripped(tmp_path: Path) -> None:
    exif = Image.Exif()
    exif[0x010E] = "tracked"
    source = write_image(tmp_path / "t.jpg", (100, 100), exif=exif)
    assert dict(Image.open(source).getexif())
    assert dict(read(square_cover(source).data).getexif()) == {}


def test_small_cover_uses_the_top_quality(tmp_path: Path) -> None:
    result = square_cover(write_image(tmp_path / "t.jpg", (100, 100)))
    assert result.quality == 90
    assert not result.over_budget


def test_quality_steps_down_until_it_fits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = write_noise(tmp_path / "t.png", (300, 300))
    high = len(wide_cover(source).data)
    low = io.BytesIO()
    Image.open(source).convert("RGB").save(low, "JPEG", quality=75)
    monkeypatch.setattr(cover, "MAX_COVER_BYTES", (high + low.tell()) // 2)
    result = wide_cover(source)
    assert 75 <= result.quality < 90
    assert len(result.data) <= cover.MAX_COVER_BYTES
    assert not result.over_budget


def test_over_budget_cover_keeps_the_lowest_quality_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cover, "MAX_COVER_BYTES", 10)
    result = wide_cover(write_image(tmp_path / "t.jpg", (100, 100)))
    assert result.quality == 75
    assert result.over_budget


@pytest.mark.parametrize("build", [square_cover, wide_cover])
def test_damaged_image_is_a_cover_error(tmp_path: Path, build) -> None:
    source = tmp_path / "t.jpg"
    source.write_bytes(b"not an image")
    with pytest.raises(CoverError):
        build(source)


def test_truncated_image_is_a_cover_error(tmp_path: Path) -> None:
    source = write_noise(tmp_path / "t.png", (200, 200))
    source.write_bytes(source.read_bytes()[:300])
    with pytest.raises(CoverError):
        square_cover(source)


def test_missing_image_is_a_cover_error(tmp_path: Path) -> None:
    with pytest.raises(CoverError):
        square_cover(tmp_path / "gone.jpg")


def test_oversized_image_is_a_cover_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = write_image(tmp_path / "t.png", (400, 400))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(CoverError):
        square_cover(source)
