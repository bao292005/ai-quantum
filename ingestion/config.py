import os
from dataclasses import dataclass


class ConfigError(Exception):
    pass


@dataclass
class IngestionConfig:
    wss_url: str
    wss_fallback_url: str | None = None
    alchemy_key: str | None = None
    etherscan_api_key: str | None = None


def load() -> IngestionConfig:
    wss_url = os.environ.get("WSS_URL", "").strip()
    if not wss_url:
        raise ConfigError("WSS_URL is required but not set or empty")
    return IngestionConfig(
        wss_url=wss_url,
        wss_fallback_url=os.environ.get("WSS_FALLBACK_URL") or None,
        alchemy_key=os.environ.get("ALCHEMY_KEY") or None,
        etherscan_api_key=os.environ.get("ETHERSCAN_API_KEY") or None,
    )
