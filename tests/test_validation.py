import httpx
import pytest

from discord_cli.client import DiscordClient
from discord_cli.validation import validate_token


@pytest.mark.asyncio
async def test_validate_token_returns_user_info() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"id": "111", "username": "alice", "global_name": "Alice"}
        )

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="t", transport=transport) as client:
        info = await validate_token(client)
    assert info["username"] == "alice"


@pytest.mark.asyncio
async def test_validate_token_raises_on_invalid() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "401: Unauthorized", "code": 0})

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="bad", transport=transport) as client:
        from discord_cli.auth.errors import AuthError

        with pytest.raises(AuthError, match="Invalid token"):
            await validate_token(client)
