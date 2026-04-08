import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from discord_cli.client import DiscordClient

_OP_DISPATCH = 0
_OP_HEARTBEAT = 1
_OP_IDENTIFY = 2


@runtime_checkable
class WebSocketLike(Protocol):
    async def recv(self) -> str | bytes: ...
    async def send(self, data: str) -> None: ...
    def __aiter__(self) -> AsyncIterator[str | bytes]: ...
    async def __anext__(self) -> str | bytes: ...

_GUILD_MESSAGES = 1 << 9
_DIRECT_MESSAGES = 1 << 12
_MESSAGE_CONTENT = 1 << 15
_DEFAULT_INTENTS = _GUILD_MESSAGES | _DIRECT_MESSAGES | _MESSAGE_CONTENT
_HEARTBEAT_PAYLOAD = json.dumps({"op": _OP_HEARTBEAT, "d": None})


async def get_gateway_url(client: DiscordClient) -> str:
    data = await client.api_get("/gateway")
    return data["url"]


async def gateway_events(
    token: str, ws: WebSocketLike,
) -> AsyncIterator[dict[str, Any]]:
    hello_raw = await ws.recv()
    hello = json.loads(hello_raw)
    heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000

    identify = {
        "op": _OP_IDENTIFY,
        "d": {
            "token": token,
            "properties": {
                "os": "linux",
                "browser": "discord-cli",
                "device": "discord-cli",
            },
            "intents": _DEFAULT_INTENTS,
        },
    }
    await ws.send(json.dumps(identify))

    async def _heartbeat() -> None:
        while True:
            await asyncio.sleep(heartbeat_interval)
            await ws.send(_HEARTBEAT_PAYLOAD)

    task = asyncio.create_task(_heartbeat())
    try:
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("op") == _OP_DISPATCH and isinstance(msg.get("d"), dict):
                yield {"event": msg["t"], **msg["d"]}
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
