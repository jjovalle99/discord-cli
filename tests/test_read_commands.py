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
async def test_read_channel_skip_system_filters_system_types(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": "5",
            "author": {"id": "u1", "username": "alice"},
            "content": "hello",
            "type": 0,
        },
        {
            "id": "4",
            "author": {"id": "u2", "username": "bob"},
            "content": "",
            "type": 7,
        },
        {
            "id": "3",
            "author": {"id": "u3", "username": "carol"},
            "content": "",
            "type": 6,
        },
        {
            "id": "2",
            "author": {"id": "u1", "username": "alice"},
            "content": "reply",
            "type": 19,
        },
        {
            "id": "1",
            "author": {"id": "u4", "username": "dave"},
            "content": "ctx cmd",
            "type": 23,
        },
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", skip_system=True)

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 3
    assert output[0]["type"] == 0
    assert output[1]["type"] == 19
    assert output[2]["type"] == 23


@pytest.mark.asyncio
async def test_read_channel_skip_system_paginates_to_fill_limit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    page1 = [
        {
            "id": str(i),
            "author": {"id": "u1", "username": "x"},
            "content": "",
            "type": 7,
        }
        for i in range(100, 0, -1)
    ]
    page1[0] = {
        "id": "100",
        "author": {"id": "u1", "username": "x"},
        "content": "real",
        "type": 0,
    }

    page2 = [
        {
            "id": str(i),
            "author": {"id": "u1", "username": "x"},
            "content": f"msg{i}",
            "type": 0,
        }
        for i in range(200, 100, -1)
    ]

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
        await read_channel(client, channel_id="999", limit=5, skip_system=True)

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 5
    assert all(m["type"] == 0 for m in output)
    assert call_count == 2


@pytest.mark.asyncio
async def test_read_channel_skip_system_combined_with_author(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": "5",
            "author": {"id": "u1", "username": "alice"},
            "content": "hello",
            "type": 0,
        },
        {
            "id": "4",
            "author": {"id": "u2", "username": "bob"},
            "content": "",
            "type": 7,
        },
        {
            "id": "3",
            "author": {"id": "u1", "username": "alice"},
            "content": "",
            "type": 6,
        },
        {
            "id": "2",
            "author": {"id": "u2", "username": "bob"},
            "content": "bob msg",
            "type": 0,
        },
        {
            "id": "1",
            "author": {"id": "u1", "username": "alice"},
            "content": "reply",
            "type": 19,
        },
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", author="u1", skip_system=True)

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 2
    assert all(m["author"]["id"] == "u1" for m in output)
    assert output[0]["type"] == 0
    assert output[1]["type"] == 19


@pytest.mark.asyncio
async def test_read_channel_skip_system_not_capped_at_author_scan_cap(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from discord_cli.commands.read import _AUTHOR_SCAN_CAP

    pages_needed = _AUTHOR_SCAN_CAP // 100
    beyond_cap = pages_needed + 2
    call_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count > beyond_cap:
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(call_count * 100 + i),
                    "author": {"id": "u1", "username": "x"},
                    "content": "",
                    "type": 7,
                }
                for i in range(100, 0, -1)
            ],
        )

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", limit=10, skip_system=True)

    json.loads(capsys.readouterr().out)
    assert call_count > pages_needed


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


