import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from discord_cli.auth.command import run_auth


@pytest.mark.asyncio
async def test_run_auth_extracts_validates_and_saves(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"

    def mock_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"id": "123", "username": "alice", "global_name": "Alice"}
        )

    transport = httpx.MockTransport(mock_handler)

    with (
        patch(
            "discord_cli.auth.command.extract_token_from_leveldb",
            return_value="plain-token",
        ),
        patch(
            "discord_cli.auth.command.DISCORD_LEVELDB_PATHS",
            {"Darwin": tmp_path / "leveldb"},
        ),
        patch("discord_cli.auth.command.store_token", return_value=False),
    ):
        (tmp_path / "leveldb").mkdir()

        await run_auth(config_path=config_path, is_macos=True, transport=transport)

    config = json.loads(config_path.read_text())
    assert config["token"] == "plain-token"
    assert config["username"] == "alice"


@pytest.mark.asyncio
async def test_run_auth_raises_when_no_token_found(tmp_path: Path) -> None:
    with (
        patch(
            "discord_cli.auth.command.extract_token_from_leveldb",
            return_value=None,
        ),
        patch(
            "discord_cli.auth.command.DISCORD_LEVELDB_PATHS",
            {"Darwin": tmp_path / "leveldb"},
        ),
    ):
        (tmp_path / "leveldb").mkdir()

        from discord_cli.auth.errors import AuthError

        with pytest.raises(AuthError, match="No token found"):
            await run_auth(config_path=tmp_path / "config.json", is_macos=True)


@pytest.mark.asyncio
async def test_run_auth_stores_token_in_keyring_and_excludes_from_config(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"

    def mock_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"id": "123", "username": "alice", "global_name": "Alice"}
        )

    transport = httpx.MockTransport(mock_handler)

    with (
        patch(
            "discord_cli.auth.command.extract_token_from_leveldb",
            return_value="plain-token",
        ),
        patch(
            "discord_cli.auth.command.DISCORD_LEVELDB_PATHS",
            {"Darwin": tmp_path / "leveldb"},
        ),
        patch("discord_cli.auth.command.store_token", return_value=True) as mock_store,
    ):
        (tmp_path / "leveldb").mkdir()
        await run_auth(config_path=config_path, is_macos=True, transport=transport)

    mock_store.assert_called_once_with("plain-token")
    config = json.loads(config_path.read_text())
    assert "token" not in config
    assert config["username"] == "alice"


@pytest.mark.asyncio
async def test_run_auth_falls_back_to_plaintext_with_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"

    def mock_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"id": "123", "username": "alice", "global_name": "Alice"}
        )

    transport = httpx.MockTransport(mock_handler)

    with (
        patch(
            "discord_cli.auth.command.extract_token_from_leveldb",
            return_value="plain-token",
        ),
        patch(
            "discord_cli.auth.command.DISCORD_LEVELDB_PATHS",
            {"Darwin": tmp_path / "leveldb"},
        ),
        patch("discord_cli.auth.command.store_token", return_value=False),
    ):
        (tmp_path / "leveldb").mkdir()
        await run_auth(config_path=config_path, is_macos=True, transport=transport)

    config = json.loads(config_path.read_text())
    assert config["token"] == "plain-token"
    stderr = capsys.readouterr().err
    assert "plaintext" in stderr.lower() or "no system keyring" in stderr.lower()


@pytest.mark.asyncio
async def test_run_auth_quiet_suppresses_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"

    def mock_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"id": "123", "username": "alice", "global_name": "Alice"}
        )

    transport = httpx.MockTransport(mock_handler)

    with (
        patch(
            "discord_cli.auth.command.extract_token_from_leveldb",
            return_value="plain-token",
        ),
        patch(
            "discord_cli.auth.command.DISCORD_LEVELDB_PATHS",
            {"Darwin": tmp_path / "leveldb"},
        ),
        patch("discord_cli.auth.command.store_token", return_value=False),
    ):
        (tmp_path / "leveldb").mkdir()
        await run_auth(
            config_path=config_path, is_macos=True, transport=transport, quiet=True
        )

    stderr = capsys.readouterr().err
    assert stderr == ""
