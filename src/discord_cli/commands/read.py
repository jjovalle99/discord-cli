from typing import Any

from discord_cli.client import DiscordClient
from discord_cli.output import write_success


_AUTHOR_KEEP_FIELDS = ("id", "username", "global_name")
_AUTHOR_PROVENANCE_FIELDS = ("bot", "system")
# Discord uses null vs absent to distinguish "reply to deleted message" from "not a reply"
_PRESERVE_WHEN_NULL = frozenset({"referenced_message"})


def _compact_author(author: dict[str, Any]) -> dict[str, Any]:
    result = {k: author[k] for k in _AUTHOR_KEEP_FIELDS if author.get(k) is not None}
    for k in _AUTHOR_PROVENANCE_FIELDS:
        if author.get(k):
            result[k] = author[k]
    return result


def _compact_message(msg: dict[str, Any]) -> dict[str, Any]:
    result = {k: v for k, v in msg.items() if v is not None or k in _PRESERVE_WHEN_NULL}
    if "author" in result and isinstance(result["author"], dict):
        result["author"] = _compact_author(result["author"])
    return result


async def read_channel(
    client: DiscordClient, *, channel_id: str, limit: int = 50, compact: bool = False
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

    result = all_messages[:limit]
    if compact:
        result = [_compact_message(msg) for msg in result]
    write_success(result)


async def read_message(
    client: DiscordClient,
    *,
    channel_id: str,
    message_id: str,
    compact: bool = False,
) -> None:
    msg = await client.api_get(f"/channels/{channel_id}/messages/{message_id}")
    if compact:
        msg = _compact_message(msg)
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
