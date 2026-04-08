import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any, cast

from discord_cli.gateway import WebSocketLike, gateway_events
from discord_cli.output import set_quiet, write_status

_MAX_RECONNECTS = 5
_MAX_BACKOFF = 30


async def stream_events(
    *,
    token: str,
    gateway_url: str,
    channel_id: str | None = None,
    guild_id: str | None = None,
    event_type: str | None = None,
    event_source: AsyncIterator[dict[str, Any]] | None = None,
    ws_connect: Callable[..., Any] | None = None,
    quiet: bool = False,
) -> None:
    set_quiet(quiet)
    async def _consume(source: AsyncIterator[dict[str, Any]]) -> None:
        async for event in source:
            if channel_id and event.get("channel_id") != channel_id:
                continue
            if guild_id and event.get("guild_id") != guild_id:
                continue
            if event_type and event.get("event") != event_type:
                continue
            print(json.dumps(event), flush=True)

    if event_source is not None:
        await _consume(event_source)
        return

    write_status(
        "[warning] WebSocket streaming increases detection risk. See SPEC.md."
    )

    if ws_connect is None:
        import websockets
        ws_connect = websockets.connect

    from websockets.exceptions import WebSocketException

    url = f"{gateway_url}?v=10&encoding=json"
    for attempt in range(_MAX_RECONNECTS):
        try:
            async with ws_connect(url) as ws:
                await _consume(gateway_events(token, cast(WebSocketLike, ws)))
        except (OSError, WebSocketException):
            pass
        if attempt + 1 >= _MAX_RECONNECTS:
            break
        delay = min(2**attempt, _MAX_BACKOFF)
        write_status(
            f"[reconnect] Connection lost — retrying in {delay}s ({attempt + 1}/{_MAX_RECONNECTS})"
        )
        await asyncio.sleep(delay)

    msg = "Max reconnection attempts reached"
    raise ConnectionError(msg)
