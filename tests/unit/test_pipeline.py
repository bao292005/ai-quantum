"""Unit tests for the pipeline orchestrator (Story 1E.1)."""

import pytest

from core.ring_buffer import DequeRingBuffer
from ingestion import metrics
from ingestion.pipeline import _parse_args, run_backtest

_HEADER = ("block_number,block_timestamp,protocol,event_type,pool_address,"
           "token0,token1,amount0,amount1,tx_hash,log_index")


def _row(block: int) -> str:
    return (f"{block},2022-05-06T14:15:06Z,uniswap_v3,swap,"
            "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640,"
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48,"
            "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2,"
            "-13739080501,5130000000000000000,"
            "0xa343dacfff741a8773aa3b85b865c3ff98ed0b2b69d52e3aecd77a9877182d45,"
            f"{block}")


def test_parse_args_defaults():
    args = _parse_args(["--source", "backtest"])
    assert args.source == "backtest"
    assert args.scenario == "luna"
    assert args.speed == "100x"
    assert args.capacity == 1000
    assert args.metrics_port == 9090


def test_parse_args_requires_source():
    with pytest.raises(SystemExit):
        _parse_args([])


def test_parse_args_source_choices():
    with pytest.raises(SystemExit):
        _parse_args(["--source", "invalid"])


async def test_run_backtest_fills_buffer_and_counter(tmp_path):
    csv = tmp_path / "mini.csv"
    csv.write_text(_HEADER + "\n" + "\n".join(_row(b) for b in range(1, 6)) + "\n")
    buf = DequeRingBuffer(100)

    before = metrics.EVENTS_INGESTED._value.get()
    n = await run_backtest(buf, "luna", "asap", path=csv)
    after = metrics.EVENTS_INGESTED._value.get()

    assert n == 5
    assert len(buf) == 5
    assert after - before == 5
    assert [e["block_number"] for e in buf.read_all()] == [1, 2, 3, 4, 5]


async def test_run_backtest_evicts_at_capacity(tmp_path):
    csv = tmp_path / "mini.csv"
    csv.write_text(_HEADER + "\n" + "\n".join(_row(b) for b in range(1, 11)) + "\n")
    buf = DequeRingBuffer(4)
    n = await run_backtest(buf, "luna", "asap", path=csv)
    assert n == 10  # counter counts all replayed
    assert len(buf) == 4  # ring buffer keeps only the last 4
    assert [e["block_number"] for e in buf.read_all()] == [7, 8, 9, 10]
