from __future__ import annotations

import asyncio
import socket

import pytest

from ingestion.client import EthereumClient
from ingestion.config import IngestionConfig
from ingestion.streams import stream_new_heads


def is_mock_wss_up() -> bool:
    with socket.socket() as sock:
        return sock.connect_ex(("localhost", 8546)) == 0


pytestmark = pytest.mark.skipif(
    not is_mock_wss_up(),
    reason="mock WSS not running on :8546",
)


async def test_stream_new_heads_receives_at_least_five_headers():
    cfg = IngestionConfig(wss_url="ws://localhost:8546")
    headers = []
    deadline = asyncio.get_event_loop().time() + 10.0

    async with EthereumClient(cfg) as client:
        async for head in stream_new_heads(client):
            headers.append(head)
            if len(headers) >= 5 or asyncio.get_event_loop().time() >= deadline:
                break

    assert len(headers) >= 5
    for header in headers:
        assert {"number", "hash", "timestamp", "parentHash"}.issubset(header)
        assert isinstance(header["number"], int)
        assert isinstance(header["timestamp"], int)
        assert isinstance(header["hash"], str)
        assert isinstance(header["parentHash"], str)
