import json

import httpx
import pytest

from discord_cli.client import DiscordClient
from discord_cli.commands.list import list_servers


@pytest.mark.asyncio
async def test_list_servers_emits_guild_data(
    capsys: pytest.CaptureFixture[str],
) -> None:
    guilds = [
        {
            "id": "111",
            "name": "Test Server",
            "icon": "abc",
            "owner": True,
            "approximate_member_count": 42,
            "approximate_presence_count": 10,
            "features": [],
        }
    ]

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=guilds)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await list_servers(client)

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["id"] == "111"
    assert output[0]["name"] == "Test Server"
    assert output[0]["approximate_member_count"] == 42
    assert "features" not in output[0]
    assert set(output[0].keys()) == {
        "id",
        "name",
        "icon",
        "owner",
        "approximate_member_count",
        "approximate_presence_count",
    }


@pytest.mark.asyncio
async def test_list_channels_emits_channel_data(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from discord_cli.commands.list import list_channels

    channels = [
        {
            "id": "222",
            "name": "general",
            "type": 0,
            "topic": "Welcome",
            "parent_id": None,
            "position": 0,
            "nsfw": False,
        }
    ]

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=channels)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await list_channels(client, guild_id="999")

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["name"] == "general"
    assert output[0]["type"] == 0
    assert output[0]["type_name"] == "text"
    assert set(output[0].keys()) == {
        "id",
        "name",
        "type",
        "type_name",
        "topic",
        "parent_id",
        "position",
        "nsfw",
    }


@pytest.mark.asyncio
async def test_list_dms_emits_dm_channels(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from discord_cli.commands.list import list_dms

    dms = [
        {
            "id": "333",
            "type": 1,
            "recipients": [{"id": "444", "username": "bob", "global_name": "Bob"}],
            "last_message_id": "555",
        }
    ]

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=dms)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await list_dms(client)

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["type"] == 1
    assert output[0]["type_name"] == "dm"
    assert output[0]["recipients"][0]["username"] == "bob"
    assert set(output[0].keys()) == {
        "id",
        "type",
        "type_name",
        "recipients",
        "last_message_id",
    }