@pytest.mark.asyncio
async def test_read_channel_resolve_channels_adds_channel_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    channel_info = {"id": "999", "name": "general", "guild_id": "111", "type": 0}
    guild_channels = [
        {"id": "999", "name": "general", "type": 0},
        {"id": "888", "name": "random", "type": 0},
    ]
    messages = [
        {
            "id": "100",
            "channel_id": "999",
            "author": {"id": "1", "username": "alice"},
            "content": "hello",
            "type": 0,
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v10/channels/999/messages":
            return httpx.Response(200, json=messages)
        if path == "/api/v10/channels/999":
            return httpx.Response(200, json=channel_info)
        if path == "/api/v10/guilds/111/channels":
            return httpx.Response(200, json=guild_channels)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", resolve_channels=True)

    output = json.loads(capsys.readouterr().out)
    assert output[0]["channel_name"] == "general"


@pytest.mark.asyncio
async def test_read_channel_resolve_channels_replaces_mentions_in_content(
    capsys: pytest.CaptureFixture[str],
) -> None:
    channel_info = {"id": "999", "name": "general", "guild_id": "111", "type": 0}
    guild_channels = [
        {"id": "999", "name": "general", "type": 0},
        {"id": "888", "name": "resources", "type": 0},
    ]
    messages = [
        {
            "id": "100",
            "channel_id": "999",
            "author": {"id": "1", "username": "alice"},
            "content": "Check <#888> for info and <#777> for unknown",
            "type": 0,
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v10/channels/999/messages":
            return httpx.Response(200, json=messages)
        if path == "/api/v10/channels/999":
            return httpx.Response(200, json=channel_info)
        if path == "/api/v10/guilds/111/channels":
            return httpx.Response(200, json=guild_channels)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", resolve_channels=True)

    output = json.loads(capsys.readouterr().out)
    assert output[0]["content"] == "Check #resources for info and <#777> for unknown"


@pytest.mark.asyncio
async def test_read_channel_resolve_channels_dm_skips_resolution(
    capsys: pytest.CaptureFixture[str],
) -> None:
    channel_info = {
        "id": "999",
        "type": 1,
        "recipients": [{"id": "2", "username": "bob"}],
    }
    messages = [
        {
            "id": "100",
            "channel_id": "999",
            "author": {"id": "1", "username": "alice"},
            "content": "Check <#888> for info",
            "type": 0,
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v10/channels/999/messages":
            return httpx.Response(200, json=messages)
        if path == "/api/v10/channels/999":
            return httpx.Response(200, json=channel_info)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", resolve_channels=True)

    output = json.loads(capsys.readouterr().out)
    assert "channel_name" not in output[0]
    assert output[0]["content"] == "Check <#888> for info"


@pytest.mark.asyncio
async def test_read_channel_resolve_channels_seeds_map_from_channel_info(
    capsys: pytest.CaptureFixture[str],
) -> None:
    channel_info = {
        "id": "999",
        "name": "my-thread",
        "guild_id": "111",
        "type": 11,
    }
    guild_channels = [
        {"id": "888", "name": "resources", "type": 0},
    ]
    messages = [
        {
            "id": "100",
            "channel_id": "999",
            "author": {"id": "1", "username": "alice"},
            "content": "hello <#999>",
            "type": 0,
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v10/channels/999/messages":
            return httpx.Response(200, json=messages)
        if path == "/api/v10/channels/999":
            return httpx.Response(200, json=channel_info)
        if path == "/api/v10/guilds/111/channels":
            return httpx.Response(200, json=guild_channels)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", resolve_channels=True)

    output = json.loads(capsys.readouterr().out)
    assert output[0]["channel_name"] == "my-thread"
    assert output[0]["content"] == "hello #my-thread"


@pytest.mark.asyncio
async def test_read_channel_resolve_channels_degrades_on_api_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": "100",
            "channel_id": "999",
            "author": {"id": "1", "username": "alice"},
            "content": "Check <#888> for info",
            "type": 0,
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v10/channels/999/messages":
            return httpx.Response(200, json=messages)
        if path == "/api/v10/channels/999":
            return httpx.Response(403, json={"message": "Missing Access"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", resolve_channels=True)

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert "channel_name" not in output[0]
    assert output[0]["content"] == "Check <#888> for info"


@pytest.mark.asyncio
async def test_read_channel_max_bytes_truncates_older_messages(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": str(i),
            "author": {"id": "1", "username": "alice"},
            "content": f"message number {i}",
            "type": 0,
        }
        for i in range(10, 0, -1)
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", limit=10, max_bytes=500)

    captured = capsys.readouterr()
    assert len(captured.out.encode()) <= 500
    output = json.loads(captured.out)
    assert output["truncated"] is True
    assert output["messages_available"] == 10
    assert output["messages_returned"] < 10
    assert len(output["messages"]) == output["messages_returned"]


@pytest.mark.asyncio
async def test_read_channel_max_bytes_no_envelope_when_fits(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": "1",
            "author": {"id": "1", "username": "alice"},
            "content": "hi",
            "type": 0,
        }
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", limit=10, max_bytes=50000)

    output = json.loads(capsys.readouterr().out)
    assert isinstance(output, list)
    assert len(output) == 1
    assert output[0]["content"] == "hi"


@pytest.mark.asyncio
async def test_read_channel_max_bytes_with_compact(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": str(i),
            "author": {
                "id": "1",
                "username": "alice",
                "global_name": "Alice",
                "avatar": "abc123",
                "discriminator": "0",
            },
            "content": f"message number {i}",
            "edited_timestamp": None,
            "type": 0,
            "pinned": False,
            "thread": None,
        }
        for i in range(10, 0, -1)
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(
            client, channel_id="999", limit=10, compact=True, max_bytes=500
        )

    captured = capsys.readouterr()
    assert len(captured.out.encode()) <= 500
    output = json.loads(captured.out)
    assert output["truncated"] is True
    for msg in output["messages"]:
        assert "edited_timestamp" not in msg
        assert "thread" not in msg
        assert "avatar" not in msg.get("author", {})


@pytest.mark.asyncio
async def test_read_channel_pinned_calls_pins_endpoint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    pinned_messages = [
        {
            "id": "200",
            "author": {"id": "1", "username": "alice"},
            "content": "important announcement",
            "type": 0,
            "pinned": True,
        },
        {
            "id": "100",
            "author": {"id": "2", "username": "bob"},
            "content": "server rules",
            "type": 0,
            "pinned": True,
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v10/channels/999/pins":
            return httpx.Response(200, json=pinned_messages)
        if "/messages" in request.url.path:
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", pinned=True)

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 2
    assert output[0]["content"] == "important announcement"
    assert output[1]["content"] == "server rules"


@pytest.mark.asyncio
async def test_read_channel_pinned_rejects_incompatible_filters(
    capsys: pytest.CaptureFixture[str],
) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=[]))
    async with DiscordClient(token="t", transport=transport) as client:
        with pytest.raises(SystemExit, match="1"):
            await read_channel(client, channel_id="999", pinned=True, author="u1")

    err = json.loads(capsys.readouterr().err)
    assert err["error"] == "incompatible_flags"


@pytest.mark.asyncio
async def test_read_channel_pinned_rejects_skip_system(
    capsys: pytest.CaptureFixture[str],
) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=[]))
    async with DiscordClient(token="t", transport=transport) as client:
        with pytest.raises(SystemExit, match="1"):
            await read_channel(client, channel_id="999", pinned=True, skip_system=True)

    err = json.loads(capsys.readouterr().err)
    assert err["error"] == "incompatible_flags"


@pytest.mark.asyncio
async def test_read_channel_before_passes_cursor_to_api(
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_params: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_params.append(dict(request.url.params))
        return httpx.Response(
            200,
            json=[
                {"id": "99", "author": {"id": "1", "username": "a"}, "content": "old"},
            ],
        )

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", limit=5, before="200")

    assert captured_params[0]["before"] == "200"
    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["id"] == "99"


@pytest.mark.asyncio
async def test_read_channel_after_paginates_forward(
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_params: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_params.append(dict(request.url.params))
        params = request.url.params
        if "after" in params and params["after"] == "100":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": str(i),
                        "author": {"id": "1", "username": "a"},
                        "content": f"p1-{i}",
                    }
                    for i in range(101, 201)
                ],
            )
        if "after" in params and params["after"] == "200":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "201",
                        "author": {"id": "1", "username": "a"},
                        "content": "last",
                    },
                ],
            )
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", limit=150, after="100")

    assert captured_params[0]["after"] == "100"
    assert captured_params[1]["after"] == "200"
    output = json.loads(capsys.readouterr().out)
    assert len(output) == 101


@pytest.mark.asyncio
async def test_read_channel_before_and_after_mutually_exclusive(
    capsys: pytest.CaptureFixture[str],
) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=[]))
    async with DiscordClient(token="t", transport=transport) as client:
        with pytest.raises(SystemExit, match="1"):
            await read_channel(client, channel_id="999", before="200", after="100")

    err = json.loads(capsys.readouterr().err)
    assert err["error"] == "incompatible_flags"


@pytest.mark.asyncio
async def test_read_channel_pinned_rejects_before(
    capsys: pytest.CaptureFixture[str],
) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=[]))
    async with DiscordClient(token="t", transport=transport) as client:
        with pytest.raises(SystemExit, match="1"):
            await read_channel(client, channel_id="999", pinned=True, before="200")

    err = json.loads(capsys.readouterr().err)
    assert err["error"] == "incompatible_flags"


