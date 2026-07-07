import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ingestion.client import EthereumClient
from ingestion.config import IngestionConfig


@pytest.fixture
def cfg():
    return IngestionConfig(wss_url="wss://localhost:8546")


def _make_mocks():
    """Return (mock_provider, mock_w3) with async connect/disconnect."""
    mock_provider = MagicMock()
    mock_provider.connect = AsyncMock()
    mock_provider.disconnect = AsyncMock()

    mock_w3 = MagicMock()
    mock_w3.provider = mock_provider
    return mock_provider, mock_w3


class TestEthereumClientConnect:
    async def test_connect_success_returns_w3(self, cfg):
        mock_provider, mock_w3 = _make_mocks()

        with patch("ingestion.client.WebSocketProvider", return_value=mock_provider), \
             patch("ingestion.client.AsyncWeb3", return_value=mock_w3):

            client = EthereumClient(cfg)
            result = await client.connect()

        assert result is mock_w3
        assert client.w3 is mock_w3
        mock_provider.connect.assert_called_once()

    async def test_connect_timeout_raises_connection_error(self, cfg):
        mock_provider, mock_w3 = _make_mocks()
        mock_provider.connect = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("ingestion.client.WebSocketProvider", return_value=mock_provider), \
             patch("ingestion.client.AsyncWeb3", return_value=mock_w3):

            client = EthereumClient(cfg)
            with pytest.raises(ConnectionError, match="Cannot connect"):
                await client.connect()

    async def test_connect_connection_refused_raises_connection_error(self, cfg):
        mock_provider, mock_w3 = _make_mocks()
        mock_provider.connect = AsyncMock(side_effect=ConnectionRefusedError())

        with patch("ingestion.client.WebSocketProvider", return_value=mock_provider), \
             patch("ingestion.client.AsyncWeb3", return_value=mock_w3):

            client = EthereumClient(cfg)
            with pytest.raises(ConnectionError):
                await client.connect()

    async def test_connect_os_error_raises_connection_error(self, cfg):
        mock_provider, mock_w3 = _make_mocks()
        mock_provider.connect = AsyncMock(side_effect=OSError("network unreachable"))

        with patch("ingestion.client.WebSocketProvider", return_value=mock_provider), \
             patch("ingestion.client.AsyncWeb3", return_value=mock_w3):

            client = EthereumClient(cfg)
            with pytest.raises(ConnectionError):
                await client.connect()

    async def test_connect_stores_w3_on_client(self, cfg):
        mock_provider, mock_w3 = _make_mocks()

        with patch("ingestion.client.WebSocketProvider", return_value=mock_provider), \
             patch("ingestion.client.AsyncWeb3", return_value=mock_w3):

            client = EthereumClient(cfg)
            assert client.w3 is None
            await client.connect()
            assert client.w3 is mock_w3


class TestEthereumClientDisconnect:
    async def test_disconnect_clears_w3(self, cfg):
        mock_provider, mock_w3 = _make_mocks()

        with patch("ingestion.client.WebSocketProvider", return_value=mock_provider), \
             patch("ingestion.client.AsyncWeb3", return_value=mock_w3):

            client = EthereumClient(cfg)
            await client.connect()
            await client.disconnect()

        assert client.w3 is None
        mock_provider.disconnect.assert_called_once()

    async def test_disconnect_when_not_connected_is_safe(self, cfg):
        client = EthereumClient(cfg)
        await client.disconnect()  # should not raise
        assert client.w3 is None

    async def test_disconnect_swallows_provider_exceptions(self, cfg):
        mock_provider, mock_w3 = _make_mocks()
        mock_provider.disconnect = AsyncMock(side_effect=RuntimeError("already closed"))

        with patch("ingestion.client.WebSocketProvider", return_value=mock_provider), \
             patch("ingestion.client.AsyncWeb3", return_value=mock_w3):

            client = EthereumClient(cfg)
            await client.connect()
            await client.disconnect()  # must not raise

        assert client.w3 is None


class TestEthereumClientContextManager:
    async def test_aenter_returns_client(self, cfg):
        mock_provider, mock_w3 = _make_mocks()

        with patch("ingestion.client.WebSocketProvider", return_value=mock_provider), \
             patch("ingestion.client.AsyncWeb3", return_value=mock_w3):

            async with EthereumClient(cfg) as client:
                assert isinstance(client, EthereumClient)
                assert client.w3 is mock_w3

    async def test_aexit_disconnects(self, cfg):
        mock_provider, mock_w3 = _make_mocks()

        with patch("ingestion.client.WebSocketProvider", return_value=mock_provider), \
             patch("ingestion.client.AsyncWeb3", return_value=mock_w3):

            async with EthereumClient(cfg) as client:
                pass

        assert client.w3 is None
        mock_provider.disconnect.assert_called_once()
