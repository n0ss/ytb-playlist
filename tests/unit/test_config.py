# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path

import pytest

from ytb_playlist.config import Config, ConfigError, default_config_dir, load_config
from ytb_playlist.core.models import CoverSource


def write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def test_config_dir_is_application_support_on_macos(home: Path) -> None:
    assert default_config_dir() == home / "Library/Application Support/ytb-playlist"


def test_config_dir_follows_xdg_on_linux(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert default_config_dir() == tmp_path / "ytb-playlist"


def test_no_config_file_gives_the_defaults(home: Path) -> None:
    assert load_config() == Config(output_root=home / "Music/YouTube", binaries={})


def test_default_config_file_is_read(home: Path) -> None:
    default_config_dir().mkdir(parents=True)
    write(default_config_dir() / "config.toml", 'output_root = "/data/yt"\n')
    assert load_config().output_root == Path("/data/yt")


def test_explicit_file_replaces_the_default_file(home: Path, tmp_path: Path) -> None:
    default_config_dir().mkdir(parents=True)
    write(default_config_dir() / "config.toml", 'output_root = "/from/default"\n')
    explicit = write(tmp_path / "other.toml", 'output_root = "/from/explicit"\n')
    assert load_config(explicit).output_root == Path("/from/explicit")


def test_explicit_file_must_exist(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="missing.toml"):
        load_config(tmp_path / "missing.toml")


def test_output_root_expands_the_home_folder(home: Path, tmp_path: Path) -> None:
    path = write(tmp_path / "c.toml", 'output_root = "~/Videos"\n')
    assert load_config(path).output_root == home / "Videos"


def test_binary_paths_are_read(tmp_path: Path) -> None:
    path = write(tmp_path / "c.toml", '[binaries]\nyt-dlp = "/opt/custom/yt-dlp"\n')
    assert load_config(path).binaries == {"yt-dlp": Path("/opt/custom/yt-dlp")}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("output_root = [", "invalid TOML"),
        ("output_root = 3\n", "output_root"),
        ("[binaries]\nytdlp = '/x'\n", "ytdlp"),
        ("[binaries]\nyt-dlp = 'relative/path'\n", "absolute"),
        ("[binaries]\nyt-dlp = 3\n", "yt-dlp"),
        ("binaries = 'x'\n", "binaries"),
        ("output_root = 'Music'\n", "absolute"),
    ],
)
def test_invalid_config_is_rejected(tmp_path: Path, text: str, message: str) -> None:
    path = write(tmp_path / "c.toml", text)
    with pytest.raises(ConfigError, match=message):
        load_config(path)


def test_undecodable_config_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(path)


def test_defaults_for_the_new_settings(home: Path) -> None:
    config = load_config()
    assert (config.genre, config.cover, config.max_height) == ("YouTube", CoverSource.EPISODE, 1080)
    assert (config.sleep_min, config.sleep_max) == (3, 8)


def test_file_settings_are_read(tmp_path: Path) -> None:
    text = 'genre = "Radio"\ncover = "playlist"\nmax_height = 720\nsleep_min = 1\nsleep_max = 2\n'
    config = load_config(write(tmp_path / "c.toml", text))
    assert (config.genre, config.cover, config.max_height) == ("Radio", CoverSource.PLAYLIST, 720)
    assert (config.sleep_min, config.sleep_max) == (1, 2)


def test_environment_beats_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YTB_PLAYLIST_GENRE", "From env")
    monkeypatch.setenv("YTB_PLAYLIST_MAX_HEIGHT", "480")
    monkeypatch.setenv("YTB_PLAYLIST_OUTPUT_ROOT", "/from/env")
    path = write(tmp_path / "c.toml", 'genre = "From file"\nmax_height = 720\n')
    config = load_config(path)
    assert (config.genre, config.max_height) == ("From env", 480)
    assert config.output_root == Path("/from/env")


def test_file_beats_the_defaults_when_the_environment_is_silent(tmp_path: Path) -> None:
    assert load_config(write(tmp_path / "c.toml", 'genre = "From file"\n')).genre == "From file"


def test_empty_environment_value_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YTB_PLAYLIST_GENRE", "")
    assert load_config(write(tmp_path / "c.toml", 'genre = "File"\n')).genre == "File"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MAX_HEIGHT", "tall"),
        ("MAX_HEIGHT", "0"),
        ("SLEEP_MIN", "-1"),
        ("COVER", "square"),
        ("OUTPUT_ROOT", "relative"),
    ],
)
def test_invalid_environment_value_names_the_variable(
    home: Path, monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(f"YTB_PLAYLIST_{name}", value)
    with pytest.raises(ConfigError, match=name.lower()):
        load_config()


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("outptu_root = '/x'\n", "outptu_root"),
        ("max_height = 'tall'\n", "max_height"),
        ("max_height = true\n", "max_height"),
        ("max_height = 0\n", "max_height"),
        ("sleep_min = -1\n", "sleep_min"),
        ("sleep_min = 9\nsleep_max = 2\n", "sleep_min"),
        ("cover = 'square'\n", "cover"),
        ("genre = 3\n", "genre"),
    ],
)
def test_invalid_settings_are_rejected(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path / "c.toml", text))


def test_sleep_of_zero_is_kept(tmp_path: Path) -> None:
    path = write(tmp_path / "c.toml", "sleep_min = 0\nsleep_max = 0\n")
    assert (load_config(path).sleep_min, load_config(path).sleep_max) == (0, 0)
