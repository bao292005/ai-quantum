import asyncio
import logging
from dataclasses import dataclass, field

from web3 import AsyncWeb3
from web3.providers import WebSocketProvider

from ingestion.config import IngestionConfig

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 3.0


@dataclass
class EthereumClient:
    cfg: IngestionConfig
    w3: AsyncWeb3 | None = field(default=None, init=False)

    async def connect(self) -> AsyncWeb3:
        if self.w3 is not None:
            return self.w3
        provider = WebSocketProvider(
            self.cfg.wss_url,
            websocket_timeout=_CONNECT_TIMEOUT,
        )
        w3 = AsyncWeb3(provider)
        try:
            await asyncio.wait_for(w3.provider.connect(), timeout=_CONNECT_TIMEOUT)
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as exc:
            raise ConnectionError(
                f"Cannot connect to {self.cfg.wss_url}: {exc}"
            ) from exc
        self.w3 = w3
        return self.w3

    async def disconnect(self) -> None:
        if self.w3 and self.w3.provider:
            try:
                await self.w3.provider.disconnect()
            except Exception:
                logger.debug("Provider disconnect raised an error; ignoring.", exc_info=True)
        self.w3 = None

    async def __aenter__(self) -> "EthereumClient":
        await self.connect()
        return self

    async def __aexit__(self, *_) -> None:
        await self.disconnect()
