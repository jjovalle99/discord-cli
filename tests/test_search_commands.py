import json

import httpx
import pytest

from discord_cli.client import DiscordClient
from discord_cli.commands.search import search_messages


@pytest.mark.asyncio
async def test_search_messages_emits_results(
    capsys: pytest.CaptureFixture[str],
) -> None:
    response_data = {
        "total_results": 1,
        "messages": [[{"id": "100", "content": "found it"}]],
    }

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=response_data))
    async with DiscordClient(token="t", transport=transport) as client:
        await search_messages(client, guild_id="111", query="found")

    output = json.loads(capsys.readouterr().out)
    assert output["total_results"] == 1
    assert output["messages"][0][0]["content"] == "found it"


@pytest.mark.asyncio
async def test_search_messages_retries_on_202(
    capsys: pytest.CaptureFixture[str],
) -> None:
    call_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(202, json={"retry_after": 0.01})
        return httpx.Response(200, json={"total_results": 0, "messages": []})

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await search_messages(client, guild_id="111", query="test")

    assert call_count == 2
    output = json.loads(capsys.readouterr().out)
    assert output["total_results"] == 0


@pytest.mark.asyncio
async def test_search_dms_emits_results(capsys: pytest.CaptureFixture[str]) -> None:
    from discord_cli.commands.search import search_dms

    response_data = {
        "total_results": 1,
        "messages": [[{"id": "50", "content": "dm msg"}]],
    }

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=response_data))
    async with DiscordClient(token="t", transport=transport) as client:
        await search_dms(client, channel_id="333", query="dm")

    output = json.loads(capsys.readouterr().out)
    assert output["messages"][0][0]["content"] == "dm msg"
