from typing import Any

from discord_cli.client import DiscordClient
from discord_cli.output import write_success


async def read_channel(
    client: DiscordClient, *, channel_id: str, limit: int = 50
) -> None:
    all_messages: list[dict[str, Any]] = []
    params: dict[str, str] = {"limit": str(min(limit, 100))}

    while len(all_messages) < limit:
        batch = await client.api_get_list(
            f"/channels/{channel_id}/messages", params=params
        )
        if not batch:
            break
        all_messages.extend(batch)
        if len(batch) < 100:
            break
        params["before"] = batch[-1]["id"]
        params["limit"] = str(min(limit - len(all_messages), 100))

    write_success(all_messages[:limit])


async def read_message(
    client: DiscordClient, *, channel_id: str, message_id: str
) -> None:
    msg = await client.api_get(f"/channels/{channel_id}/messages/{message_id}")
    write_success(msg)


async def read_server_info(client: DiscordClient, *, guild_id: str) -> None:
    guild = await client.api_get(f"/guilds/{guild_id}", params={"with_counts": "true"})
    write_success(guild)


async def read_channel_info(client: DiscordClient, *, channel_id: str) -> None:
    channel = await client.api_get(f"/channels/{channel_id}")
    write_success(channel)


async def read_user(client: DiscordClient, *, user_id: str) -> None:
    user = await client.api_get(f"/users/{user_id}")
    write_success(user)


async def read_member(client: DiscordClient, *, guild_id: str, user_id: str) -> None:
    member = await client.api_get(f"/guilds/{guild_id}/members/{user_id}")
    write_success(member)
