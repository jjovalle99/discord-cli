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


@pytest.mark.asyncio
async def test_read_channel_compact_strips_null_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": "100",
            "content": "hello",
            "timestamp": "2024-01-15T10:00:00+00:00",
            "edited_timestamp": None,
            "type": 0,
            "pinned": False,
            "thread": None,
            "referenced_message": None,
            "author": {"id": "1", "username": "alice", "global_name": "Alice"},
        }
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", compact=True)

    output = json.loads(capsys.readouterr().out)
    msg = output[0]
    assert "edited_timestamp" not in msg
    assert "thread" not in msg
    assert "referenced_message" in msg
    assert msg["referenced_message"] is None
    assert msg["content"] == "hello"
    assert msg["pinned"] is False
    assert msg["type"] == 0


@pytest.mark.asyncio
async def test_read_channel_compact_reduces_author(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": "100",
            "content": "hello",
            "author": {
                "id": "1",
                "username": "alice",
                "global_name": "Alice",
                "avatar": "abc123",
                "discriminator": "0",
                "public_flags": 0,
                "banner": None,
                "accent_color": None,
                "clan": None,
            },
        }
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", compact=True)

    output = json.loads(capsys.readouterr().out)
    author = output[0]["author"]
    assert author == {"id": "1", "username": "alice", "global_name": "Alice"}


@pytest.mark.asyncio
async def test_read_message_compact(capsys: pytest.CaptureFixture[str]) -> None:
    from discord_cli.commands.read import read_message

    msg = {
        "id": "100",
        "content": "hi",
        "edited_timestamp": None,
        "author": {
            "id": "1",
            "username": "alice",
            "global_name": "Alice",
            "avatar": "abc",
            "banner": None,
        },
    }

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=msg))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_message(client, channel_id="999", message_id="100", compact=True)

    output = json.loads(capsys.readouterr().out)
    assert "edited_timestamp" not in output
    assert output["author"] == {"id": "1", "username": "alice", "global_name": "Alice"}


@pytest.mark.asyncio
async def test_compact_preserves_bot_flag_in_author(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": "100",
            "content": "beep",
            "author": {
                "id": "1",
                "username": "bot-user",
                "global_name": None,
                "bot": True,
                "avatar": "abc",
                "discriminator": "0",
            },
        }
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", compact=True)

    output = json.loads(capsys.readouterr().out)
    author = output[0]["author"]
    assert author["bot"] is True
    assert "global_name" not in author
    assert "avatar" not in author
    assert "discriminator" not in author


@pytest.mark.asyncio
async def test_compact_does_not_synthesize_absent_global_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": "100",
            "content": "hi",
            "author": {"id": "1", "username": "alice"},
        }
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", compact=True)

    output = json.loads(capsys.readouterr().out)
    assert "global_name" not in output[0]["author"]


@pytest.mark.asyncio
async def test_compact_preserves_referenced_message_null(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": "100",
            "content": "replying to deleted",
            "referenced_message": None,
            "author": {"id": "1", "username": "alice"},
        }
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", compact=True)

    output = json.loads(capsys.readouterr().out)
    assert "referenced_message" in output[0]
    assert output[0]["referenced_message"] is None


@pytest.mark.asyncio
async def test_read_channel_author_filters_by_author_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {"id": "3", "author": {"id": "u1", "username": "alice"}, "content": "a1"},
        {"id": "2", "author": {"id": "u2", "username": "bob"}, "content": "b1"},
        {"id": "1", "author": {"id": "u1", "username": "alice"}, "content": "a2"},
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", author="u1")

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 2
    assert all(m["author"]["id"] == "u1" for m in output)


@pytest.mark.asyncio
async def test_read_channel_author_paginates_to_fill_limit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    page1 = [
        {"id": str(i), "author": {"id": "other", "username": "x"}, "content": f"p1-{i}"}
        for i in range(100, 0, -1)
    ]
    page1[50] = {
        "id": "50",
        "author": {"id": "target", "username": "t"},
        "content": "match1",
    }

    page2 = [
        {"id": str(i), "author": {"id": "other", "username": "x"}, "content": f"p2-{i}"}
        for i in range(200, 100, -1)
    ]
    page2[0] = {
        "id": "200",
        "author": {"id": "target", "username": "t"},
        "content": "match2",
    }

    call_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=page1)
        if call_count == 2:
            return httpx.Response(200, json=page2)
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", limit=2, author="target")

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 2
    assert all(m["author"]["id"] == "target" for m in output)
    assert call_count == 2


@pytest.mark.asyncio
async def test_read_channel_author_stops_at_scan_cap(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from discord_cli.commands.read import _AUTHOR_SCAN_CAP

    pages_needed = _AUTHOR_SCAN_CAP // 100

    call_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(call_count * 100 + i),
                    "author": {"id": "other", "username": "x"},
                    "content": "no",
                }
                for i in range(100, 0, -1)
            ],
        )

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", limit=10, author="missing")

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 0
    assert call_count == pages_needed
