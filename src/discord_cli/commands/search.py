import asyncio
from typing import Any

from discord_cli.client import DiscordClient
from discord_cli.output import write_status, write_success

MAX_SEARCH_RETRIES = 3
SEARCH_INDEX_NOTE = "Search index may lag behind recent messages. Use --fallback-read with --channel to also search channel history."
_FALLBACK_PAGE_SIZE = 100
_FALLBACK_MAX_SCAN = 500


async def _search(
    client: DiscordClient, path: str, params: dict[str, str]
) -> dict[str, Any]:
    for _ in range(MAX_SEARCH_RETRIES):
        response = await client._request(path, params=params)

        if response.status_code == 202:
            retry_after = max(float(response.json().get("retry_after", 1)), 0.1)
            write_status(f"Index not ready. Retrying in {retry_after}s...")
            await asyncio.sleep(retry_after)
            continue

        return response.json()  # type: ignore[no-any-return]

    msg = "Search index not ready after retries."
    raise TimeoutError(msg)


async def _fallback_channel_search(
    client: DiscordClient, channel_id: str, query: str, limit: int
) -> dict[str, Any]:
    matched: list[dict[str, Any]] = []
    params: dict[str, str] = {"limit": str(_FALLBACK_PAGE_SIZE)}
    query_lower = query.lower()
    scanned = 0

    while len(matched) < limit and scanned < _FALLBACK_MAX_SCAN:
        batch: list[dict[str, Any]] = await client.api_get_list(
            f"/channels/{channel_id}/messages", params=params
        )
        if not batch:
            break
        scanned += len(batch)
        for msg in batch:
            if query_lower in msg.get("content", "").lower():
                matched.append(msg)
                if len(matched) >= limit:
                    break
        if len(batch) < _FALLBACK_PAGE_SIZE:
            break
        params["before"] = batch[-1]["id"]

    return {
        "total_results": len(matched),
        "messages": [[m] for m in matched],
        "note": f"Results from channel history fallback (scanned {scanned} messages). Search index may lag behind recent messages.",
    }


def _validate_fallback_filters(
    *,
    channel_id: str | None,
    author_id: str | None = None,
    has: str | None = None,
    offset: int = 0,
) -> str:
    if not channel_id:
        msg = "--fallback-read requires --channel"
        raise ValueError(msg)
    unsupported: list[str] = []
    if author_id:
        unsupported.append("--author-id")
    if has:
        unsupported.append("--has")
    if offset:
        unsupported.append("--offset")
    if unsupported:
        msg = f"--fallback-read does not support: {', '.join(unsupported)}"
        raise ValueError(msg)
    return channel_id


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
    fallback_read: bool = False,
) -> None:
    validated_channel_id: str | None = None
    if fallback_read:
        validated_channel_id = _validate_fallback_filters(
            channel_id=channel_id, author_id=author_id, has=has, offset=offset
        )

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

    if validated_channel_id and result.get("total_results", 0) == 0:
        result = await _fallback_channel_search(
            client, validated_channel_id, query, limit
        )
    else:
        result["note"] = SEARCH_INDEX_NOTE

    write_success(result)


async def search_dms(
    client: DiscordClient,
    *,
    channel_id: str,
    query: str,
    limit: int = 25,
    fallback_read: bool = False,
) -> None:
    params: dict[str, str] = {
        "content": query,
        "limit": str(min(limit, 25)),
    }
    result = await _search(client, f"/channels/{channel_id}/messages/search", params)

    if fallback_read and result.get("total_results", 0) == 0:
        result = await _fallback_channel_search(client, channel_id, query, limit)
    else:
        result["note"] = SEARCH_INDEX_NOTE

    write_success(result)
