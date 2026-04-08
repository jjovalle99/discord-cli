import asyncio
import io
import json
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, redirect_stdout
from typing import Annotated

import cyclopts
import httpx

from discord_cli.cache import run_with_cache
from discord_cli.client import DiscordClient
from discord_cli.commands.list import (
    list_channels,
    list_dms,
    list_members,
    list_servers,
    list_threads,
)
from discord_cli.commands.read import (
    Format,
    read_channel,
    read_channel_info,
    read_file,
    read_member,
    read_message,
    read_server_info,
    read_user,
)
from discord_cli.commands.search import search_dms, search_messages
from discord_cli.config import DEFAULT_CONFIG_PATH
from discord_cli.tokens import resolve_token
from discord_cli.validation import validate_token

app = cyclopts.App(name="discord-cli", help="Read-only Discord CLI for coding agents.")
search_app = cyclopts.App(name="search", help="Search Discord data.")
read_app = cyclopts.App(name="read", help="Read Discord data.")
list_app = cyclopts.App(name="list", help="List Discord data.")
stream_app = cyclopts.App(name="stream", help="Stream real-time Discord events via WebSocket gateway.")
app.command(search_app)
app.command(read_app)
app.command(list_app)
app.command(stream_app)


def _fail(error: str, message: str) -> None:
    from discord_cli.output import write_error

    write_error(error, message)
    raise SystemExit(1)


def _run_with_error_handling(fn: Callable[[], object]) -> None:
    import subprocess

    from discord_cli.auth.errors import AuthError
    from discord_cli.client import DiscordAPIError

    try:
        fn()
    except AuthError as e:
        _fail("auth_error", str(e))
    except DiscordAPIError as e:
        _fail("discord_api_error", str(e))
    except (ValueError, UnicodeDecodeError) as e:
        _fail("auth_error", f"Token decryption failed: {e}")
    except subprocess.CalledProcessError as e:
        _fail("auth_error", f"Keychain access failed: {e}")
    except TimeoutError as e:
        _fail("timeout", str(e))


@app.command
def auth() -> None:
    """Extract token from Discord desktop app and save to config."""
    from discord_cli.auth.command import run_auth

    _run_with_error_handling(lambda: asyncio.run(run_auth()))


