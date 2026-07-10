"""Unit tests for the backtest replay driver (Story 1D.3)."""

import asyncio
import math

import pytest

from core.ring_buffer import DequeRingBuffer
from ingestion.csv_loader import ReplayDriver, _parse_rate

_HEADER = ("block_number,block_timestamp,protocol,event_type,pool_address,"
           "token0,token1,amount0,amount1,tx_hash,log_index")


def _row(block: int, ts: str, log_index: int = 0) -> str:
    return (f"{block},{ts},uniswap_v3,swap,"
            "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640,"
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48,"
            "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2,"
            "-13739080501,5130000000000000000,"
            "0xa343dacfff741a8773aa3b85b865c3ff98ed0b2b69d52e3aecd77a9877182d45,"
            f"{log_index}")


def test_parse_rate():
    assert _parse_rate("1x") == 1.0
    assert _parse_rate("100x") == 100.0
    assert _parse_rate(50) == 50.0
    assert math.isinf(_parse_rate("asap"))
    for bad in ("fast", "0x", "-5x", "", "inf", "nan", "-inf"):
        with pytest.raises(ValueError):
            _parse_rate(bad)


async def test_asap_no_sleep(tmp_path, monkeypatch):
    sleeps = []

    async def fake_sleep(d):
        sleeps.append(d)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    p = tmp_path / "s.csv"
    p.write_text(_HEADER + "\n"
                 + _row(1, "2022-05-06T14:15:06Z") + "\n"
                 + _row(2, "2022-05-06T14:15:16Z") + "\n")
    buf = DequeRingBuffer(100)
    n = await ReplayDriver(buf, rate="asap").run(p, error_log=tmp_path / "e.log")
    assert n == 2
    assert [e["block_number"] for e in buf.read_all()] == [1, 2]
    # asap: no pacing delay (sleep(0) cooperative yields from stream_csv are ok)
    assert [d for d in sleeps if d > 0] == []


async def test_pacing_ratio(tmp_path, monkeypatch):
    sleeps = []

    async def fake_sleep(d):
        sleeps.append(d)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    p = tmp_path / "s.csv"
    p.write_text(_HEADER + "\n"
                 + _row(1, "2022-05-06T14:15:00Z") + "\n"       # t0
                 + _row(2, "2022-05-06T14:15:10Z") + "\n"       # +10s
                 + _row(2, "2022-05-06T14:15:10Z", 1) + "\n"    # same block, +0s
                 + _row(3, "2022-05-06T14:15:40Z") + "\n")      # +30s
    buf = DequeRingBuffer(100)
    await ReplayDriver(buf, rate="10x").run(p, error_log=tmp_path / "e.log")
    assert [d for d in sleeps if d > 0] == [1.0, 3.0]  # 10s/10, 30s/10


async def test_integration_deque(tmp_path):
    p = tmp_path / "s.csv"
    rows = "\n".join(_row(b, f"2022-05-06T14:15:{b:02d}Z") for b in (1, 2, 3))
    p.write_text(_HEADER + "\n" + rows + "\n")
    buf = DequeRingBuffer(100)
    n = await ReplayDriver(buf, rate="asap").run(p, error_log=tmp_path / "e.log")
    assert n == 3
    assert [e["block_number"] for e in buf.read_all()] == [1, 2, 3]
