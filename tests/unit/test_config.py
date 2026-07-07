import pytest

from ingestion.config import ConfigError, IngestionConfig, load


def test_load_success(monkeypatch):
    monkeypatch.setenv("WSS_URL", "wss://localhost:8546")
    monkeypatch.delenv("WSS_FALLBACK_URL", raising=False)
    monkeypatch.delenv("ALCHEMY_KEY", raising=False)
    monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)

    cfg = load()

    assert cfg.wss_url == "wss://localhost:8546"
    assert cfg.wss_fallback_url is None
    assert cfg.alchemy_key is None
    assert cfg.etherscan_api_key is None


def test_load_all_fields(monkeypatch):
    monkeypatch.setenv("WSS_URL", "wss://eth-mainnet.g.alchemy.com/v2/abc123")
    monkeypatch.setenv("WSS_FALLBACK_URL", "wss://mainnet.infura.io/ws/v3/xyz")
    monkeypatch.setenv("ALCHEMY_KEY", "abc123")
    monkeypatch.setenv("ETHERSCAN_API_KEY", "D2W8TK696S")

    cfg = load()

    assert cfg.wss_url == "wss://eth-mainnet.g.alchemy.com/v2/abc123"
    assert cfg.wss_fallback_url == "wss://mainnet.infura.io/ws/v3/xyz"
    assert cfg.alchemy_key == "abc123"
    assert cfg.etherscan_api_key == "D2W8TK696S"


def test_load_missing_wss_url(monkeypatch):
    monkeypatch.delenv("WSS_URL", raising=False)

    with pytest.raises(ConfigError, match="WSS_URL"):
        load()


def test_load_empty_wss_url(monkeypatch):
    monkeypatch.setenv("WSS_URL", "   ")

    with pytest.raises(ConfigError, match="WSS_URL"):
        load()


def test_load_optional_fields_default_none(monkeypatch):
    monkeypatch.setenv("WSS_URL", "wss://localhost:8546")
    monkeypatch.delenv("WSS_FALLBACK_URL", raising=False)
    monkeypatch.delenv("ALCHEMY_KEY", raising=False)
    monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)

    cfg = load()

    assert cfg.wss_fallback_url is None
    assert cfg.alchemy_key is None
    assert cfg.etherscan_api_key is None


def test_ingestion_config_is_dataclass():
    cfg = IngestionConfig(wss_url="wss://localhost:8546")
    assert cfg.wss_url == "wss://localhost:8546"
    assert cfg.wss_fallback_url is None


def test_config_error_is_exception():
    err = ConfigError("test error")
    assert isinstance(err, Exception)
    assert str(err) == "test error"
