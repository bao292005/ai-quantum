"""Unit tests for CSV schema mapping (Story 1D.1)."""

import gzip
import json

import pytest

from ingestion.csv_loader import CsvRowError, iter_csv_events, map_csv_row

_UNI_ROW = {
    "block_number": "14724001",
    "block_timestamp": "2022-05-06T14:15:06Z",
    "protocol": "uniswap_v3",
    "event_type": "swap",
    "pool_address": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
    "token0": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "token1": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    "amount0": "-13739080501",
    "amount1": "5130000000000000000",
    "tx_hash": "0xa343dacfff741a8773aa3b85b865c3ff98ed0b2b69d52e3aecd77a9877182d45",
    "log_index": "154",
}


def test_map_uniswap_row():
    e = map_csv_row(_UNI_ROW)
    assert e["block_number"] == 14724001 and isinstance(e["block_number"], int)
    assert e["log_index"] == 154 and isinstance(e["log_index"], int)
    # amounts MUST stay strings (precision + schema)
    assert e["amount0"] == "-13739080501" and isinstance(e["amount0"], str)
    assert e["amount1"] == "5130000000000000000" and isinstance(e["amount1"], str)
    assert set(e) == set(_UNI_ROW)  # exactly 11 fields


def test_map_aave_v2_row():
    row = {
        **_UNI_ROW,
        "protocol": "aave_v2",
        "event_type": "liquidation",
        "token1": "0x0000000000000000000000000000000000000000",
    }
    e = map_csv_row(row)
    assert e["protocol"] == "aave_v2"
    assert e["event_type"] == "liquidation"


def test_reject_bad_enum():
    with pytest.raises(CsvRowError):
        map_csv_row({**_UNI_ROW, "protocol": "sushiswap"})


def test_reject_bad_address():
    with pytest.raises(CsvRowError):
        map_csv_row({**_UNI_ROW, "pool_address": "0xNOTHEX"})


def test_reject_non_integer_block():
    with pytest.raises(CsvRowError):
        map_csv_row({**_UNI_ROW, "block_number": "abc"})


def test_reject_missing_column():
    incomplete = {k: v for k, v in _UNI_ROW.items() if k != "tx_hash"}
    with pytest.raises(CsvRowError):
        map_csv_row(incomplete)


def test_bad_row_logged_not_raised(tmp_path):
    csv_path = tmp_path / "mini.csv"
    header = ",".join(_UNI_ROW.keys())
    good = ",".join(_UNI_ROW.values())
    bad = good.replace("14724001", "not_a_number", 1)
    csv_path.write_text(f"{header}\n{good}\n{bad}\n{good}\n")
    err_log = tmp_path / "csv_errors.log"

    events = list(iter_csv_events(csv_path, error_log=err_log))
    assert len(events) == 2  # 2 good rows, bad one skipped
    lines = err_log.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["line"] == 3


def test_gzip_transparent(tmp_path):
    gz = tmp_path / "mini.csv.gz"
    header = ",".join(_UNI_ROW.keys())
    good = ",".join(_UNI_ROW.values())
    with gzip.open(gz, "wt", encoding="utf-8") as f:
        f.write(f"{header}\n{good}\n")
    events = list(iter_csv_events(gz, error_log=tmp_path / "e.log"))
    assert len(events) == 1
    assert events[0]["block_number"] == 14724001
