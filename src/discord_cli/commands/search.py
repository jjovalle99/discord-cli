import asyncio
import sys
from typing import Any

from discord_cli.client import DiscordClient
from discord_cli.output import write_success

MAX_SEARCH_RETRIES = 3


async def _search(
    client: DiscordClient, path: str, params: dict[str, str]
) -> dict[str, Any]:
    for _ in range(MAX_SEARCH_RETRIES):
        response = await client._request(path, params=params)

        if response.status_code == 202:
            retry_after = max(float(response.json().get("retry_after", 1)), 0.1)
            print(f"Index not ready. Retrying in {retry_after}s...", file=sys.stderr)
            await asyncio.sleep(retry_after)
            continue

        return response.json()  # type: ignore[no-any-return]

    msg = "Search index not ready after retries."
    raise TimeoutError(msg)


async def search_messages(
    client: DiscordClient,
    *,
    guild_id: str,
    query: str,
    limit: int = 25,
    channel_id: str | None = None,
    author_id: str | None = None,
    has: str | None = None,
    sort_by: str = "timestamp",
    sort_order: str = "desc",
    offset: int = 0,
) -> None:
    params: dict[str, str] = {
        "content": query,
        "limit": str(min(limit, 25)),
        "sort_by": sort_by,
        "sort_order": sort_order,
        "offset": str(offset),
    }
    if channel_id:
        params["channel_id"] = channel_id
    if author_id:
        params["author_id"] = author_id
    if has:
        params["has"] = has

    result = await _search(client, f"/guilds/{guild_id}/messages/search", params)
    write_success(result)


async def search_dms(
    client: DiscordClient,
    *,
    channel_id: str,
    query: str,
    limit: int = 25,
) -> None:
    params: dict[str, str] = {
        "content": query,
        "limit": str(min(limit, 25)),
    }
    result = await _search(client, f"/channels/{channel_id}/messages/search", params)
    write_success(result)
