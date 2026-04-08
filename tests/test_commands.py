import json

import httpx
import pytest

from discord_cli.client import DiscordClient
from discord_cli.commands.list import list_members, list_servers, list_threads


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


@pytest.mark.asyncio
async def test_list_members_resolves_role_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    roles = [
        {"id": "r1", "name": "Admin"},
        {"id": "r2", "name": "Participant"},
    ]
    members = [
        {
            "user": {"id": "u1", "username": "alice", "global_name": "Alice"},
            "nick": "Ali",
            "roles": ["r2"],
            "joined_at": "2024-01-01T00:00:00+00:00",
            "deaf": False,
            "mute": False,
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/roles"):
            return httpx.Response(200, json=roles)
        return httpx.Response(200, json=members)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await list_members(client, guild_id="111")

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["id"] == "u1"
    assert output[0]["username"] == "alice"
    assert output[0]["roles"] == ["Participant"]
    assert set(output[0].keys()) == {"id", "username", "roles"}


@pytest.mark.asyncio
async def test_list_members_role_filter(
    capsys: pytest.CaptureFixture[str],
) -> None:
    roles = [
        {"id": "r1", "name": "Admin"},
        {"id": "r2", "name": "Participant"},
    ]
    members = [
        {
            "user": {"id": "u1", "username": "alice"},
            "roles": ["r1"],
        },
        {
            "user": {"id": "u2", "username": "bob"},
            "roles": ["r2"],
        },
        {
            "user": {"id": "u3", "username": "carol"},
            "roles": ["r1", "r2"],
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/roles"):
            return httpx.Response(200, json=roles)
        return httpx.Response(200, json=members)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await list_members(client, guild_id="111", role="Admin")

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 2
    assert output[0]["username"] == "alice"
    assert output[1]["username"] == "carol"


@pytest.mark.asyncio
async def test_list_members_paginates_with_after_cursor(
    capsys: pytest.CaptureFixture[str],
) -> None:
    roles: list[dict[str, str]] = []
    page1 = [
        {"user": {"id": str(i), "username": f"u{i}"}, "roles": []} for i in range(1000)
    ]
    page2 = [{"user": {"id": "2000", "username": "last"}, "roles": []}]

    captured_params: list[dict[str, str]] = []
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        if request.url.path.endswith("/roles"):
            return httpx.Response(200, json=roles)
        call_count += 1
        captured_params.append(dict(request.url.params))
        if call_count == 1:
            return httpx.Response(200, json=page1)
        return httpx.Response(200, json=page2)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await list_members(client, guild_id="111", limit=1001)

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1001
    assert output[-1]["username"] == "last"
    assert captured_params[1]["after"] == "999"


@pytest.mark.asyncio
async def test_list_members_role_filter_scans_across_pages(
    capsys: pytest.CaptureFixture[str],
) -> None:
    roles = [{"id": "r1", "name": "Admin"}]
    page1 = [
        {"user": {"id": str(i), "username": f"u{i}"}, "roles": []} for i in range(1000)
    ]
    page2 = [{"user": {"id": "2000", "username": "target"}, "roles": ["r1"]}]

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        if request.url.path.endswith("/roles"):
            return httpx.Response(200, json=roles)
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=page1)
        return httpx.Response(200, json=page2)

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await list_members(client, guild_id="111", limit=1, role="Admin")

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["username"] == "target"


@pytest.mark.asyncio
async def test_list_threads_fetches_archived_and_shapes_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    public_threads = {
        "threads": [
            {
                "id": "t1",
                "name": "Public Thread",
                "type": 11,
                "guild_id": "g1",
                "parent_id": "c1",
                "message_count": 12,
                "member_count": 3,
                "thread_metadata": {"archived": True, "auto_archive_duration": 1440},
                "owner_id": "u1",
            }
        ],
        "members": [],
        "has_more": False,
    }
    private_threads = {
        "threads": [
            {
                "id": "t2",
                "name": "Private Thread",
                "type": 12,
                "guild_id": "g1",
                "parent_id": "c1",
                "message_count": 5,
                "member_count": 2,
                "thread_metadata": {"archived": True, "auto_archive_duration": 1440},
                "owner_id": "u2",
            }
        ],
        "members": [],
        "has_more": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "/threads/archived/public" in request.url.path:
            return httpx.Response(200, json=public_threads)
        if "/threads/archived/private" in request.url.path:
            return httpx.Response(200, json=private_threads)
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await list_threads(client, channel_id="c1")

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 2
    assert output[0]["id"] == "t1"
    assert output[0]["name"] == "Public Thread"
    assert output[0]["message_count"] == 12
    assert output[0]["archived"] is True
    assert output[1]["id"] == "t2"
    assert output[1]["archived"] is True
    assert "owner_id" not in output[0]
    assert "thread_metadata" not in output[0]
    assert "guild_id" not in output[0]
    assert set(output[0].keys()) == {"id", "name", "message_count", "archived"}


@pytest.mark.asyncio
async def test_list_threads_discovers_active_threads_from_messages(
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty_archived = {"threads": [], "members": [], "has_more": False}
    messages = [
        {
            "id": "m1",
            "content": "hello",
            "author": {"id": "u1"},
        },
        {
            "id": "m2",
            "content": "thread starter",
            "author": {"id": "u2"},
            "thread": {
                "id": "t1",
                "name": "Active Discussion",
                "type": 11,
                "message_count": 7,
                "thread_metadata": {"archived": False, "auto_archive_duration": 1440},
            },
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if "/threads/archived/" in request.url.path:
            return httpx.Response(200, json=empty_archived)
        if "/messages" in request.url.path:
            return httpx.Response(200, json=messages)
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await list_threads(client, channel_id="c1")

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["id"] == "t1"
    assert output[0]["name"] == "Active Discussion"
    assert output[0]["message_count"] == 7
    assert output[0]["archived"] is False


@pytest.mark.asyncio
async def test_list_threads_deduplicates_across_sources(
    capsys: pytest.CaptureFixture[str],
) -> None:
    archived = {
        "threads": [
            {
                "id": "t1",
                "name": "Shared Thread",
                "type": 11,
                "message_count": 10,
                "thread_metadata": {"archived": True},
            }
        ],
        "members": [],
        "has_more": False,
    }
    messages = [
        {
            "id": "m1",
            "content": "starter",
            "author": {"id": "u1"},
            "thread": {
                "id": "t1",
                "name": "Shared Thread",
                "type": 11,
                "message_count": 15,
                "thread_metadata": {"archived": False},
            },
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if "/threads/archived/" in request.url.path:
            return httpx.Response(200, json=archived)
        if "/messages" in request.url.path:
            return httpx.Response(200, json=messages)
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await list_threads(client, channel_id="c1")

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["id"] == "t1"
    assert output[0]["archived"] is True


@pytest.mark.asyncio
async def test_list_threads_survives_private_archive_403(
    capsys: pytest.CaptureFixture[str],
) -> None:
    public_threads = {
        "threads": [
            {
                "id": "t1",
                "name": "Public Only",
                "type": 11,
                "message_count": 3,
                "thread_metadata": {"archived": True},
            }
        ],
        "members": [],
        "has_more": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "/threads/archived/private" in request.url.path:
            return httpx.Response(403, json={"message": "Missing Permissions", "code": 50013})
        if "/threads/archived/public" in request.url.path:
            return httpx.Response(200, json=public_threads)
        if "/messages" in request.url.path:
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await list_threads(client, channel_id="c1")

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["id"] == "t1"


@pytest.mark.asyncio
async def test_list_threads_paginates_archived(
    capsys: pytest.CaptureFixture[str],
) -> None:
    page1 = {
        "threads": [
            {
                "id": "t1",
                "name": "Thread 1",
                "type": 11,
                "message_count": 5,
                "thread_metadata": {
                    "archived": True,
                    "archive_timestamp": "2024-06-01T00:00:00+00:00",
                },
            }
        ],
        "members": [],
        "has_more": True,
    }
    page2 = {
        "threads": [
            {
                "id": "t2",
                "name": "Thread 2",
                "type": 11,
                "message_count": 3,
                "thread_metadata": {
                    "archived": True,
                    "archive_timestamp": "2024-05-01T00:00:00+00:00",
                },
            }
        ],
        "members": [],
        "has_more": False,
    }
    empty_archived = {"threads": [], "members": [], "has_more": False}
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        if "/threads/archived/public" in request.url.path:
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json=page1)
            return httpx.Response(200, json=page2)
        if "/threads/archived/private" in request.url.path:
            return httpx.Response(200, json=empty_archived)
        if "/messages" in request.url.path:
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await list_threads(client, channel_id="c1")

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 2
    assert output[0]["id"] == "t1"
    assert output[1]["id"] == "t2"
