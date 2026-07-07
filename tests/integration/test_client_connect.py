import socket

import pytest

from ingestion.client import EthereumClient
from ingestion.config import IngestionConfig


def is_port_open(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("localhost", port)) == 0


pytestmark = pytest.mark.skipif(
    not is_port_open(8546),
    reason="mock WSS not running on :8546",
)


async def test_client_connects_to_mock_wss():
    cfg = IngestionConfig(wss_url="ws://localhost:8546")
    async with EthereumClient(cfg) as client:
        assert client.w3 is not None
