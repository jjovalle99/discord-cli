import json

import httpx
import pytest

from discord_cli.client import DiscordClient


@pytest.fixture
def mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "test-token"
        return httpx.Response(200, json={"id": "123", "username": "bot"})

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_client_sends_auth_header(mock_transport: httpx.MockTransport) -> None:
    async with DiscordClient(token="test-token", transport=mock_transport) as client:
        result = await client.api_get("/users/@me")
    assert result["id"] == "123"


@pytest.mark.asyncio
async def test_client_retries_on_429() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, json={"retry_after": 0.01})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        result = await client.api_get("/test")
    assert result == {"ok": True}
    assert call_count == 2


@pytest.mark.asyncio
async def test_429_stderr_includes_path(capsys: pytest.CaptureFixture[str]) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, json={"retry_after": 0.01})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await client.api_get("/channels/123/messages")
    stderr = capsys.readouterr().err
    assert "[rate-limit]" in stderr
    assert "/channels/123/messages" in stderr
    assert "0.01s" in stderr


@pytest.mark.asyncio
async def test_429_stderr_suppressed_when_quiet(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from discord_cli.output import set_quiet

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, json={"retry_after": 0.01})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    set_quiet(True)
    try:
        async with DiscordClient(token="t", transport=transport) as client:
            await client.api_get("/channels/123/messages")
        stderr = capsys.readouterr().err
        assert stderr == ""
    finally:
        set_quiet(False)


def test_quiet_flag_suppresses_429_via_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from discord_cli.cli import _run
    from discord_cli.commands.list import list_servers

    call_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json={"id": "1", "username": "u"})
        if call_count == 2:
            return httpx.Response(429, json={"retry_after": 0.01})
        return httpx.Response(200, json=[{"id": "1", "name": "S"}])

    transport = httpx.MockTransport(handler)
    _run(
        lambda c: list_servers(c),
        token="t",
        transport=transport,
        quiet=True,
    )
    stderr = capsys.readouterr().err
    assert stderr == ""


@pytest.mark.asyncio
async def test_retries_up_to_max_on_repeated_429() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            return httpx.Response(429, json={"retry_after": 0.01})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        result = await client.api_get("/test")
    assert result == {"ok": True}
    assert call_count == 4


@pytest.mark.asyncio
async def test_429_raises_after_max_retries() -> None:
    from discord_cli.client import DiscordAPIError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"retry_after": 0.01})

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        with pytest.raises(DiscordAPIError) as exc_info:
            await client.api_get("/test")
    assert exc_info.value.status == 429


@pytest.mark.asyncio
async def test_rate_limit_stats_tracks_headers_and_retries() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, json={"retry_after": 0.01})
        return httpx.Response(
            200,
            json={"ok": True},
            headers={
                "X-RateLimit-Remaining": "3",
                "X-RateLimit-Reset-After": "1.5",
            },
        )

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        await client.api_get("/test")
        stats = client.rate_limit_stats
    assert stats["retries"] == 1
    assert stats["remaining"] == 3
    assert stats["reset_after"] == 1.5


@pytest.mark.asyncio
async def test_client_raises_on_error_response() -> None:
    from discord_cli.client import DiscordAPIError

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Unknown Channel", "code": 10003})

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        with pytest.raises(DiscordAPIError) as exc_info:
            await client.api_get("/channels/999")
    assert exc_info.value.status == 404


def test_rate_limit_info_wraps_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from discord_cli.cli import _run
    from discord_cli.commands.list import list_servers

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"id": "1", "name": "S"}],
            headers={
                "X-RateLimit-Remaining": "5",
                "X-RateLimit-Reset-After": "2.0",
            },
        )

    transport = httpx.MockTransport(handler)
    _run(
        lambda c: list_servers(c),
        token="t",
        transport=transport,
        rate_limit_info=True,
    )
    output = json.loads(capsys.readouterr().out)
    assert "data" in output
    assert "_rate_limit" in output
    assert output["_rate_limit"]["remaining"] == 5
    assert output["_rate_limit"]["reset_after"] == 2.0
    assert output["_rate_limit"]["retries"] == 0


def test_rate_limit_info_non_json_passes_through(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from discord_cli.cli import _run
    from discord_cli.commands.read import read_channel

    msg = {
        "id": "1",
        "author": {"id": "u1", "username": "alice"},
        "content": "hello",
        "timestamp": "2024-01-15T10:30:00+00:00",
        "type": 0,
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[msg],
            headers={"X-RateLimit-Remaining": "3"},
        )

    transport = httpx.MockTransport(handler)
    _run(
        lambda c: read_channel(c, channel_id="ch1", limit=1, format="text"),
        token="t",
        transport=transport,
        rate_limit_info=True,
    )
    captured = capsys.readouterr()
    assert "[2024-01-15 10:30] alice: hello" in captured.out
    rate_info = json.loads(captured.err.split("\n")[-2])
    assert rate_info["_rate_limit"]["remaining"] == 3


def test_rate_limit_info_with_min_remaining(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from discord_cli.cli import _run
    from discord_cli.commands.list import list_servers

    call_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        remaining = "10" if call_count == 1 else "3"
        return httpx.Response(
            200,
            json=[{"id": "1", "name": "S"}],
            headers={
                "X-RateLimit-Remaining": remaining,
                "X-RateLimit-Reset-After": "1.0",
            },
        )

    transport = httpx.MockTransport(handler)
    _run(
        lambda c: list_servers(c),
        token="t",
        transport=transport,
        rate_limit_info=True,
    )
    output = json.loads(capsys.readouterr().out)
    assert output["_rate_limit"]["remaining"] == 3


@pytest.mark.asyncio
async def test_client_rejects_non_cdn_url() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200))
    async with DiscordClient(token="t", transport=transport) as client:
        with pytest.raises(ValueError, match="Discord CDN"):
            await client.fetch_url_bytes("https://evil.com/payload")


@pytest.mark.asyncio
async def test_fetch_url_bytes_does_not_send_auth_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return httpx.Response(200, content=b"file-data")

    cdn_transport = httpx.MockTransport(handler)
    async with DiscordClient(token="secret", cdn_transport=cdn_transport) as client:
        data = await client.fetch_url_bytes(
            "https://cdn.discordapp.com/attachments/1/2/f.png"
        )
    assert data == b"file-data"


@pytest.mark.asyncio
async def test_client_rejects_cdn_subdomain() -> None:
    async with DiscordClient(token="t") as client:
        with pytest.raises(ValueError, match="Discord CDN"):
            await client.fetch_url_bytes("https://evil.cdn.discordapp.com/file")


@pytest.mark.asyncio
async def test_client_sends_super_properties_header() -> None:
    from discord_cli.super_properties import build_super_properties

    sp = build_super_properties(build_number=999)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Super-Properties"] == sp
        from discord_cli.super_properties import get_fingerprint

        assert request.headers["User-Agent"] == get_fingerprint().user_agent
        return httpx.Response(200, json={"id": "1"})

    transport = httpx.MockTransport(handler)
    async with DiscordClient(
        token="t", transport=transport, super_properties=sp
    ) as client:
        await client.api_get("/users/@me")
