"""Round-trip test: mock raw log -> EventRouter -> normalized dict (Story 0.6).

Proves the mock server's ``build_raw_log`` emits ABI-encoded logs that the
Track 1B decoders decode back to the original normalized fixture values.
"""

from pathlib import Path

import pytest

from ingestion.decoders.uniswap_v3 import PoolMeta
from ingestion.router import EventRouter
from ingestion.whitelist import ContractWhitelist, WhitelistEntry
from tools.mock_wss.replay import build_raw_log, load_events, resolve_scenario_file

_BLOCK_TS = 1698148811  # 2023-10-24T12:00:11Z

USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
WBTC = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
UNI_POOL = "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"
AAVE_V2_POOL = "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9"
ZERO = "0x0000000000000000000000000000000000000000"

_WL = ContractWhitelist({
    UNI_POOL: WhitelistEntry("uniswap_v3", PoolMeta(USDC, WETH)),
    AAVE_V2_POOL: WhitelistEntry("aave_v3", PoolMeta(ZERO, ZERO)),
})


def _row(**kw) -> dict:
    base = {
        "block_number": 14740000,
        "block_timestamp": "2023-10-24T12:00:11Z",
        "protocol": "uniswap_v3",
        "event_type": "swap",
        "pool_address": UNI_POOL,
        "token0": USDC,
        "token1": WETH,
        "amount0": "0",
        "amount1": "0",
        "tx_hash": "0x" + "ab" * 32,
        "log_index": 3,
    }
    base.update(kw)
    return base


@pytest.fixture
def router():
    return EventRouter(_WL)


def test_roundtrip_uniswap_swap_negative(router):
    row = _row(event_type="swap", amount0="-1000000000", amount1="500000000000000000")
    e = router.route_validated(build_raw_log(row), _BLOCK_TS)
    assert e.protocol == "uniswap_v3" and e.event_type == "swap"
    assert e.amount0 == "-1000000000"
    assert e.amount1 == "500000000000000000"
    assert e.token0 == USDC and e.token1 == WETH
    assert e.pool_address == UNI_POOL
    assert e.log_index == 3


def test_roundtrip_uniswap_mint(router):
    row = _row(event_type="mint", amount0="5000000", amount1="2500000000000000000")
    e = router.route(build_raw_log(row), _BLOCK_TS)
    assert e.event_type == "mint"
    assert e.amount0 == "5000000" and e.amount1 == "2500000000000000000"


def test_roundtrip_uniswap_burn(router):
    row = _row(event_type="burn", amount0="2500000", amount1="1250000000000000000")
    e = router.route(build_raw_log(row), _BLOCK_TS)
    assert e.event_type == "burn"
    assert e.amount0 == "2500000" and e.amount1 == "1250000000000000000"


def test_roundtrip_aave_supply(router):
    row = _row(protocol="aave_v2", event_type="supply", pool_address=AAVE_V2_POOL,
               token0=USDC, token1=ZERO, amount0="1000000000", amount1="0")
    e = router.route(build_raw_log(row), _BLOCK_TS)
    assert e.protocol == "aave_v3" and e.event_type == "supply"
    assert e.token0 == USDC and e.token1 == ZERO
    assert e.amount0 == "1000000000" and e.amount1 == "0"


def test_roundtrip_aave_borrow(router):
    row = _row(protocol="aave_v2", event_type="borrow", pool_address=AAVE_V2_POOL,
               token0=WETH, token1=ZERO, amount0="500000000000000000", amount1="0")
    e = router.route(build_raw_log(row), _BLOCK_TS)
    assert e.event_type == "borrow"
    assert e.token0 == WETH and e.amount0 == "500000000000000000" and e.amount1 == "0"


def test_roundtrip_aave_withdraw(router):
    row = _row(protocol="aave_v2", event_type="withdraw", pool_address=AAVE_V2_POOL,
               token0=USDC, token1=ZERO, amount0="500000000", amount1="0")
    e = router.route(build_raw_log(row), _BLOCK_TS)
    assert e.event_type == "withdraw"
    assert e.token0 == USDC and e.amount0 == "500000000" and e.amount1 == "0"


def test_roundtrip_aave_liquidation(router):
    # amount0 = liquidated collateral, amount1 = debt covered (fixture semantics)
    row = _row(protocol="aave_v2", event_type="liquidation", pool_address=AAVE_V2_POOL,
               token0=WBTC, token1=USDC, amount0="100000000", amount1="5000000000")
    e = router.route(build_raw_log(row), _BLOCK_TS)
    assert e.event_type == "liquidation"
    assert e.token0 == WBTC and e.token1 == USDC
    assert e.amount0 == "100000000"  # liquidated collateral
    assert e.amount1 == "5000000000"  # debt covered


def test_roundtrip_real_fixture_rows(router):
    """First real Uniswap + Aave rows from the luna fixture round-trip cleanly."""
    events = load_events(resolve_scenario_file("luna"))
    uni = next(r for r in events if r["protocol"] == "uniswap_v3")
    aave = next(r for r in events if r["protocol"] == "aave_v2")
    for row in (uni, aave):
        e = router.route(build_raw_log(row), _BLOCK_TS)
        assert e is not None
        assert e.amount0 == row["amount0"]
        assert e.amount1 == row["amount1"]
