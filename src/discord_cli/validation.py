from typing import Any

from discord_cli.auth.errors import AuthError
from discord_cli.client import DiscordAPIError, DiscordClient


async def validate_token(client: DiscordClient) -> dict[str, Any]:
    try:
        return await client.api_get("/users/@me")
    except DiscordAPIError as e:
        if e.status == 401:
            raise AuthError(
                "Invalid token. Run 'discord-cli auth' to re-authenticate."
            ) from e
        raise
