from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, AsyncIterable, Mapping
from typing import Any

from ingestion.client import EthereumClient

logger = logging.getLogger(__name__)

_REQUIRED_HEADER_FIELDS = ("number", "hash", "timestamp", "parentHash")


async def stream_new_heads(client: EthereumClient) -> AsyncGenerator[dict[str, Any], None]:
    """Subscribe to Ethereum newHeads and yield normalized block headers."""
    w3 = client.w3
    if w3 is None:
        w3 = await client.connect()

    subscription = await w3.eth.subscribe("newHeads")
    try:
        async for message in _subscription_messages(w3, subscription):
            header = _extract_header(message, subscription)
            if header is None:
                continue
            yield _normalize_header(header)
    finally:
        await _unsubscribe(w3, subscription)


async def _subscription_messages(w3: Any, subscription: Any) -> AsyncGenerator[Any, None]:
    if isinstance(subscription, AsyncIterable) or hasattr(subscription, "__aiter__"):
        async for message in subscription:
            yield message
        return

    processor = _subscription_processor(w3)
    if processor is None:
        raise TypeError("newHeads subscription is not async iterable")

    async for message in processor():
        yield message


def _subscription_processor(w3: Any) -> Any:
    socket = getattr(w3, "socket", None)
    if socket is not None and hasattr(socket, "process_subscriptions"):
        return socket.process_subscriptions

    ws = getattr(w3, "ws", None)
    if ws is not None and hasattr(ws, "process_subscriptions"):
        return ws.process_subscriptions

    return None


def _extract_header(message: Any, subscription: Any) -> Mapping[str, Any] | None:
    payload = _plain_dict(message)

    params = payload.get("params")
    if isinstance(params, Mapping):
        params = _plain_dict(params)
        if not _matches_subscription(params.get("subscription"), subscription):
            return None
        result = params.get("result")
        return _plain_dict(result)

    if "result" in payload and not any(field in payload for field in _REQUIRED_HEADER_FIELDS):
        if not _matches_subscription(payload.get("subscription"), subscription):
            return None
        return _plain_dict(payload["result"])

    return payload


def _normalize_header(header: Mapping[str, Any]) -> dict[str, Any]:
    plain = _plain_dict(header)
    missing = [field for field in _REQUIRED_HEADER_FIELDS if field not in plain]
    if missing:
        raise ValueError(f"newHeads header missing required fields: {', '.join(missing)}")

    normalized = dict(plain)
    normalized["number"] = _to_int(plain["number"])
    normalized["timestamp"] = _to_int(plain["timestamp"])
    normalized["hash"] = _to_hex_string(plain["hash"])
    normalized["parentHash"] = _to_hex_string(plain["parentHash"])
    return normalized


def _plain_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {key: _plain_value(item) for key, item in value.items()}
    return dict(value)


def _plain_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _plain_dict(value)
    return value


def _to_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        return int(text, 16) if text.lower().startswith("0x") else int(text)
    if isinstance(value, bytes):
        return int.from_bytes(value, byteorder="big")
    return int(value)


def _to_hex_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return f"0x{bytes(value).hex()}"
    if hasattr(value, "hex"):
        text = value.hex()
        return text if str(text).startswith("0x") else f"0x{text}"
    return str(value)


def _matches_subscription(message_subscription: Any, subscription: Any) -> bool:
    if message_subscription is None or isinstance(subscription, AsyncIterable):
        return True
    return message_subscription == subscription


async def _unsubscribe(w3: Any, subscription: Any) -> None:
    unsubscribe = getattr(getattr(w3, "eth", None), "unsubscribe", None)
    if unsubscribe is None:
        return
    try:
        await unsubscribe(subscription)
    except Exception:
        logger.debug("newHeads unsubscribe failed; ignoring.", exc_info=True)
