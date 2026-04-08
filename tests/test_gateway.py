import asyncio
import json

import httpx

from discord_cli.client import DiscordClient
from discord_cli.gateway import gateway_events, get_gateway_url


class MockWebSocket:
    def __init__(self, incoming: list[str]) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        for msg in incoming:
            self._queue.put_nowait(msg)
        self.sent: list[str] = []

    async def recv(self) -> str:
        return self._queue.get_nowait()

    async def send(self, data: str) -> None:
        self.sent.append(data)

    def __aiter__(self) -> "MockWebSocket":
        return self

    async def __anext__(self) -> str:
        if self._queue.empty():
            raise StopAsyncIteration
        return self._queue.get_nowait()


async def test_get_gateway_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v10/gateway"
        return httpx.Response(200, json={"url": "wss://gateway.discord.gg"})

    transport = httpx.MockTransport(handler)
    async with DiscordClient(token="test", transport=transport) as client:
        url = await get_gateway_url(client)
    assert url == "wss://gateway.discord.gg"


async def test_gateway_events_yields_dispatch_and_sends_identify() -> None:
    hello = json.dumps({"op": 10, "d": {"heartbeat_interval": 45000}})
    dispatch = json.dumps({
        "op": 0,
        "t": "MESSAGE_CREATE",
        "d": {"channel_id": "111", "content": "hello"},
    })
    ws = MockWebSocket([hello, dispatch])

    events = []
    async for event in gateway_events("my-token", ws):
        events.append(event)

    assert len(events) == 1
    assert events[0] == {"event": "MESSAGE_CREATE", "channel_id": "111", "content": "hello"}

    identify = json.loads(ws.sent[0])
    assert identify["op"] == 2
    assert identify["d"]["token"] == "my-token"
    assert "properties" in identify["d"]


class DelayedMockWebSocket:
    def __init__(self, incoming: list[str], delay: float) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        for msg in incoming:
            self._queue.put_nowait(msg)
        self.sent: list[str] = []
        self._delay = delay
        self._yielded_first = False

    async def recv(self) -> str:
        return self._queue.get_nowait()

    async def send(self, data: str) -> None:
        self.sent.append(data)

    def __aiter__(self) -> "DelayedMockWebSocket":
        return self

    async def __anext__(self) -> str:
        if not self._yielded_first:
            await asyncio.sleep(self._delay)
            self._yielded_first = True
        if self._queue.empty():
            raise StopAsyncIteration
        return self._queue.get_nowait()


async def test_gateway_sends_heartbeat() -> None:
    hello = json.dumps({"op": 10, "d": {"heartbeat_interval": 50}})
    dispatch = json.dumps({
        "op": 0,
        "t": "READY",
        "d": {"session_id": "abc"},
    })
    ws = DelayedMockWebSocket([hello, dispatch], delay=0.1)

    async for _ in gateway_events("tok", ws):
        pass

    parsed = [json.loads(m) for m in ws.sent]
    heartbeats = [p for p in parsed if p.get("op") == 1]
    assert len(heartbeats) >= 1
    assert heartbeats[0] == {"op": 1, "d": None}


async def test_gateway_preserves_payload_type_field() -> None:
    hello = json.dumps({"op": 10, "d": {"heartbeat_interval": 45000}})
    dispatch = json.dumps({
        "op": 0,
        "t": "MESSAGE_CREATE",
        "d": {"channel_id": "111", "content": "hi", "type": 0},
    })
    ws = MockWebSocket([hello, dispatch])

    events = []
    async for event in gateway_events("tok", ws):
        events.append(event)

    assert events[0]["event"] == "MESSAGE_CREATE"
    assert events[0]["type"] == 0
