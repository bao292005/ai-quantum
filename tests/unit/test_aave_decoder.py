"""Unit tests for AaveV3Decoder (Story 1B.2)."""

import json
from pathlib import Path

import jsonschema
import pytest

from ingestion.decoders.aave_v3 import AaveV3Decoder
from ingestion.decoders.uniswap_v3 import PoolMeta
from tests.fixtures.aave_v3_logs import (
    AAVE_V3_POOL,
    BLOCK_TS,
    BORROW_LOG,
    LIQUIDATION_LOG,
    SUPPLY_LOG,
    USDC,
    WBTC,
    WETH,
    WITHDRAW_LOG,
)

_SCHEMA = json.loads(
    (Path(__file__).resolve().parents[2] / "contracts" / "tick_data.schema.json").read_text()
)
_ZERO = "0x0000000000000000000000000000000000000000"
# Aave decoder derives token0/token1 from event topics, so pool_meta is unused.
_POOL_META = PoolMeta(token0=_ZERO, token1=_ZERO)
_DECODER = AaveV3Decoder()


def _decode(log):
    return _DECODER.decode(log, _POOL_META, BLOCK_TS)


def test_decode_supply():
    e = _decode(SUPPLY_LOG)
    assert e.protocol == "aave_v3"
    assert e.event_type == "supply"
    assert e.token0 == USDC
    assert e.token1 == _ZERO
    assert e.amount0 == "1000000000"
    assert e.amount1 == "0"
    assert e.pool_address == AAVE_V3_POOL
    assert e.block_number == 19000000
    assert e.log_index == 10


def test_decode_borrow():
    e = _decode(BORROW_LOG)
    assert e.event_type == "borrow"
    assert e.token0 == WETH
    assert e.token1 == _ZERO
    assert e.amount0 == "500000000000000000"
    assert e.amount1 == "0"


def test_decode_withdraw():
    e = _decode(WITHDRAW_LOG)
    assert e.event_type == "withdraw"
    assert e.token0 == USDC
    assert e.amount0 == "500000000"
    assert e.amount1 == "0"


def test_decode_liquidation():
    e = _decode(LIQUIDATION_LOG)
    assert e.event_type == "liquidation"
    assert e.token0 == WBTC  # collateralAsset
    assert e.token1 == USDC  # debtAsset
    assert e.amount0 == "100000000"  # liquidatedCollateralAmount
    assert e.amount1 == "5000000000"  # debtToCover


def test_unknown_topic_raises():
    bad = {**SUPPLY_LOG, "topics": [bytes.fromhex("ee" * 32)] + list(SUPPLY_LOG["topics"][1:])}
    with pytest.raises(ValueError, match="Unknown Aave V3 topic"):
        _decode(bad)


@pytest.mark.parametrize("log", [SUPPLY_LOG, BORROW_LOG, WITHDRAW_LOG, LIQUIDATION_LOG])
def test_schema_validation(log):
    jsonschema.validate(_decode(log).to_dict(), _SCHEMA)
