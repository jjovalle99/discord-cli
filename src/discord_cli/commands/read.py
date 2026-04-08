import json
import re
from typing import Any

from discord_cli.client import DiscordClient
from discord_cli.output import write_error, write_success


def _stdout_size(data: list[dict[str, Any]] | dict[str, Any]) -> int:
    return len(json.dumps(data, indent=2).encode()) + 1


def _truncate_to_fit(
    messages: list[dict[str, Any]], max_bytes: int, total_available: int
) -> dict[str, Any] | None:
    kept = list(messages)
    while True:
        envelope: dict[str, Any] = {
            "truncated": len(kept) < total_available,
            "messages_returned": len(kept),
            "messages_available": total_available,
            "messages": kept,
        }
        if _stdout_size(envelope) <= max_bytes:
            return envelope
        if not kept:
            return None
        kept.pop()


_CHANNEL_MENTION_RE = re.compile(r"<#(\d+)>")


_AUTHOR_SCAN_CAP = 500
_SYSTEM_MESSAGE_TYPES = frozenset(
    {
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        14,
        15,
        16,
        17,
        18,
        21,
        22,
        24,
        25,
        26,
        27,
        28,
        29,
        31,
        32,
        36,
        37,
        38,
        39,
        44,
        46,
    }
)

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


async def _build_channel_map(client: DiscordClient, channel_id: str) -> dict[str, str]:
    channel_info = await client.api_get(f"/channels/{channel_id}")
    result: dict[str, str] = {}
    if channel_info.get("name"):
        result[channel_info["id"]] = channel_info["name"]
    guild_id = channel_info.get("guild_id")
    if not guild_id:
        return result
    channels = await client.api_get_list(f"/guilds/{guild_id}/channels")
    for ch in channels:
        if "name" in ch:
            result[ch["id"]] = ch["name"]
    return result


def _resolve_channels(
    msg: dict[str, Any], channel_map: dict[str, str]
) -> dict[str, Any]:
    msg = dict(msg)
    ch_id = msg.get("channel_id", "")
    if ch_id in channel_map:
        msg["channel_name"] = channel_map[ch_id]
    content = msg.get("content", "")
    if content:
        msg["content"] = _CHANNEL_MENTION_RE.sub(
            lambda m: (
                f"#{channel_map[m.group(1)]}"
                if m.group(1) in channel_map
                else m.group(0)
            ),
            content,
        )
    return msg


async def read_channel(
    client: DiscordClient,
    *,
    channel_id: str,
    limit: int = 50,
    compact: bool = False,
    author: str | None = None,
    skip_system: bool = False,
    resolve_channels: bool = False,
    max_bytes: int | None = None,
    pinned: bool = False,
    before: str | None = None,
    after: str | None = None,
) -> None:
    if before and after:
        write_error(
            "incompatible_flags",
            "--before and --after are mutually exclusive",
        )
        raise SystemExit(1)
    if pinned:
        if author or skip_system or before or after:
            write_error(
                "incompatible_flags",
                "--pinned cannot be combined with --author, --skip-system, --before, or --after",
            )
            raise SystemExit(1)
        all_messages = await client.api_get_list(f"/channels/{channel_id}/pins")
    else:
        all_messages = []
        scanned = 0
        needs_client_filter = bool(author) or skip_system
        params: dict[str, str] = {
            "limit": str(100 if needs_client_filter else min(limit, 100))
        }
        if before:
            params["before"] = before
        if after:
            params["after"] = after

        while len(all_messages) < limit:
            batch = await client.api_get_list(
                f"/channels/{channel_id}/messages", params=params
            )
            if not batch:
                break

            page_exhausted = len(batch) < 100

            if needs_client_filter:
                if author:
                    scanned += len(batch)
                filtered = [
                    m
                    for m in batch
                    if (not skip_system or m["type"] not in _SYSTEM_MESSAGE_TYPES)
                    and (not author or m["author"]["id"] == author)
                ]
                all_messages.extend(filtered)
            else:
                all_messages.extend(batch)

            if page_exhausted or (author and scanned >= _AUTHOR_SCAN_CAP):
                break
            if after:
                params["after"] = max(batch, key=lambda m: int(m["id"]))["id"]
            else:
                params["before"] = batch[-1]["id"]
            if not needs_client_filter:
                params["limit"] = str(min(limit - len(all_messages), 100))

    result = all_messages[:limit]
    if resolve_channels:
        try:
            channel_map = await _build_channel_map(client, channel_id)
        except Exception:
            channel_map = {}
        if channel_map:
            result = [_resolve_channels(msg, channel_map) for msg in result]
    if compact:
        result = [_compact_message(msg) for msg in result]
    if max_bytes is not None:
        if _stdout_size(result) > max_bytes:
            envelope = _truncate_to_fit(result, max_bytes, len(result))
            if envelope is None:
                write_error(
                    "max_bytes_too_small",
                    f"--max-bytes {max_bytes} is too small for even an empty response",
                )
                raise SystemExit(1)
            write_success(envelope)
            return
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
