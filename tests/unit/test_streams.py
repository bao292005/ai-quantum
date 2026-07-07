from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from hexbytes import HexBytes

from ingestion.streams import stream_new_heads


class _AttributeDictLike(dict):
    pass


class _AsyncSubscription:
    def __init__(self, headers):
        self._headers = list(headers)

    def __aiter__(self):
        self._iter = iter(self._headers)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


def _client_for(subscription, unsubscribe=None):
    eth = SimpleNamespace(
        subscribe=AsyncMock(return_value=subscription),
        unsubscribe=unsubscribe or AsyncMock(),
    )
    return SimpleNamespace(w3=SimpleNamespace(eth=eth))


async def test_stream_new_heads_yields_normalized_header():
    subscription = _AsyncSubscription(
        [
            _AttributeDictLike(
                {
                    "number": "0x10",
                    "hash": HexBytes("0x" + "12" * 32),
                    "timestamp": "0x64",
                    "parentHash": bytes.fromhex("34" * 32),
                    "extra": "kept",
                }
            )
        ]
    )
    client = _client_for(subscription)

    agen = stream_new_heads(client)
    header = await anext(agen)
    await agen.aclose()

    assert header["number"] == 16
    assert header["timestamp"] == 100
    assert header["hash"] == "0x" + "12" * 32
    assert header["parentHash"] == "0x" + "34" * 32
    assert header["extra"] == "kept"


async def test_stream_new_heads_has_required_fields():
    subscription = _AsyncSubscription(
        [
            {
                "number": 1,
                "hash": "0xabc",
                "timestamp": 2,
                "parentHash": "0xdef",
            }
        ]
    )
    client = _client_for(subscription)

    agen = stream_new_heads(client)
    header = await anext(agen)
    await agen.aclose()

    assert {"number", "hash", "timestamp", "parentHash"}.issubset(header)


async def test_stream_new_heads_converts_hex_numbers_to_int():
    subscription = _AsyncSubscription(
        [
            {
                "number": "0xff",
                "hash": "0xabc",
                "timestamp": "0x65",
                "parentHash": "0xdef",
            }
        ]
    )
    client = _client_for(subscription)

    agen = stream_new_heads(client)
    header = await anext(agen)
    await agen.aclose()

    assert header["number"] == 255
    assert header["timestamp"] == 101


async def test_stream_new_heads_unwraps_subscription_notification():
    subscription = _AsyncSubscription(
        [
            {
                "jsonrpc": "2.0",
                "method": "eth_subscription",
                "params": {
                    "subscription": "0x1",
                    "result": {
                        "number": "0x2",
                        "hash": "0xabc",
                        "timestamp": "0x3",
                        "parentHash": "0xdef",
                    },
                },
            }
        ]
    )
    client = _client_for(subscription)

    agen = stream_new_heads(client)
    header = await anext(agen)
    await agen.aclose()

    assert header["number"] == 2
    assert header["timestamp"] == 3


async def test_stream_new_heads_break_does_not_raise_or_disconnect():
    unsubscribe = AsyncMock(side_effect=RuntimeError("already gone"))
    provider = SimpleNamespace(disconnect=AsyncMock())
    subscription = _AsyncSubscription(
        [
            {
                "number": 1,
                "hash": "0xabc",
                "timestamp": 2,
                "parentHash": "0xdef",
            }
        ]
    )
    client = _client_for(subscription, unsubscribe=unsubscribe)
    client.w3.provider = provider

    async for _header in stream_new_heads(client):
        break

    provider.disconnect.assert_not_called()
