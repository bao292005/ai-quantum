"""Unit tests for UniswapV3Decoder (Story 1B.1)."""

import json
from pathlib import Path

import jsonschema
import pytest

from ingestion.decoders.uniswap_v3 import PoolMeta, UniswapV3Decoder
from tests.fixtures.uniswap_v3_logs import (
    BLOCK_TS,
    BURN_LOG_1,
    MINT_LOG_1,
    POOL_ADDRESS,
    SWAP_LOG_1,
    SWAP_LOG_2,
    SWAP_LOG_ZERO,
    TOKEN0,
    TOKEN1,
)

_SCHEMA = json.loads(
    (Path(__file__).resolve().parents[2] / "contracts" / "tick_data.schema.json").read_text()
)
_POOL_META = PoolMeta(token0=TOKEN0, token1=TOKEN1)
_DECODER = UniswapV3Decoder()


def _decode(log):
    return _DECODER.decode(log, _POOL_META, BLOCK_TS)


def test_decode_swap_fields():
    e = _decode(SWAP_LOG_1)
    assert e.protocol == "uniswap_v3"
    assert e.event_type == "swap"
    assert e.amount0 == "-1000000000"  # negative int256 preserved as decimal string
    assert e.amount1 == "500000000000000000"
    assert e.pool_address == POOL_ADDRESS
    assert e.token0 == TOKEN0
    assert e.token1 == TOKEN1
    assert e.block_number == 18500000
    assert e.block_timestamp == "2023-10-24T12:00:11Z"
    assert e.tx_hash == "0x" + "ab" * 32
    assert e.log_index == 42


def test_decode_swap_reverse_direction():
    e = _decode(SWAP_LOG_2)
    assert e.amount0 == "2000000000"
    assert e.amount1 == "-999000000000000000"


def test_decode_mint():
    e = _decode(MINT_LOG_1)
    assert e.event_type == "mint"
    assert e.amount0 == "5000000"
    assert e.amount1 == "2500000000000000000"


def test_decode_burn():
    e = _decode(BURN_LOG_1)
    assert e.event_type == "burn"
    assert e.amount0 == "2500000"
    assert e.amount1 == "1250000000000000000"


def test_swap_zero_amount1():
    e = _decode(SWAP_LOG_ZERO)
    assert e.amount0 == "1"
    assert e.amount1 == "0"


def test_unknown_topic_raises():
    bad = {**SWAP_LOG_1, "topics": [bytes.fromhex("de" * 32)] + list(SWAP_LOG_1["topics"][1:])}
    with pytest.raises(ValueError, match="Unknown Uniswap V3 topic"):
        _decode(bad)


@pytest.mark.parametrize("log", [SWAP_LOG_1, SWAP_LOG_2, MINT_LOG_1, BURN_LOG_1, SWAP_LOG_ZERO])
def test_schema_validation(log):
    jsonschema.validate(_decode(log).to_dict(), _SCHEMA)
