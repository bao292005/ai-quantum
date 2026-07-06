"""Offline smoke tests for the backtest fixtures (Story 0.4).

Fast, network-free guards that run in the ``unit-tests`` CI job. They open the
committed ``.csv.gz`` fixtures, validate a bounded sample of rows against the
Story 0.1 tick-data schema, and assert the AC2/AC6 invariants. The full
row-by-row + on-chain cross-check lives in ``tools/verify_fixtures.py`` and its
dedicated ``verify-fixtures`` CI job.
"""

from __future__ import annotations

import csv
import gzip
from pathlib import Path

import pytest

from core.schemas import validate_tick

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "fixtures" / "backtest"

EXPECTED = {
    "luna_2022_05_09.csv.gz": {"aave_v2", "uniswap_v3"},
    "ftx_2022_11_08.csv.gz": {"aave_v2", "uniswap_v3"},
    "normal_2023_03_15.csv.gz": {"aave_v3", "uniswap_v3"},
}

SAMPLE_LIMIT = 200  # bound work so the unit job stays fast


def _rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        yield from csv.DictReader(fh)


@pytest.mark.parametrize("filename", sorted(EXPECTED))
def test_fixture_exists(filename: str) -> None:
    assert (FIXTURES_DIR / filename).is_file(), f"missing fixture {filename}"


@pytest.mark.parametrize("filename", sorted(EXPECTED))
def test_fixture_schema_sanity(filename: str) -> None:
    path = FIXTURES_DIR / filename
    prev_block = -1
    seen: set[tuple[str, int]] = set()
    event_types: set[str] = set()
    protocols: set[str] = set()
    total = 0

    for i, row in enumerate(_rows(path)):
        total += 1
        block = int(row["block_number"])
        assert block >= prev_block, f"{filename}: block_number not monotonic at row {i}"
        prev_block = block

        key = (row["tx_hash"], int(row["log_index"]))
        assert key not in seen, f"{filename}: duplicate (tx_hash, log_index) at row {i}"
        seen.add(key)

        event_types.add(row["event_type"])
        protocols.add(row["protocol"])

        if i < SAMPLE_LIMIT:
            typed = dict(row)
            typed["block_number"] = block
            typed["log_index"] = int(row["log_index"])
            validate_tick(typed)  # raises on schema violation

    assert total >= 1000, f"{filename}: only {total} rows (AC2 needs ≥ 1000)"
    assert len(event_types) >= 3, f"{filename}: {event_types} has < 3 event types (AC6)"
    assert protocols == EXPECTED[filename], (
        f"{filename}: protocols {protocols} != expected {EXPECTED[filename]}"
    )
