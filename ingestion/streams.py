"""Block-header streaming over the WebSocket JSON-RPC subscription (Story 1A.4).

``stream_new_heads`` wraps web3.py's ``newHeads`` subscription behind a plain
async generator so downstream consumers (Track 1B decoders, Track 1C ring
buffer) receive normalized block-header dicts without knowing any WebSocket
internals.

web3.py 7.x subscription model (verified against 7.16.0): ``eth.subscribe``
returns a subscription id, and messages are consumed from the shared socket via
``w3.socket.process_subscriptions()``, which yields
``{"subscription": <id>, "result": <BlockHeader>}``. The header's ``number`` and
``timestamp`` arrive as ``int`` and ``hash``/``parentHash`` as ``HexBytes``.
"""

from __future__ import annotations

from typing import AsyncGenerator

from ingestion.client import EthereumClient


def _to_hex(value: object) -> str:
    """Normalize a ``HexBytes``/``bytes`` hash to a ``0x``-prefixed string.

    ``HexBytes.hex()`` (hexbytes 1.x) returns no ``0x`` prefix, so prepend it.
    """
    if isinstance(value, (bytes, bytearray)):
        return "0x" + bytes(value).hex()
    return "" if value is None else str(value)


async def stream_new_heads(client: EthereumClient) -> AsyncGenerator[dict, None]:
    """Subscribe to ``newHeads`` and yield normalized block-header dicts.

    Each yielded dict contains ``number`` (int), ``hash`` (str), ``timestamp``
    (int) and ``parentHash`` (str). The subscription is torn down in ``finally``
    so a consumer that breaks or cancels leaves the socket clean (AC4).
    """
    w3 = client.w3
    if w3 is None:
        raise RuntimeError(
            "EthereumClient is not connected; call connect() or use it as an "
            "async context manager before streaming."
        )
    subscription_id = await w3.eth.subscribe("newHeads")
    try:
        async for message in w3.socket.process_subscriptions():
            # process_subscriptions() is a shared socket iterator: it yields
            # messages for every subscription on this connection. Ignore any that
            # are not ours so a future logs subscription can't be mis-yielded.
            if message.get("subscription") != subscription_id:
                continue
            header = message["result"]
            yield {
                "number": header["number"],
                "hash": _to_hex(header.get("hash")),
                "timestamp": header["timestamp"],
                "parentHash": _to_hex(header.get("parentHash")),
            }
    finally:
        try:
            await w3.eth.unsubscribe(subscription_id)
        except Exception:
            pass  # best-effort: socket may already be gone on shutdown
