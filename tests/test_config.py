import json
from pathlib import Path

from discord_cli.config import load_config, save_config


def test_save_config_writes_json_with_restricted_permissions(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    save_config(token="test-token-123", username="testuser", config_path=config_path)

    assert config_path.exists()
    assert oct(config_path.stat().st_mode & 0o777) == "0o600"
    data = json.loads(config_path.read_text())
    assert data == {"token": "test-token-123", "username": "testuser"}


def test_load_config_returns_saved_data(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    save_config(token="tok", username="usr", config_path=config_path)
    result = load_config(config_path)
    assert result == {"token": "tok", "username": "usr"}


def test_save_config_rotates_inode_on_overwrite(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}")
    config_path.chmod(0o644)
    old_inode = config_path.stat().st_ino

    save_config(token="new-tok", username="u", config_path=config_path)

    assert oct(config_path.stat().st_mode & 0o777) == "0o600"
    assert json.loads(config_path.read_text())["token"] == "new-tok"
    assert config_path.stat().st_ino != old_inode


def test_load_config_returns_empty_dict_when_missing(tmp_path: Path) -> None:
    result = load_config(tmp_path / "nonexistent.json")
    assert result == {}
