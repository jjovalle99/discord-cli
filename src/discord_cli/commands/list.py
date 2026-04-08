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


def _shape_member(
    raw: dict[str, Any], role_id_to_name: dict[str, str]
) -> dict[str, Any]:
    user = raw.get("user", {})
    resolved_roles = [role_id_to_name.get(rid, rid) for rid in raw.get("roles", [])]
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "roles": resolved_roles,
    }


_MEMBERS_PAGE_SIZE = 1000


async def list_members(
    client: DiscordClient,
    guild_id: str,
    *,
    limit: int = 1000,
    role: str | None = None,
) -> None:
    import asyncio

    first_page_size = (
        _MEMBERS_PAGE_SIZE if role is not None else min(limit, _MEMBERS_PAGE_SIZE)
    )
    roles_coro = client.api_get_list(f"/guilds/{guild_id}/roles")
    first_batch_coro = client.api_get_list(
        f"/guilds/{guild_id}/members",
        params={"limit": str(first_page_size), "after": "0"},
    )
    roles_list, first_batch = await asyncio.gather(roles_coro, first_batch_coro)

    role_id_to_name: dict[str, str] = {r["id"]: r["name"] for r in roles_list}
    target_role_id: str | None = None
    if role is not None:
        for r in roles_list:
            if r["name"] == role:
                target_role_id = r["id"]
                break

    result: list[dict[str, Any]] = []
    batch = first_batch
    page_size = first_page_size
    while True:
        if not batch:
            break
        for m in batch:
            if target_role_id is not None and target_role_id not in m.get("roles", []):
                continue
            result.append(_shape_member(m, role_id_to_name))
            if len(result) >= limit:
                break
        if len(result) >= limit or len(batch) < page_size:
            break
        after = batch[-1].get("user", {}).get("id", "0")
        page_size = (
            _MEMBERS_PAGE_SIZE
            if role is not None
            else min(limit - len(result), _MEMBERS_PAGE_SIZE)
        )
        batch = await client.api_get_list(
            f"/guilds/{guild_id}/members",
            params={"limit": str(page_size), "after": after},
        )

    write_success(result)
