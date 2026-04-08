import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest

from discord_cli.client import DiscordClient
from discord_cli.commands.search import search_messages

VALIDATE_RESPONSE = {"id": "1", "username": "a", "global_name": "A"}


def _mock_get_client(mock_transport: httpx.AsyncBaseTransport):  # noqa: ANN201, ANN202
    @asynccontextmanager
    async def _factory(
        token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> AsyncIterator[DiscordClient]:
        async with DiscordClient(
            token=token or "t", transport=mock_transport
        ) as client:
            yield client

    return _factory


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


@pytest.mark.asyncio
async def test_search_fallback_read_returns_matching_messages(
    capsys: pytest.CaptureFixture[str],
) -> None:
    call_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        call_paths.append(path)
        if "search" in path:
            return httpx.Response(200, json={"total_results": 0, "messages": []})
        return httpx.Response(
            200,
            json=[
                {"id": "1", "content": "hello world", "author": {"username": "u1"}},
                {"id": "2", "content": "goodbye", "author": {"username": "u2"}},
                {"id": "3", "content": "Hello again", "author": {"username": "u3"}},
            ],
        )

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await search_messages(
            client,
            guild_id="111",
            query="hello",
            channel_id="999",
            fallback_read=True,
        )

    output = json.loads(capsys.readouterr().out)
    assert output["total_results"] == 2
    assert len(output["messages"]) == 2
    contents = [m[0]["content"] for m in output["messages"]]
    assert "hello world" in contents
    assert "Hello again" in contents
    assert any("search" in p for p in call_paths)
    assert any("messages" in p and "search" not in p for p in call_paths)


@pytest.mark.asyncio
async def test_search_fallback_read_without_channel_id_raises() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    async with DiscordClient(token="t", transport=transport) as client:
        with pytest.raises(ValueError, match="--fallback-read requires --channel$"):
            await search_messages(
                client, guild_id="111", query="hello", fallback_read=True
            )


@pytest.mark.asyncio
async def test_search_dms_fallback_read_returns_matching_messages(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from discord_cli.commands.search import search_dms

    def handler(request: httpx.Request) -> httpx.Response:
        if "search" in request.url.path:
            return httpx.Response(200, json={"total_results": 0, "messages": []})
        return httpx.Response(
            200,
            json=[
                {"id": "1", "content": "hey there", "author": {"username": "u1"}},
                {"id": "2", "content": "nope", "author": {"username": "u2"}},
            ],
        )

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await search_dms(client, channel_id="444", query="hey", fallback_read=True)

    output = json.loads(capsys.readouterr().out)
    assert output["total_results"] == 1
    assert output["messages"][0][0]["content"] == "hey there"


@pytest.mark.asyncio
async def test_search_fallback_paginates_beyond_first_page(
    capsys: pytest.CaptureFixture[str],
) -> None:
    page_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal page_count
        if "search" in request.url.path:
            return httpx.Response(200, json={"total_results": 0, "messages": []})
        page_count += 1
        if page_count == 1:
            return httpx.Response(
                200,
                json=[{"id": str(i), "content": "filler"} for i in range(100, 0, -1)],
            )
        return httpx.Response(
            200,
            json=[{"id": "0", "content": "target match"}],
        )

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await search_messages(
            client,
            guild_id="111",
            query="target",
            channel_id="999",
            fallback_read=True,
        )

    output = json.loads(capsys.readouterr().out)
    assert output["total_results"] == 1
    assert output["messages"][0][0]["content"] == "target match"
    assert page_count == 2


@pytest.mark.asyncio
async def test_search_fallback_rejects_unsupported_filters() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    async with DiscordClient(token="t", transport=transport) as client:
        with pytest.raises(ValueError, match="--fallback-read does not support"):
            await search_messages(
                client,
                guild_id="111",
                query="hello",
                channel_id="999",
                author_id="123",
                fallback_read=True,
            )


@pytest.mark.asyncio
async def test_search_output_includes_index_lag_note(
    capsys: pytest.CaptureFixture[str],
) -> None:
    response_data = {"total_results": 0, "messages": []}
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=response_data))
    async with DiscordClient(token="t", transport=transport) as client:
        await search_messages(client, guild_id="111", query="test")

    output = json.loads(capsys.readouterr().out)
    assert "note" in output
    assert "index" in output["note"].lower()
    assert "--channel" in output["note"]
    assert "--channel-id" not in output["note"]


