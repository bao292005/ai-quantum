"""Unit tests for the async CSV streamer (Story 1D.2)."""

import gzip
import tracemalloc
from pathlib import Path

from ingestion.csv_loader import stream_csv

_HEADER = ("block_number,block_timestamp,protocol,event_type,pool_address,"
           "token0,token1,amount0,amount1,tx_hash,log_index")


def _row(block: int, log_index: int = 0) -> str:
    return (f"{block},2022-05-06T14:15:06Z,uniswap_v3,swap,"
            "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640,"
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48,"
            "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2,"
            "-13739080501,5130000000000000000,"
            "0xa343dacfff741a8773aa3b85b865c3ff98ed0b2b69d52e3aecd77a9877182d45,"
            f"{log_index}")


async def test_stream_order_and_count(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text(_HEADER + "\n" + "\n".join(_row(b) for b in (1, 2, 3, 10)) + "\n")
    events = [e async for e in stream_csv(p, error_log=tmp_path / "e.log")]
    assert [e["block_number"] for e in events] == [1, 2, 3, 10]


async def test_stream_skips_bad_row(tmp_path):
    p = tmp_path / "s.csv"
    good = _row(1)
    bad = good.replace("1,", "notanumber,", 1)
    p.write_text(f"{_HEADER}\n{good}\n{bad}\n{_row(2)}\n")
    err = tmp_path / "e.log"
    events = [e async for e in stream_csv(p, error_log=err)]
    assert [e["block_number"] for e in events] == [1, 2]
    assert err.exists() and len(err.read_text().strip().splitlines()) == 1


async def test_stream_gzip(tmp_path):
    gz = tmp_path / "s.csv.gz"
    with gzip.open(gz, "wt", encoding="utf-8") as f:
        f.write(_HEADER + "\n" + _row(5) + "\n")
    events = [e async for e in stream_csv(gz, error_log=tmp_path / "e.log")]
    assert len(events) == 1 and events[0]["block_number"] == 5


async def test_stream_out_of_order_still_yields(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text(_HEADER + "\n" + "\n".join(_row(b) for b in (5, 3)) + "\n")
    events = [e async for e in stream_csv(p, error_log=tmp_path / "e.log")]
    assert [e["block_number"] for e in events] == [5, 3]  # not dropped


async def test_stream_memory_under_50mb():
    fixture = Path("fixtures/backtest/luna_2022_05_09.csv.gz")
    tracemalloc.start()
    count = 0
    async for _ in stream_csv(fixture, error_log="/tmp/csv_errors_test.log"):
        count += 1
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert count == 26540
    assert peak < 50 * 1024 * 1024  # < 50 MB
