import asyncio
import json
import sys
from collections.abc import AsyncIterator, Callable
from typing import Any, cast

from discord_cli.gateway import WebSocketLike, gateway_events

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
) -> None:
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

    print(
        "[warning] WebSocket streaming increases detection risk. See SPEC.md.",
        file=sys.stderr,
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
        print(
            f"[reconnect] Connection lost — retrying in {delay}s ({attempt + 1}/{_MAX_RECONNECTS})",
            file=sys.stderr,
        )
        await asyncio.sleep(delay)

    print("[error] Max reconnection attempts reached", file=sys.stderr)