@pytest.mark.asyncio
async def test_read_channel_after_handles_newest_first_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_params: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_params.append(dict(request.url.params))
        params = request.url.params
        if params.get("after") == "100":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": str(i),
                        "author": {"id": "1", "username": "a"},
                        "content": f"msg{i}",
                    }
                    for i in range(200, 100, -1)
                ],
            )
        if params.get("after") == "200":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "201",
                        "author": {"id": "1", "username": "a"},
                        "content": "last",
                    },
                ],
            )
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", limit=150, after="100")

    assert captured_params[0]["after"] == "100"
    assert captured_params[1]["after"] == "200"
    output = json.loads(capsys.readouterr().out)
    assert len(output) == 101
    ids = [m["id"] for m in output]
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_read_channel_max_bytes_too_small_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": "1",
            "author": {"id": "1", "username": "alice"},
            "content": "hi",
            "type": 0,
        }
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        with pytest.raises(SystemExit, match="1"):
            await read_channel(client, channel_id="999", limit=10, max_bytes=10)

    err = json.loads(capsys.readouterr().err)
    assert err["error"] == "max_bytes_too_small"


@pytest.mark.asyncio
async def test_read_channel_resolve_mentions_replaces_known_and_preserves_unknown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": "1",
            "author": {"id": "10", "username": "sender"},
            "content": "Hello <@200> and <@999>!",
            "type": 0,
            "mentions": [
                {"id": "200", "username": "alice", "global_name": "Alice A"},
            ],
        }
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", resolve_mentions=True)

    output = json.loads(capsys.readouterr().out)
    assert output[0]["content"] == "Hello @alice and <@999>!"


@pytest.mark.asyncio
async def test_read_channel_resolve_mentions_handles_nick_prefix_format(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": "1",
            "author": {"id": "10", "username": "sender"},
            "content": "cc <@!300>",
            "type": 0,
            "mentions": [
                {"id": "300", "username": "bob", "global_name": "Bob B"},
            ],
        }
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", resolve_mentions=True)

    output = json.loads(capsys.readouterr().out)
    assert output[0]["content"] == "cc @bob"


@pytest.mark.asyncio
async def test_read_channel_resolve_mentions_preserves_code_spans(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = [
        {
            "id": "1",
            "author": {"id": "10", "username": "sender"},
            "content": "Hey <@200>, use `<@200>` to mention and ```<@200>``` in blocks",
            "type": 0,
            "mentions": [
                {"id": "200", "username": "alice", "global_name": "Alice"},
            ],
        }
    ]

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=messages))
    async with DiscordClient(token="t", transport=transport) as client:
        await read_channel(client, channel_id="999", resolve_mentions=True)

    output = json.loads(capsys.readouterr().out)
    assert (
        output[0]["content"]
        == "Hey @alice, use `<@200>` to mention and ```<@200>``` in blocks"
    )
