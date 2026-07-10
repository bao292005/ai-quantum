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

from eth_abi import encode as abi_encode

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

_ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
_ZERO_WORD = "0x" + "00" * 32

# Real mainnet topic0 per normalized event_type — MUST match the Track 1B decoder
# constants (ingestion/decoders/*), so mock logs decode end-to-end. Borrow uses
# the real uint8-interestRateMode variant.
_EVENT_TOPIC0: dict[str, str] = {
    "swap": "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67",
    "mint": "0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde",
    "burn": "0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c",
    "supply": "0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61",
    "borrow": "0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0",
    "withdraw": "0x3115d1449a7b732c986cba18244e897a450f61e1bb8d589cd2e69e6c8924f9f7",
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


def _addr_topic(addr: str) -> str:
    """Left-pad a 20-byte address into a 32-byte indexed-topic hex string."""
    return "0x" + "00" * 12 + addr.lower().removeprefix("0x")


def _encode_event(event_type: str, amount0: int, amount1: int, token0: str, token1: str):
    """Return ``(topics_tail, data_bytes)`` for a normalized event.

    ``topics_tail`` are the indexed topics AFTER topic0. Layouts mirror the real
    Uniswap V3 / Aave V3 event ABIs exactly where the Track 1B decoders read
    amounts and asset addresses; other positions are zero-filled placeholders.
    """
    if event_type == "swap":
        tail = [_addr_topic(_ZERO_ADDRESS), _addr_topic(_ZERO_ADDRESS)]  # sender, recipient
        data = abi_encode(["int256", "int256", "uint160", "uint128", "int24"], [amount0, amount1, 0, 0, 0])
    elif event_type == "mint":
        tail = [_addr_topic(_ZERO_ADDRESS), _ZERO_WORD, _ZERO_WORD]  # owner, tickLower, tickUpper
        data = abi_encode(["address", "uint128", "uint256", "uint256"], [_ZERO_ADDRESS, 0, amount0, amount1])
    elif event_type == "burn":
        tail = [_addr_topic(_ZERO_ADDRESS), _ZERO_WORD, _ZERO_WORD]  # owner, tickLower, tickUpper
        data = abi_encode(["uint128", "uint256", "uint256"], [0, amount0, amount1])
    elif event_type == "supply":
        tail = [_addr_topic(token0), _addr_topic(_ZERO_ADDRESS), _ZERO_WORD]  # reserve, onBehalfOf, refCode
        data = abi_encode(["address", "uint256"], [_ZERO_ADDRESS, amount0])
    elif event_type == "borrow":
        tail = [_addr_topic(token0), _addr_topic(_ZERO_ADDRESS), _ZERO_WORD]  # reserve, onBehalfOf, refCode
        data = abi_encode(["address", "uint256", "uint256", "uint256"], [_ZERO_ADDRESS, amount0, 0, 0])
    elif event_type == "withdraw":
        tail = [_addr_topic(token0), _addr_topic(_ZERO_ADDRESS), _addr_topic(_ZERO_ADDRESS)]  # reserve, user, to
        data = abi_encode(["uint256"], [amount0])
    elif event_type == "liquidation":
        tail = [_addr_topic(token0), _addr_topic(token1), _addr_topic(_ZERO_ADDRESS)]  # collateral, debt, user
        # decoder reads amount0=data[1] (collateral), amount1=data[0] (debtToCover)
        data = abi_encode(["uint256", "uint256", "address", "bool"], [amount1, amount0, _ZERO_ADDRESS, False])
    else:
        tail = []
        data = abi_encode(["int256", "int256"], [amount0, amount1])
    return tail, data


def build_raw_log(row: dict) -> dict:
    """Build a real ABI-encoded raw-log ``result`` payload for a ``logs`` sub (AC3).

    Reconstructs an eth-style log from the normalized fixture row so the Track 1B
    decoders round-trip it: ``topics`` carries topic0 + the event's indexed
    fields (asset addresses for Aave), and ``data`` is the ABI-encoded
    non-indexed tuple. Raises ``ValueError`` if an amount is non-numeric so the
    replay loop's per-row guard can skip the bad row.
    """
    amount0, amount1 = int(row["amount0"]), int(row["amount1"])  # ValueError on bad row
    event_type = row["event_type"]
    topic0 = _EVENT_TOPIC0.get(event_type, "0x" + "00" * 32)
    try:
        tail, data = _encode_event(
            event_type,
            amount0,
            amount1,
            row.get("token0", _ZERO_ADDRESS),
            row.get("token1", _ZERO_ADDRESS),
        )
    except Exception as exc:
        # eth_abi raises its own EncodingError (e.g. ValueOutOfBounds) for a
        # negative/overflow amount on a uint field. Re-raise as ValueError so the
        # replay loop's per-row guard skips the row instead of dying.
        raise ValueError(f"cannot ABI-encode {event_type} log: {exc}") from exc
    return {
        "address": row["pool_address"],
        "topics": [topic0, *tail],
        "data": "0x" + data.hex(),
        "blockNumber": hex(int(row["block_number"])),
        "blockHash": _block_hash(int(row["block_number"])),
        "transactionHash": row["tx_hash"],
        "logIndex": hex(int(row["log_index"])),
        "removed": False,
    }