@app.command
def whoami(
    *,
    token: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    """Show which user is authenticated and how the token was resolved."""
    from discord_cli.commands.whoami import whoami as _whoami

    resolved = resolve_token(flag_token=token, config_path=DEFAULT_CONFIG_PATH)

    async def _inner() -> None:
        async with DiscordClient(
            token=resolved.value, transport=transport
        ) as client:
            await _whoami(client, token_source=resolved.source)

    _run_with_error_handling(lambda: asyncio.run(_inner()))


@asynccontextmanager
async def _get_client(
    token: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[DiscordClient]:
    from discord_cli.super_properties import (
        build_super_properties,
        get_cached_build_number,
    )

    build_number = get_cached_build_number()
    sp = build_super_properties(build_number) if build_number is not None else None
    async with DiscordClient(
        token=token, transport=transport, super_properties=sp
    ) as client:
        await validate_token(client)
        yield client


def _run(
    fn: Callable[[DiscordClient], Awaitable[object]],
    token: str | None,
    transport: httpx.AsyncBaseTransport | None = None,
    cache_ttl: int = 0,
    no_cache: bool = False,
    rate_limit_info: bool = False,
) -> None:
    resolved = resolve_token(flag_token=token, config_path=DEFAULT_CONFIG_PATH)
    captured_client: DiscordClient | None = None

    async def _inner() -> None:
        nonlocal captured_client
        async with _get_client(resolved.value, transport=transport) as client:
            captured_client = client
            await fn(client)

    def _execute() -> None:
        _run_with_error_handling(lambda: asyncio.run(_inner()))

    if rate_limit_info:
        buf = io.StringIO()
        with redirect_stdout(buf):
            _execute()
        raw = buf.getvalue()
        if raw.strip() and captured_client is not None:
            stats = captured_client.rate_limit_stats
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                sys.stdout.write(raw)
                print(json.dumps({"_rate_limit": stats}), file=sys.stderr)
                return
            print(json.dumps({"data": data, "_rate_limit": stats}, indent=2))
        elif raw:
            sys.stdout.write(raw)
    else:
        run_with_cache(
            _execute,
            argv=sys.argv,
            cache_ttl=cache_ttl,
            no_cache=no_cache,
            token=resolved.value,
        )


@search_app.command(name="messages")
def search_messages_cmd(
    guild_id: str,
    query: str,
    *,
    limit: int = 25,
    channel: Annotated[str | None, cyclopts.Parameter(name=["--channel", "--channel-id"])] = None,
    author_id: str | None = None,
    has: str | None = None,
    sort_by: str = "timestamp",
    sort_order: str = "desc",
    offset: int = 0,
    fallback_read: bool = False,
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """Search messages in a server."""
    _run(
        lambda c: search_messages(
            c,
            guild_id=guild_id,
            query=query,
            limit=limit,
            channel_id=channel,
            author_id=author_id,
            has=has,
            sort_by=sort_by,
            sort_order=sort_order,
            offset=offset,
            fallback_read=fallback_read,
        ),
        token,
        cache_ttl=cache_ttl,
        no_cache=no_cache,
        rate_limit_info=rate_limit_info,
    )


@search_app.command(name="dms")
def search_dms_cmd(
    channel_id: str,
    query: str,
    *,
    limit: int = 25,
    fallback_read: bool = False,
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """Search messages in a DM channel."""
    _run(
        lambda c: search_dms(
            c,
            channel_id=channel_id,
            query=query,
            limit=limit,
            fallback_read=fallback_read,
        ),
        token,
        cache_ttl=cache_ttl,
        no_cache=no_cache,
        rate_limit_info=rate_limit_info,
    )


@list_app.command(name="servers")
def list_servers_cmd(
    *,
    limit: int = 200,
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """List all servers the user is in."""
    _run(lambda c: list_servers(c, limit=limit), token, cache_ttl=cache_ttl, no_cache=no_cache, rate_limit_info=rate_limit_info)


@list_app.command(name="channels")
def list_channels_cmd(
    guild_id: str,
    *,
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """List all channels in a server."""
    _run(lambda c: list_channels(c, guild_id=guild_id), token, cache_ttl=cache_ttl, no_cache=no_cache, rate_limit_info=rate_limit_info)


@list_app.command(name="dms")
def list_dms_cmd(
    *,
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """List open DM conversations."""
    _run(lambda c: list_dms(c), token, cache_ttl=cache_ttl, no_cache=no_cache, rate_limit_info=rate_limit_info)


@list_app.command(name="members")
def list_members_cmd(
    guild_id: str,
    *,
    role: str | None = None,
    limit: int = 1000,
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """List members in a server."""
    _run(lambda c: list_members(c, guild_id=guild_id, limit=limit, role=role), token, cache_ttl=cache_ttl, no_cache=no_cache, rate_limit_info=rate_limit_info)


@list_app.command(name="threads")
def list_threads_cmd(
    channel_id: str,
    *,
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """List threads in a channel (archived + active from recent messages)."""
    _run(lambda c: list_threads(c, channel_id=channel_id), token, cache_ttl=cache_ttl, no_cache=no_cache, rate_limit_info=rate_limit_info)


@read_app.command(name="channel")
def read_channel_cmd(
    channel_id: str,
    *,
    limit: int = 50,
    compact: bool = False,
    author: str | None = None,
    skip_system: bool = False,
    resolve_channels: bool = False,
    resolve_mentions: bool = False,
    flatten_embeds: bool = False,
    max_bytes: int | None = None,
    pinned: bool = False,
    before: str | None = None,
    after: str | None = None,
    since: str | None = None,
    chronological: bool = False,
    format: Format = "json",
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """Fetch message history of a channel or thread."""
    _run(
        lambda c: read_channel(
            c,
            channel_id=channel_id,
            limit=limit,
            compact=compact,
            author=author,
            skip_system=skip_system,
            resolve_channels=resolve_channels,
            resolve_mentions=resolve_mentions,
            flatten_embeds=flatten_embeds,
            max_bytes=max_bytes,
            pinned=pinned,
            before=before,
            after=after,
            since=since,
            chronological=chronological,
            format=format,
        ),
        token,
        cache_ttl=cache_ttl,
        no_cache=no_cache,
        rate_limit_info=rate_limit_info,
    )


@read_app.command(name="thread")
def read_thread_cmd(
    thread_id: str,
    *,
    limit: int = 50,
    compact: bool = False,
    author: str | None = None,
    skip_system: bool = False,
    resolve_channels: bool = False,
    resolve_mentions: bool = False,
    flatten_embeds: bool = False,
    max_bytes: int | None = None,
    pinned: bool = False,
    before: str | None = None,
    after: str | None = None,
    since: str | None = None,
    chronological: bool = False,
    format: Format = "json",
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """Fetch messages in a thread (alias for read channel)."""
    _run(
        lambda c: read_channel(
            c,
            channel_id=thread_id,
            limit=limit,
            compact=compact,
            author=author,
            skip_system=skip_system,
            resolve_channels=resolve_channels,
            resolve_mentions=resolve_mentions,
            flatten_embeds=flatten_embeds,
            max_bytes=max_bytes,
            pinned=pinned,
            before=before,
            after=after,
            since=since,
            chronological=chronological,
            format=format,
        ),
        token,
        cache_ttl=cache_ttl,
        no_cache=no_cache,
        rate_limit_info=rate_limit_info,
    )


@read_app.command(name="message")
def read_message_cmd(
    channel_id: str,
    message_id: str,
    *,
    compact: bool = False,
    flatten_embeds: bool = False,
    format: Format = "json",
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """Fetch a single message."""
    _run(
        lambda c: read_message(
            c,
            channel_id=channel_id,
            message_id=message_id,
            compact=compact,
            flatten_embeds=flatten_embeds,
            format=format,
        ),
        token,
        cache_ttl=cache_ttl,
        no_cache=no_cache,
        rate_limit_info=rate_limit_info,
    )


@read_app.command(name="server-info")
def read_server_info_cmd(
    guild_id: str,
    *,
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """Fetch server metadata."""
    _run(lambda c: read_server_info(c, guild_id=guild_id), token, cache_ttl=cache_ttl, no_cache=no_cache, rate_limit_info=rate_limit_info)


@read_app.command(name="channel-info")
def read_channel_info_cmd(
    channel_id: str,
    *,
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """Fetch channel metadata."""
    _run(lambda c: read_channel_info(c, channel_id=channel_id), token, cache_ttl=cache_ttl, no_cache=no_cache, rate_limit_info=rate_limit_info)


@read_app.command(name="user")
def read_user_cmd(
    user_id: str,
    *,
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """Fetch a user's profile."""
    _run(lambda c: read_user(c, user_id=user_id), token, cache_ttl=cache_ttl, no_cache=no_cache, rate_limit_info=rate_limit_info)


@read_app.command(name="member")
def read_member_cmd(
    guild_id: str,
    user_id: str,
    *,
    rate_limit_info: bool = False,
    cache_ttl: int = 0,
    no_cache: bool = False,
    token: str | None = None,
) -> None:
    """Fetch a member's server-specific profile."""
    _run(lambda c: read_member(c, guild_id=guild_id, user_id=user_id), token, cache_ttl=cache_ttl, no_cache=no_cache, rate_limit_info=rate_limit_info)


@read_app.command(name="file")
def read_file_cmd(
    *,
    url: str | None = None,
    channel: str | None = None,
    message: str | None = None,
    filename: str | None = None,
    output: str | None = None,
    token: str | None = None,
) -> None:
    """Download an attachment by URL or by message reference."""
    from pathlib import Path as P

    async def _download(c: DiscordClient) -> None:
        data = await read_file(
            c, url=url, channel=channel, message=message, filename=filename
        )
        if output:
            P(output).write_bytes(data)
        else:
            import sys

            sys.stdout.buffer.write(data)

    _run(_download, token)


def _run_stream(
    fn: Callable[[str, str], Awaitable[None]],
    token_flag: str | None,
) -> None:
    resolved = resolve_token(flag_token=token_flag, config_path=DEFAULT_CONFIG_PATH)

    async def _inner() -> None:
        from discord_cli.gateway import get_gateway_url

        async with DiscordClient(token=resolved.value) as client:
            url = await get_gateway_url(client)
        await fn(resolved.value, url)

    try:
        _run_with_error_handling(lambda: asyncio.run(_inner()))
    except KeyboardInterrupt:
        raise SystemExit(130)


@stream_app.command(name="channel")
def stream_channel_cmd(
    channel_id: str,
    *,
    event: str | None = None,
    token: str | None = None,
) -> None:
    """Stream real-time events for a channel."""
    from discord_cli.commands.stream import stream_events

    _run_stream(
        lambda tok, url: stream_events(
            token=tok, gateway_url=url, channel_id=channel_id, event_type=event,
        ),
        token,
    )


@stream_app.command(name="server")
def stream_server_cmd(
    guild_id: str,
    *,
    event: str | None = None,
    token: str | None = None,
) -> None:
    """Stream real-time events for all channels in a server."""
    from discord_cli.commands.stream import stream_events

    _run_stream(
        lambda tok, url: stream_events(
            token=tok, gateway_url=url, guild_id=guild_id, event_type=event,
        ),
        token,
    )


def main() -> None:
    app()
