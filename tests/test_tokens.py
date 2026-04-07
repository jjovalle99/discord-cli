from pathlib import Path

import pytest

from discord_cli.tokens import resolve_token


def test_resolve_token_prefers_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    result = resolve_token(flag_token="flag-tok", config_path=tmp_path / "nope.json")
    assert result == "flag-tok"


def test_resolve_token_falls_back_to_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "env-tok")
    result = resolve_token(flag_token=None, config_path=tmp_path / "nope.json")
    assert result == "env-tok"


def test_resolve_token_falls_back_to_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from discord_cli.config import save_config

    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    config_path = tmp_path / "config.json"
    save_config(token="cfg-tok", username="u", config_path=config_path)
    result = resolve_token(flag_token=None, config_path=config_path)
    assert result == "cfg-tok"


def test_resolve_token_raises_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        resolve_token(flag_token=None, config_path=tmp_path / "nope.json")
