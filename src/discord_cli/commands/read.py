import json
import re
from datetime import datetime, timezone
from typing import Any, Literal

from discord_cli.client import DiscordClient
from discord_cli.output import write_error, write_success

type Format = Literal["json", "jsonl", "text"]


def _to_items(data: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    return data if isinstance(data, list) else [data]


def _item_size(msg: dict[str, Any], fmt: Format) -> int:
    if fmt == "text":
        return len(_format_text_line(msg).encode()) + 1
    if fmt == "jsonl":
        return len(json.dumps(msg).encode()) + 1
    return 0


def _output_size(data: list[dict[str, Any]] | dict[str, Any], fmt: Format = "json") -> int:
    if fmt in ("text", "jsonl"):
        return sum(_item_size(m, fmt) for m in _to_items(data))
    return len(json.dumps(data, indent=2).encode()) + 1


def _truncate_to_fit(
    messages: list[dict[str, Any]],
    max_bytes: int,
    total_size: int,
    fmt: Format = "json",
) -> list[dict[str, Any]] | None:
    kept = list(messages)
    if fmt in ("text", "jsonl"):
        current = total_size
        while current > max_bytes:
            if not kept:
                return None
            current -= _item_size(kept.pop(), fmt)
        return kept
    while True:
        envelope: dict[str, Any] = {
            "truncated": len(kept) < len(messages),
            "messages_returned": len(kept),
            "messages_available": len(messages),
            "messages": kept,
        }
        if _output_size(envelope) <= max_bytes:
            return kept
        if not kept:
            return None
        kept.pop()


_CHANNEL_MENTION_RE = re.compile(r"<#(\d+)>")
_USER_MENTION_PAT = r"<@!?(\d+)>"
_USER_MENTION_RE = re.compile(_USER_MENTION_PAT)
_CODE_OR_MENTION_RE = re.compile(rf"```[\s\S]*?```|`[^`]+`|{_USER_MENTION_PAT}")


def _message_sort_key(m: dict[str, Any]) -> int:
    return int(m["id"])


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


def _replace_mentions_outside_code(content: str, mention_map: dict[str, str]) -> str:
    def _replacer(m: re.Match[str]) -> str:
        uid = m.group(1)
        if uid and uid in mention_map:
            return f"@{mention_map[uid]}"
        return m.group(0)

    return _CODE_OR_MENTION_RE.sub(_replacer, content)


def _resolve_mentions(msg: dict[str, Any]) -> dict[str, Any]:
    mentions = msg.get("mentions", [])
    if not mentions:
        return msg
    content = msg.get("content", "")
    if not content:
        return msg
    mention_map = {m["id"]: m["username"] for m in mentions}
    msg = dict(msg)
    msg["content"] = _replace_mentions_outside_code(content, mention_map)
    return msg


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


def _format_text_line(msg: dict[str, Any]) -> str:
    ts = msg.get("timestamp", "")
    if ts:
        dt = datetime.fromisoformat(ts)
        ts_str = dt.strftime("%Y-%m-%d %H:%M")
    else:
        ts_str = "unknown"
    username = msg.get("author", {}).get("username", "unknown")
    content = msg.get("content", "").replace("\n", "\\n").replace("\r", "\\r")
    return f"[{ts_str}] {username}: {content}"


_DISCORD_EPOCH_MS = 1420070400000


def _since_to_snowflake(since: str) -> str:
    dt = datetime.fromisoformat(since)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    unix_ms = int(dt.timestamp() * 1000)
    return str((unix_ms - _DISCORD_EPOCH_MS) << 22)


def _write_output(
    data: list[dict[str, Any]] | dict[str, Any], fmt: Format = "json"
) -> None:
    if fmt == "text":
        for msg in _to_items(data):
            print(_format_text_line(msg))
    elif fmt == "jsonl":
        for msg in _to_items(data):
            print(json.dumps(msg))
    else:
        write_success(data)


async def read_channel(
    client: DiscordClient,
    *,
    channel_id: str,
    limit: int = 50,
    compact: bool = False,
    author: str | None = None,
    skip_system: bool = False,
    resolve_channels: bool = False,
    resolve_mentions: bool = False,
    max_bytes: int | None = None,
    pinned: bool = False,
    before: str | None = None,
    after: str | None = None,
    since: str | None = None,
    chronological: bool = False,
    format: Format = "json",
) -> None:
    if since and after:
        write_error(
            "incompatible_flags",
            "--since and --after are mutually exclusive",
        )
        raise SystemExit(1)
    if since:
        try:
            after = _since_to_snowflake(since)
        except ValueError:
            write_error("invalid_since", f"Invalid ISO 8601 timestamp: {since}")
            raise SystemExit(1)
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
                params["after"] = max(batch, key=_message_sort_key)["id"]
            else:
                params["before"] = batch[-1]["id"]
            if not needs_client_filter:
                params["limit"] = str(min(limit - len(all_messages), 100))

    if after:
        all_messages.sort(key=_message_sort_key)
    result = all_messages[:limit]
    if resolve_channels:
        try:
            channel_map = await _build_channel_map(client, channel_id)
        except Exception:
            channel_map = {}
        if channel_map:
            result = [_resolve_channels(msg, channel_map) for msg in result]
    if resolve_mentions:
        result = [_resolve_mentions(msg) for msg in result]
    if compact:
        result = [_compact_message(msg) for msg in result]
    if max_bytes is not None:
        total_size = _output_size(result, format)
        if total_size > max_bytes:
            kept = _truncate_to_fit(result, max_bytes, total_size, format)
            if kept is None:
                write_error(
                    "max_bytes_too_small",
                    f"--max-bytes {max_bytes} is too small for even an empty response",
                )
                raise SystemExit(1)
            if chronological and not after:
                kept.reverse()
            if format == "json":
                envelope: dict[str, Any] = {
                    "truncated": len(kept) < len(result),
                    "messages_returned": len(kept),
                    "messages_available": len(result),
                    "messages": kept,
                }
                _write_output(envelope, format)
            else:
                _write_output(kept, format)
            return
    if chronological and not after:
        result.reverse()
    _write_output(result, format)


async def read_message(
    client: DiscordClient,
    *,
    channel_id: str,
    message_id: str,
    compact: bool = False,
    format: Format = "json",
) -> None:
    msg = await client.api_get(f"/channels/{channel_id}/messages/{message_id}")
    if compact:
        msg = _compact_message(msg)
    _write_output(msg, format)


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