@pytest.mark.asyncio
async def test_search_messages_before_sends_max_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json={"total_results": 0, "messages": []})

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await search_messages(
            client, guild_id="111", query="test", before="2026-01-15"
        )

    assert "max_id" in captured_params
    from discord_cli.snowflake import date_to_snowflake

    assert captured_params["max_id"] == date_to_snowflake("2026-01-15")
    output = json.loads(capsys.readouterr().out)
    assert output["total_results"] == 0


@pytest.mark.asyncio
async def test_search_messages_invalid_before_raises(
    capsys: pytest.CaptureFixture[str],
) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    async with DiscordClient(token="t", transport=transport) as client:
        with pytest.raises(SystemExit) as exc_info:
            await search_messages(
                client, guild_id="111", query="test", before="not-a-date"
            )
    assert exc_info.value.code == 1
    err = json.loads(capsys.readouterr().err)
    assert err["error"] == "invalid_date"


@pytest.mark.asyncio
async def test_search_messages_after_sends_min_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json={"total_results": 0, "messages": []})

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await search_messages(
            client, guild_id="111", query="test", after="2026-01-15"
        )

    assert "min_id" in captured_params
    from discord_cli.snowflake import date_to_snowflake

    assert captured_params["min_id"] == date_to_snowflake("2026-01-15")
    output = json.loads(capsys.readouterr().out)
    assert output["total_results"] == 0


@pytest.mark.asyncio
async def test_search_fallback_threads_date_bounds(
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_fallback_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if "search" in request.url.path:
            return httpx.Response(200, json={"total_results": 0, "messages": []})
        captured_fallback_params.update(dict(request.url.params))
        return httpx.Response(
            200,
            json=[{"id": "1", "content": "match me"}],
        )

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await search_messages(
            client,
            guild_id="111",
            query="match",
            channel_id="999",
            before="2026-01-15",
            fallback_read=True,
        )

    from discord_cli.snowflake import date_to_snowflake

    assert captured_fallback_params.get("before") == date_to_snowflake("2026-01-15")
    output = json.loads(capsys.readouterr().out)
    assert output["total_results"] == 1


@pytest.mark.parametrize("flag", ["--from", "--author-id"])
def test_search_messages_cli_accepts_from_flags(
    flag: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from discord_cli.cli import app

    search_response = {"total_results": 1, "messages": [[{"id": "1", "content": "hi"}]]}
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if "/users/@me" in request.url.path:
            return httpx.Response(200, json=VALIDATE_RESPONSE)
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json=search_response)

    monkeypatch.setenv("DISCORD_TOKEN", "t")
    monkeypatch.setattr(
        "discord_cli.cli._get_client",
        _mock_get_client(httpx.MockTransport(handler)),
    )

    with pytest.raises(SystemExit) as exc_info:
        app(["search", "messages", "111", "hi", flag, "999"])

    assert exc_info.value.code == 0
    assert captured_params.get("author_id") == "999"


@pytest.mark.parametrize("flag", ["--channel", "--channel-id"])
def test_search_messages_cli_accepts_channel_flags(
    flag: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from discord_cli.cli import app

    search_response = {"total_results": 1, "messages": [[{"id": "1", "content": "hi"}]]}
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if "/users/@me" in request.url.path:
            return httpx.Response(200, json=VALIDATE_RESPONSE)
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json=search_response)

    monkeypatch.setenv("DISCORD_TOKEN", "t")
    monkeypatch.setattr(
        "discord_cli.cli._get_client",
        _mock_get_client(httpx.MockTransport(handler)),
    )

    with pytest.raises(SystemExit) as exc_info:
        app(["search", "messages", "111", "hi", flag, "999"])

    assert exc_info.value.code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["total_results"] == 1
    assert captured_params.get("channel_id") == "999"
