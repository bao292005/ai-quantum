"""Unit tests for EventRouter (Story 1B.4)."""

import pytest

from ingestion.decoders.uniswap_v3 import PoolMeta
from ingestion.router import EventRouter
from ingestion.whitelist import ContractWhitelist, WhitelistEntry
from tests.fixtures.aave_v3_logs import (
    AAVE_V3_POOL,
    BLOCK_TS as AAVE_TS,
    BORROW_LOG,
    LIQUIDATION_LOG,
    SUPPLY_LOG,
    WITHDRAW_LOG,
)
from tests.fixtures.uniswap_v3_logs import (
    BLOCK_TS as UNI_TS,
    BURN_LOG_1,
    MINT_LOG_1,
    POOL_ADDRESS as UNI_POOL,
    SWAP_LOG_1,
    TOKEN0,
    TOKEN1,
)

_ZERO = "0x0000000000000000000000000000000000000000"

_WHITELIST = ContractWhitelist({
    UNI_POOL.lower(): WhitelistEntry("uniswap_v3", PoolMeta(TOKEN0, TOKEN1)),
    AAVE_V3_POOL.lower(): WhitelistEntry("aave_v3", PoolMeta(_ZERO, _ZERO)),
})


@pytest.fixture
def router():
    return EventRouter(_WHITELIST)


def test_route_uniswap_swap(router):
    e = router.route(SWAP_LOG_1, UNI_TS)
    assert e is not None
    assert e.protocol == "uniswap_v3"
    assert e.event_type == "swap"


def test_route_aave_supply(router):
    e = router.route(SUPPLY_LOG, AAVE_TS)
    assert e is not None
    assert e.protocol == "aave_v3"
    assert e.event_type == "supply"


def test_unknown_address_returns_none(router):
    unknown = {**SWAP_LOG_1, "address": "0x" + "ee" * 20}
    assert router.route(unknown, UNI_TS) is None


def test_known_address_unknown_topic_raises(router):
    bad = {**SWAP_LOG_1, "topics": [bytes.fromhex("de" * 32)] + list(SWAP_LOG_1["topics"][1:])}
    with pytest.raises(ValueError, match="Unknown Uniswap V3 topic"):
        router.route(bad, UNI_TS)


def test_route_validated_passes_schema(router):
    assert router.route_validated(SWAP_LOG_1, UNI_TS) is not None


def test_route_validated_none_for_unknown(router):
    unknown = {**SWAP_LOG_1, "address": "0x" + "ee" * 20}
    assert router.route_validated(unknown, UNI_TS) is None


def test_all_uniswap_event_types(router):
    assert router.route(MINT_LOG_1, UNI_TS).event_type == "mint"
    assert router.route(BURN_LOG_1, UNI_TS).event_type == "burn"


def test_all_aave_event_types(router):
    assert router.route(BORROW_LOG, AAVE_TS).event_type == "borrow"
    assert router.route(WITHDRAW_LOG, AAVE_TS).event_type == "withdraw"
    assert router.route(LIQUIDATION_LOG, AAVE_TS).event_type == "liquidation"


def test_from_yaml(tmp_path):
    import textwrap
    p = tmp_path / "wl.yaml"
    p.write_text(textwrap.dedent(f"""\
        "{UNI_POOL}":
          protocol: uniswap_v3
          token0: "{TOKEN0}"
          token1: "{TOKEN1}"
    """))
    r = EventRouter.from_yaml(p)
    assert r.route(SWAP_LOG_1, UNI_TS).event_type == "swap"
