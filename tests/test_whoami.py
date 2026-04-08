import json

import httpx
import pytest

from discord_cli.client import DiscordClient
from discord_cli.commands.whoami import whoami


@pytest.mark.asyncio
async def test_whoami_returns_user_info_with_source(
    capsys: pytest.CaptureFixture[str],
) -> None:
    user_data = {
        "id": "123456789012345678",
        "username": "testuser",
        "global_name": "Test User",
        "discriminator": "0",
        "avatar": "abc123",
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=user_data)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await whoami(client, token_source="config_file")

    output = json.loads(capsys.readouterr().out)
    assert output == {
        "id": "123456789012345678",
        "username": "testuser",
        "global_name": "Test User",
        "token_source": "config_file",
        "token_valid": True,
    }


def test_whoami_invalid_token_includes_source(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from discord_cli.cli import whoami as whoami_cmd

    transport = httpx.MockTransport(
        lambda _: httpx.Response(401, json={"message": "401: Unauthorized", "code": 0})
    )

    monkeypatch.setenv("DISCORD_TOKEN", "bad-token")

    with pytest.raises(SystemExit) as exc_info:
        whoami_cmd(token=None, transport=transport)

    assert exc_info.value.code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["token_valid"] is False
    assert output["token_source"] == "environment_variable"


@pytest.mark.asyncio
async def test_whoami_single_api_call(
    capsys: pytest.CaptureFixture[str],
) -> None:
    call_count = 0
    user_data = {
        "id": "123",
        "username": "u",
        "global_name": "U",
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=user_data)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await whoami(client, token_source="flag")

    assert call_count == 1
