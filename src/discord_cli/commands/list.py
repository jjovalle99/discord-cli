from typing import Any

from discord_cli.client import DiscordClient
from discord_cli.output import write_success

CHANNEL_TYPE_NAMES: dict[int, str] = {
    0: "text",
    1: "dm",
    2: "voice",
    3: "group_dm",
    4: "category",
    5: "announcement",
    13: "stage",
    15: "forum",
    16: "media",
}

_SERVER_FIELDS = (
    "id",
    "name",
    "icon",
    "owner",
    "approximate_member_count",
    "approximate_presence_count",
)
_CHANNEL_FIELDS = ("id", "name", "type", "topic", "parent_id", "position", "nsfw")
_DM_FIELDS = ("id", "type", "recipients", "last_message_id")


def _pick(raw: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {k: raw.get(k) for k in fields}


def _shape_with_type_name(
    raw: dict[str, Any], fields: tuple[str, ...]
) -> dict[str, Any]:
    shaped = _pick(raw, fields)
    shaped["type_name"] = CHANNEL_TYPE_NAMES.get(raw.get("type", -1), "unknown")
    return shaped


async def list_servers(client: DiscordClient, *, limit: int = 200) -> None:
    guilds = await client.api_get_list(
        "/users/@me/guilds",
        params={"with_counts": "true", "limit": str(min(limit, 200))},
    )
    write_success([_pick(g, _SERVER_FIELDS) for g in guilds])


async def list_channels(client: DiscordClient, guild_id: str) -> None:
    channels = await client.api_get_list(f"/guilds/{guild_id}/channels")
    write_success([_shape_with_type_name(c, _CHANNEL_FIELDS) for c in channels])


async def list_dms(client: DiscordClient) -> None:
    channels = await client.api_get_list("/users/@me/channels")
    write_success([_shape_with_type_name(c, _DM_FIELDS) for c in channels])
