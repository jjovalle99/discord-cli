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
async def test_client_raises_on_error_response() -> None:
    from discord_cli.client import DiscordAPIError

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Unknown Channel", "code": 10003})

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        with pytest.raises(DiscordAPIError) as exc_info:
            await client.api_get("/channels/999")
    assert exc_info.value.status == 404


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
