import json
from pathlib import Path
from typing import Any

import httpx
import pytest


def _parse_json_stderr(raw: str) -> dict[str, Any]:
    for line in raw.strip().splitlines():
        if line.startswith("{"):
            return json.loads(line)  # type: ignore[no-any-return]
    msg = f"No JSON line found in stderr: {raw!r}"
    raise AssertionError(msg)


def test_api_error_emits_json_to_stderr(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from discord_cli.cli import _run

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Unknown Channel", "code": 10003})

    transport = httpx.MockTransport(handler)

    monkeypatch.setenv("DISCORD_TOKEN", "t")

    with pytest.raises(SystemExit) as exc_info:
        _run(
            lambda c: c.api_get("/channels/999"),
            token=None,
            transport=transport,
        )

    assert exc_info.value.code == 1
    err = _parse_json_stderr(capsys.readouterr().err)
    assert err["error"] == "discord_api_error"
    assert "Unknown Channel" in err["message"]


def test_timeout_error_emits_json_to_stderr(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from discord_cli.cli import _run

    async def _raise_timeout(_c: object) -> None:
        raise TimeoutError("Search index not ready after retries.")

    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200, json={"id": "1", "username": "a", "global_name": "A"}
        )
    )
    monkeypatch.setenv("DISCORD_TOKEN", "t")

    with pytest.raises(SystemExit) as exc_info:
        _run(_raise_timeout, token=None, transport=transport)

    assert exc_info.value.code == 1
    err = _parse_json_stderr(capsys.readouterr().err)
    assert err["error"] == "timeout"


def test_auth_decrypt_error_emits_json_to_stderr(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    from unittest.mock import patch

    from discord_cli.cli import auth

    with (
        patch(
            "discord_cli.auth.command.extract_token_from_leveldb",
            return_value="dQw4w9WgXcQ:bm90LXZhbGlk",
        ),
        patch(
            "discord_cli.auth.command.DISCORD_LEVELDB_PATHS",
            {"Darwin": tmp_path / "leveldb"},
        ),
        patch(
            "discord_cli.auth.command.get_macos_password",
            return_value="wrong-password",
        ),
    ):
        (tmp_path / "leveldb").mkdir()

        with pytest.raises(SystemExit) as exc_info:
            auth()

    assert exc_info.value.code == 1
    err = _parse_json_stderr(capsys.readouterr().err)
    assert err["error"] == "auth_error"


def test_auth_missing_leveldb_emits_json_to_stderr(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    from unittest.mock import patch

    from discord_cli.cli import auth

    with patch(
        "discord_cli.auth.command.DISCORD_LEVELDB_PATHS",
        {"Darwin": tmp_path / "nonexistent"},
    ):
        with pytest.raises(SystemExit) as exc_info:
            auth()

    assert exc_info.value.code == 1
    err = _parse_json_stderr(capsys.readouterr().err)
    assert err["error"] == "auth_error"
    assert "not found" in err["message"].lower()


def test_auth_missing_token_emits_json_to_stderr(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    from unittest.mock import patch

    from discord_cli.cli import auth

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

        with pytest.raises(SystemExit) as exc_info:
            auth()

    assert exc_info.value.code == 1
    err = _parse_json_stderr(capsys.readouterr().err)
    assert err["error"] == "auth_error"
    assert "no token" in err["message"].lower()
