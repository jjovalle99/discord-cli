import json

import httpx
import pytest

from discord_cli.client import DiscordClient
from discord_cli.commands.list import list_members, list_servers


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
