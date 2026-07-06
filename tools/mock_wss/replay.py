"""Replay engine helpers for the mock WebSocket server (Story 0.5).

Pure, side-effect-free functions so they can be unit-tested without spinning up
a server:

* ``load_events`` — read a ``.csv``/``.csv.gz`` fixture into sorted event dicts.
* ``parse_speed`` / ``sleep_seconds`` — speed-control math (AC2).
* ``iter_block_groups`` — group events by block for newHeads/logs emission.
* ``build_block_header`` / ``build_raw_log`` — JSON-RPC ``result`` payloads (AC3).
* ``resolve_scenario_file`` — ``--scenario`` → fixture path mapping (AC4).
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
# Fixtures are shipped in sdist/wheel builds (see MANIFEST.in) and resolve to the
# repo tree for editable/dev installs. Deployments that relocate fixtures can set
# QR_FIXTURES_DIR instead of relying on the ``parents[2]`` layout.
FIXTURES_DIR = Path(os.environ.get("QR_FIXTURES_DIR", REPO_ROOT / "fixtures" / "backtest"))

# --scenario shortcut → fixture stem (AC4). The extractor may emit .csv or
# .csv.gz (Story 0.4 chose gzip), so resolution checks both extensions.
SCENARIO_FILES: dict[str, str] = {
    "luna": "luna_2022_05_09.csv",
    "ftx": "ftx_2022_11_08.csv",
    "normal": "normal_2023_03_15.csv",
}

_UINT256_MASK = (1 << 256) - 1

# topic0 signatures per event_type (cosmetic — AC9 filters on address only, but
# a realistic raw-log shape keeps downstream decoders honest).
_EVENT_TOPIC0: dict[str, str] = {
    "swap": "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67",
    "borrow": "0xc6a898309e823ee50bac64e45ca8adba6690e99e7841c45d754e2a38e9019d9b",
    "supply": "0xde6857219544bb5b7746f48ed30be6386fefc61b2f864cacf559893bf50fd951",
    "liquidation": "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286",
}

INT_COLS = ("block_number", "log_index")


# ---------------------------------------------------------------------------
# CSV loading (transparent gzip)
# ---------------------------------------------------------------------------

def _open_fixture(path: Path) -> io.TextIOBase:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def load_events(path: Path) -> list[dict]:
    """Load a fixture CSV into event dicts sorted by ``(block_number, log_index)``.

    ``block_number`` and ``log_index`` are cast to ``int``; all other columns
    stay as strings (they are re-emitted verbatim in the raw-log payload).
    Fixtures are already sorted by the extractor, but we sort defensively so the
    replay ordering does not depend on that guarantee.
    """
    with _open_fixture(path) as fh:
        reader = csv.DictReader(fh)
        rows: list[dict] = []
        for line_no, row in enumerate(reader, start=2):  # line 1 is the header
            for col in INT_COLS:
                raw = row.get(col)
                try:
                    row[col] = int(raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{path.name}: line {line_no}: invalid integer in "
                        f"column '{col}': {raw!r}"
                    ) from exc
            rows.append(row)
    rows.sort(key=lambda r: (r["block_number"], r["log_index"]))
    return rows


def resolve_scenario_file(scenario: str) -> Path:
    """Map a ``--scenario`` name to its fixture path, preferring ``.csv.gz``.

    Raises ``ValueError`` for an unknown scenario and ``FileNotFoundError`` when
    neither the gzip nor the raw CSV exists.
    """
    stem = SCENARIO_FILES.get(scenario)
    if stem is None:
        raise ValueError(
            f"unknown scenario {scenario!r}; choose one of {sorted(SCENARIO_FILES)}"
        )
    gz = FIXTURES_DIR / f"{stem}.gz"
    raw = FIXTURES_DIR / stem
    if gz.is_file():
        return gz
    if raw.is_file():
        return raw
    raise FileNotFoundError(
        f"fixture for scenario {scenario!r} not found (looked for {gz} and {raw})"
    )


# ---------------------------------------------------------------------------
# Speed control (AC2)
# ---------------------------------------------------------------------------

def parse_speed(value: str) -> float | None:
    """Parse a ``--speed`` value.

    Returns a positive multiplier for ``"1x"``/``"100x"``/``"2.5x"`` (the ``x``
    suffix is optional), or ``None`` for ``"asap"`` (emit with no sleep).
    Raises ``ValueError`` for anything non-positive or unparseable.
    """
    token = value.strip().lower()
    if token == "asap":
        return None
    if token.endswith("x"):
        token = token[:-1]
    try:
        multiplier = float(token)
    except ValueError as exc:
        raise ValueError(f"invalid --speed {value!r} (use e.g. 1x, 100x, asap)") from exc
    if multiplier <= 0:
        raise ValueError(f"--speed must be > 0, got {value!r}")
    return multiplier


def _ts_to_epoch(ts: str) -> int:
    return int(
        datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )


def sleep_seconds(prev_ts: str, cur_ts: str, speed: float | None) -> float:
    """Compute the replay sleep between two block timestamps.

    ``speed=None`` (asap) → ``0.0``. Otherwise ``dt / speed``, where ``dt`` is
    the wall-clock gap in the fixture. Never negative (guards against any
    out-of-order timestamp within a monotonic block sequence).
    """
    if speed is None:
        return 0.0
    dt = _ts_to_epoch(cur_ts) - _ts_to_epoch(prev_ts)
    if dt <= 0:
        return 0.0
    return dt / speed


# ---------------------------------------------------------------------------
# Block grouping + JSON-RPC result payloads (AC3)
# ---------------------------------------------------------------------------

def iter_block_groups(events: list[dict]) -> Iterator[tuple[int, str, list[dict]]]:
    """Yield ``(block_number, block_timestamp, rows)`` groups in block order.

    ``events`` must already be sorted (``load_events`` guarantees this). Rows
    sharing a ``block_number`` are grouped so the server can emit one
    ``newHeads`` header followed by that block's ``logs``.
    """
    if not events:
        return
    cur_block = events[0]["block_number"]
    cur_ts = events[0]["block_timestamp"]
    bucket: list[dict] = []
    for row in events:
        if row["block_number"] != cur_block:
            yield cur_block, cur_ts, bucket
            cur_block = row["block_number"]
            cur_ts = row["block_timestamp"]
            bucket = []
        bucket.append(row)
    yield cur_block, cur_ts, bucket


def _block_hash(block_number: int) -> str:
    return "0x" + hashlib.sha256(f"block:{block_number}".encode()).hexdigest()


def build_block_header(block_number: int, block_timestamp: str) -> dict:
    """Build a minimal ``newHeads`` BlockHeader payload (AC3)."""
    return {
        "number": hex(block_number),
        "hash": _block_hash(block_number),
        "parentHash": _block_hash(block_number - 1),
        "timestamp": hex(_ts_to_epoch(block_timestamp)),
    }


def _to_word(value: int) -> str:
    """Encode a (possibly negative) int as a 32-byte two's-complement hex word."""
    return format(value & _UINT256_MASK, "064x")


def build_raw_log(row: dict) -> dict:
    """Build a raw-log ``result`` payload for a ``logs`` subscription (AC3).

    Reconstructs an eth-style log from the normalized fixture row: ``topics`` is
    ``[topic0]`` for the event type, and ``data`` packs the two amounts as
    32-byte words. Numeric fields are hex-encoded per the JSON-RPC convention.
    """
    topic0 = _EVENT_TOPIC0.get(row["event_type"], "0x" + "00" * 32)
    data = "0x" + _to_word(int(row["amount0"])) + _to_word(int(row["amount1"]))
    return {
        "address": row["pool_address"],
        "topics": [topic0],
        "data": data,
        "blockNumber": hex(int(row["block_number"])),
        "blockHash": _block_hash(int(row["block_number"])),
        "transactionHash": row["tx_hash"],
        "logIndex": hex(int(row["log_index"])),
        "removed": False,
    }
