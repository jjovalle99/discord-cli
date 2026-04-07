import json

import httpx
import pytest

from discord_cli.client import DiscordClient
from discord_cli.commands.read import (
    read_channel,
)


@pytest.mark.asyncio
async def test_read_channel_emits_messages(capsys: pytest.CaptureFixture[str]) -> None:
    messages = [
        {
            "id": "100",
            "author": {"id": "1", "username": "alice", "global_name": "Alice"},
            "content": "hello",
            "timestamp": "2024-01-15T10:00:00+00:00",
            "edited_timestamp": None,
            "type": 0,
            "pinned": False,
            "mentions": [],
            "attachments": [],
            "embeds": [],
        }
    ]

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=messages)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999")

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["content"] == "hello"
    assert output[0]["author"]["username"] == "alice"


@pytest.mark.asyncio
async def test_read_channel_paginates(capsys: pytest.CaptureFixture[str]) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                200,
                json=[{"id": str(i), "content": f"msg{i}"} for i in range(100, 0, -1)],
            )
        return httpx.Response(200, json=[{"id": "0", "content": "oldest"}])

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", limit=150)

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 101
    assert call_count == 2


@pytest.mark.asyncio
async def test_read_message_emits_single_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from discord_cli.commands.read import read_message

    msg = {"id": "100", "content": "hi", "author": {"id": "1", "username": "a"}}

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=msg))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_message(client, channel_id="999", message_id="100")

    assert json.loads(capsys.readouterr().out)["content"] == "hi"


@pytest.mark.asyncio
async def test_read_server_info_emits_guild(capsys: pytest.CaptureFixture[str]) -> None:
    from discord_cli.commands.read import read_server_info

    guild = {"id": "111", "name": "Test", "approximate_member_count": 42}

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=guild))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_server_info(client, guild_id="111")

    assert json.loads(capsys.readouterr().out)["name"] == "Test"


@pytest.mark.asyncio
async def test_read_channel_info_emits_channel(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from discord_cli.commands.read import read_channel_info

    ch = {"id": "222", "name": "general", "type": 0, "topic": "Welcome"}

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=ch))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel_info(client, channel_id="222")

    assert json.loads(capsys.readouterr().out)["topic"] == "Welcome"


@pytest.mark.asyncio
async def test_read_user_emits_user(capsys: pytest.CaptureFixture[str]) -> None:
    from discord_cli.commands.read import read_user

    user = {"id": "333", "username": "bob", "global_name": "Bob"}

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=user))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_user(client, user_id="333")

    assert json.loads(capsys.readouterr().out)["username"] == "bob"


@pytest.mark.asyncio
async def test_read_member_emits_member(capsys: pytest.CaptureFixture[str]) -> None:
    from discord_cli.commands.read import read_member

    member = {
        "user": {"id": "333", "username": "bob"},
        "nick": "Bobby",
        "roles": ["r1"],
        "joined_at": "2023-01-15T10:00:00+00:00",
    }

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=member))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_member(client, guild_id="111", user_id="333")

    assert json.loads(capsys.readouterr().out)["nick"] == "Bobby"
