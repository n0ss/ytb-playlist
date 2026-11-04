from pathlib import Path

import pytest

from ytb_playlist.config import Config, ConfigError, default_config_dir, load_config


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
