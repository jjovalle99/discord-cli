import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from discord_cli.commands.stream import stream_events


async def _make_source(events: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for event in events:
        yield event


async def test_stream_channel_filters_by_channel_id(capsys: pytest.CaptureFixture[str]) -> None:
    events = [
        {"event": "MESSAGE_CREATE", "channel_id": "111", "content": "match"},
        {"event": "MESSAGE_CREATE", "channel_id": "222", "content": "no match"},
        {"event": "MESSAGE_CREATE", "channel_id": "111", "content": "match2"},
    ]

    await stream_events(
        token="tok",
        gateway_url="wss://gateway.discord.gg",
        channel_id="111",
        event_source=_make_source(events),
    )

    lines = capsys.readouterr().out.strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["content"] == "match"
    assert json.loads(lines[1])["content"] == "match2"


async def test_stream_server_filters_by_guild_id(capsys: pytest.CaptureFixture[str]) -> None:
    events = [
        {"event": "MESSAGE_CREATE", "guild_id": "aaa", "content": "yes"},
        {"event": "MESSAGE_CREATE", "guild_id": "bbb", "content": "no"},
    ]

    await stream_events(
        token="tok",
        gateway_url="wss://gateway.discord.gg",
        guild_id="aaa",
        event_source=_make_source(events),
    )

    lines = capsys.readouterr().out.strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0])["content"] == "yes"


async def test_stream_filters_by_event_type(capsys: pytest.CaptureFixture[str]) -> None:
    events = [
        {"event": "MESSAGE_CREATE", "channel_id": "111", "content": "msg"},
        {"event": "TYPING_START", "channel_id": "111"},
        {"event": "MESSAGE_CREATE", "channel_id": "111", "content": "msg2"},
    ]

    await stream_events(
        token="tok",
        gateway_url="wss://gateway.discord.gg",
        channel_id="111",
        event_type="MESSAGE_CREATE",
        event_source=_make_source(events),
    )

    lines = capsys.readouterr().out.strip().split("\n")
    assert len(lines) == 2
    for line in lines:
        assert json.loads(line)["event"] == "MESSAGE_CREATE"


async def test_stream_reconnects_on_failure(capsys: pytest.CaptureFixture[str]) -> None:
    call_count = 0

    class FailOnceConnect:
        def __init__(self, _url: str) -> None:
            pass

        async def __aenter__(self) -> "FailOnceConnect":
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("dropped")
            return self

        async def __aexit__(self, *_: object) -> None:
            pass

        async def recv(self) -> str:
            return json.dumps({"op": 10, "d": {"heartbeat_interval": 45000}})

        async def send(self, _data: str) -> None:
            pass

        def __aiter__(self) -> "FailOnceConnect":
            return self

        async def __anext__(self) -> str:
            raise StopAsyncIteration

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await stream_events(
            token="tok",
            gateway_url="wss://gateway.discord.gg",
            channel_id="111",
            ws_connect=FailOnceConnect,
        )

    assert call_count >= 2
    stderr = capsys.readouterr().err
    assert "[reconnect]" in stderr
