import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from hexbytes import HexBytes

from ingestion.streams import stream_new_heads


def _header_msg(number: int, *, hash_byte: int = 0xAB, parent_byte: int = 0xCD) -> dict:
    """Build a fake web3 v7 subscription message (shape: subscription + result)."""
    return {
        "subscription": "0xsubid",
        "result": {
            "number": number,
            "hash": HexBytes(bytes([hash_byte]) * 32),
            "timestamp": 1_651_857_000 + number,
            "parentHash": HexBytes(bytes([parent_byte]) * 32),
        },
    }


def _make_client(messages, *, block_after=False):
    """MagicMock EthereumClient whose w3 emulates the v7 subscription socket API.

    If ``block_after`` is True the async stream blocks forever after the last
    message, so cancellation/aclose paths can be exercised deterministically.
    """
    client = MagicMock()
    client.w3.eth.subscribe = AsyncMock(return_value="0xsubid")
    client.w3.eth.unsubscribe = AsyncMock(return_value=True)

    async def _stream():
        for m in messages:
            yield m
        if block_after:
            await asyncio.Event().wait()  # never resolves → simulate live socket

    client.w3.socket.process_subscriptions = MagicMock(return_value=_stream())
    return client


class TestStreamNewHeadsShape:
    async def test_yields_normalized_header_fields(self):
        client = _make_client([_header_msg(100)])

        out = [h async for h in stream_new_heads(client)]

        assert len(out) == 1
        h = out[0]
        assert h["number"] == 100
        assert isinstance(h["number"], int)
        assert h["timestamp"] == 1_651_857_100
        assert isinstance(h["timestamp"], int)
        assert h["hash"] == "0x" + "ab" * 32
        assert h["parentHash"] == "0x" + "cd" * 32

    async def test_yields_every_message_in_order(self):
        client = _make_client([_header_msg(n) for n in range(5)])

        out = [h async for h in stream_new_heads(client)]

        assert [h["number"] for h in out] == [0, 1, 2, 3, 4]

    async def test_subscribes_to_new_heads(self):
        client = _make_client([_header_msg(1)])

        _ = [h async for h in stream_new_heads(client)]

        client.w3.eth.subscribe.assert_awaited_once_with("newHeads")

    async def test_ignores_messages_from_other_subscriptions(self):
        foreign = {
            "subscription": "0xOTHER",
            "result": {
                "number": 999,
                "hash": HexBytes(b"\x00" * 32),
                "timestamp": 1,
                "parentHash": HexBytes(b"\x00" * 32),
            },
        }
        client = _make_client([foreign, _header_msg(7)])

        out = [h async for h in stream_new_heads(client)]

        assert [h["number"] for h in out] == [7]


class TestStreamNewHeadsGuards:
    async def test_raises_when_client_not_connected(self):
        client = MagicMock()
        client.w3 = None

        with pytest.raises(RuntimeError, match="not connected"):
            async for _ in stream_new_heads(client):
                pass


class TestStreamNewHeadsCleanup:
    async def test_unsubscribe_called_on_normal_exhaustion(self):
        client = _make_client([_header_msg(1)])

        _ = [h async for h in stream_new_heads(client)]

        client.w3.eth.unsubscribe.assert_awaited_once_with("0xsubid")

    async def test_aclose_triggers_cleanup(self):
        client = _make_client([_header_msg(1)], block_after=True)

        agen = stream_new_heads(client)
        first = await agen.__anext__()
        assert first["number"] == 1
        await agen.aclose()

        client.w3.eth.unsubscribe.assert_awaited_once_with("0xsubid")

    async def test_cancel_exits_cleanly_and_cleans_up(self):
        client = _make_client([_header_msg(1)], block_after=True)
        started = asyncio.Event()

        async def consume():
            async for _ in stream_new_heads(client):
                started.set()

        task = asyncio.create_task(consume())
        await asyncio.wait_for(started.wait(), timeout=1.0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        client.w3.eth.unsubscribe.assert_awaited_once_with("0xsubid")

    async def test_unsubscribe_error_is_swallowed(self):
        client = _make_client([_header_msg(1)], block_after=True)
        client.w3.eth.unsubscribe = AsyncMock(side_effect=RuntimeError("socket gone"))

        agen = stream_new_heads(client)
        await agen.__anext__()
        await agen.aclose()  # must not raise despite unsubscribe failing
