"""Unit tests for ContractWhitelist (Story 1B.3)."""

import textwrap
from pathlib import Path

import pytest

from ingestion.whitelist import ContractWhitelist

YAML_CONTENT = textwrap.dedent("""\
    "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640":
      protocol: uniswap_v3
      token0: "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
      token1: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2":
      protocol: aave_v3
      token0: "0x0000000000000000000000000000000000000000"
      token1: "0x0000000000000000000000000000000000000000"
""")


@pytest.fixture
def whitelist(tmp_path):
    p = tmp_path / "whitelist.yaml"
    p.write_text(YAML_CONTENT)
    return ContractWhitelist.from_yaml(p)


def test_load_count(whitelist):
    assert len(whitelist) == 2


def test_get_known(whitelist):
    entry = whitelist.get("0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640")
    assert entry is not None
    assert entry.protocol == "uniswap_v3"
    assert entry.pool_meta.token0 == "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    assert entry.pool_meta.token1 == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"


def test_get_unknown(whitelist):
    assert whitelist.get("0x" + "ff" * 20) is None


def test_case_insensitive(whitelist):
    assert whitelist.get("0x88E6A0C2DDD26FEEB64F039A2C41296FCB3F5640") is not None


def test_contains(whitelist):
    assert "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2" in whitelist
    assert "0x" + "aa" * 20 not in whitelist


def test_aave_entry(whitelist):
    entry = whitelist.get("0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2")
    assert entry.protocol == "aave_v3"
    assert entry.pool_meta.token0 == "0x0000000000000000000000000000000000000000"


def test_bundled_whitelist_yaml_loads():
    """The shipped ingestion/whitelist.yaml must load and contain Uniswap+Aave."""
    path = Path(__file__).resolve().parents[2] / "ingestion" / "whitelist.yaml"
    wl = ContractWhitelist.from_yaml(path)
    protocols = {wl.get(a).protocol for a in wl._entries}
    assert "uniswap_v3" in protocols
    assert "aave_v3" in protocols
