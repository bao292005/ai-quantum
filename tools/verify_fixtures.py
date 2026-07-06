"""Verify historical backtest fixtures against the tick-data schema (Story 0.4).

Runs three layers of checks over each CSV under ``fixtures/backtest/``:

1. Schema validation: every row → ``core.schemas.validate_tick``.
2. Sanity checks (AC6): monotonic block_number, unique (tx_hash, log_index),
   ≥3 distinct event_types per file, no empty amounts, no NaN.
   Note: AC6 literally says "timestamp monotonic"; we assert block_number
   monotonic instead, which is strictly stronger — block_number monotonic
   implies block_timestamp monotonic (a block's timestamp never precedes an
   earlier block's), and it avoids equal-timestamp ties within a block.
3. On-chain cross-check (AC8, optional): random-sample 10 rows/file and
   verify via Etherscan ``eth_getTransactionByHash`` that the reported
   ``blockNumber`` matches. Skipped with a warning if ``ETHERSCAN_API_KEY``
   is unset (offline dev / offline CI).

Exits with status 1 on any failure; 0 on success.

Transparently opens ``.csv`` or ``.csv.gz`` fixtures.

Usage:
    python tools/verify_fixtures.py
"""

from __future__ import annotations

import csv
import gzip
import io
import os
import random
import sys
import time
from pathlib import Path
from typing import Iterator

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "fixtures" / "backtest"

sys.path.insert(0, str(REPO_ROOT))
from core.schemas import validate_tick  # noqa: E402

ETHERSCAN_URL = "https://api.etherscan.io/v2/api"
CHAIN_ID = 1
SAMPLE_SIZE = 10
RATE_LIMIT_SEC = 0.25

INT_COLS = ("block_number", "log_index")

# ---------------------------------------------------------------------------
# .env loader (kept minimal — mirrors extract_fixtures.py)
# ---------------------------------------------------------------------------

def _load_env_file() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# ---------------------------------------------------------------------------
# CSV loading (transparent gzip)
# ---------------------------------------------------------------------------

def _open_fixture(path: Path) -> io.TextIOBase:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def _iter_rows(path: Path) -> Iterator[dict]:
    with _open_fixture(path) as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            for col in INT_COLS:
                raw = row.get(col)  # None if the column is missing / row is short
                try:
                    row[col] = int(raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{path.name}: line {reader.line_num}: "
                        f"invalid integer in column '{col}': {raw!r}"
                    ) from exc
            yield row


# ---------------------------------------------------------------------------
# Layer 1 & 2: schema + sanity
# ---------------------------------------------------------------------------

def _verify_file(path: Path) -> list[dict]:
    print(f"[verify] {path.name}")
    rows: list[dict] = []
    prev_block = -1
    seen_keys: set[tuple[str, int]] = set()
    event_types: set[str] = set()
    for idx, row in enumerate(_iter_rows(path)):
        try:
            validate_tick(row)
        except Exception as exc:
            raise AssertionError(f"{path.name} row {idx}: schema validation failed: {exc}") from exc

        if row["block_number"] < prev_block:
            raise AssertionError(
                f"{path.name} row {idx}: block_number {row['block_number']} < previous {prev_block}"
            )
        prev_block = row["block_number"]

        key = (row["tx_hash"], row["log_index"])
        if key in seen_keys:
            raise AssertionError(f"{path.name} row {idx}: duplicate (tx_hash, log_index) = {key}")
        seen_keys.add(key)

        for amt in ("amount0", "amount1"):
            val = row[amt]
            if val in ("", "NaN", "nan", None) or val.lower() == "nan":
                raise AssertionError(f"{path.name} row {idx}: empty/NaN {amt}")

        event_types.add(row["event_type"])
        rows.append(row)

    if len(rows) < 1000:
        raise AssertionError(f"{path.name}: only {len(rows)} rows (< 1000 required by AC2)")
    if len(event_types) < 3:
        raise AssertionError(
            f"{path.name}: only {len(event_types)} distinct event_types ({event_types}), need ≥3"
        )
    print(f"  rows={len(rows)}  event_types={sorted(event_types)}  monotonic ✓  unique ✓")
    return rows


# ---------------------------------------------------------------------------
# Layer 3: on-chain cross-check (AC8)
# ---------------------------------------------------------------------------

_LAST_CALL = 0.0


def _throttle() -> None:
    global _LAST_CALL
    delta = time.time() - _LAST_CALL
    if delta < RATE_LIMIT_SEC:
        time.sleep(RATE_LIMIT_SEC - delta)
    _LAST_CALL = time.time()


MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 1.0


def _tx_block_from_etherscan(tx_hash: str, api_key: str) -> int | None:
    """Return the on-chain block number for ``tx_hash``.

    Retries transient failures (network errors, or Etherscan's rate-limit
    throttling — signalled as a STRING in ``result`` with HTTP 200 and no
    exception) up to ``MAX_RETRIES`` with linear backoff so a single flaky
    response does not fail the whole run.

    Returns ``None`` only when Etherscan definitively reports the tx has no
    block yet (a dict ``result`` without ``blockNumber`` — e.g. a pending tx).
    If every attempt is a transient failure (network error or persistent
    rate-limit string), raises ``RuntimeError`` so the caller surfaces a clear,
    actionable failure instead of a misleading "no result for tx" assertion.
    """
    params = {
        "chainid": CHAIN_ID,
        "module": "proxy",
        "action": "eth_getTransactionByHash",
        "txhash": tx_hash,
        "apikey": api_key,
    }
    last_exc: Exception | None = None
    last_rate_limit: str | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        _throttle()
        try:
            resp = requests.get(ETHERSCAN_URL, params=params, timeout=15)
            resp.raise_for_status()
            body = resp.json()
            result = body.get("result")
            if isinstance(result, dict):
                block_hex = result.get("blockNumber")
                return int(block_hex, 16) if block_hex else None
            # Non-dict result: Etherscan returns rate-limit / transient errors
            # as a STRING in `result` (HTTP 200, no exception) — retry these.
            if isinstance(result, str):
                last_rate_limit = result
        except requests.RequestException as exc:
            last_exc = exc
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_SEC * attempt)
    # Every attempt failed transiently — fail loudly rather than returning a
    # silent None that would masquerade as a data mismatch downstream.
    detail = last_rate_limit or (str(last_exc) if last_exc else "unknown transient error")
    raise RuntimeError(
        f"eth_getTransactionByHash exhausted {MAX_RETRIES} retries for {tx_hash}: {detail}"
    )


def _cross_check(rows: list[dict], api_key: str, tag: str) -> None:
    rng = random.Random(0xDEF1)  # deterministic sample for reproducibility
    sample = rng.sample(rows, min(SAMPLE_SIZE, len(rows)))
    for row in sample:
        remote = _tx_block_from_etherscan(row["tx_hash"], api_key)
        if remote is None:
            raise AssertionError(f"{tag}: no result for tx {row['tx_hash']}")
        if remote != row["block_number"]:
            raise AssertionError(
                f"{tag}: on-chain block {remote} != CSV block {row['block_number']} for tx {row['tx_hash']}"
            )
    print(f"  on-chain cross-check ✓ ({len(sample)} sampled)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    _load_env_file()
    api_key = os.environ.get("ETHERSCAN_API_KEY", "").strip()

    files = sorted(
        list(FIXTURES_DIR.glob("*.csv")) + list(FIXTURES_DIR.glob("*.csv.gz"))
    )
    if not files:
        print(f"[verify] no fixtures found under {FIXTURES_DIR}", file=sys.stderr)
        return 1

    failures: list[str] = []
    for path in files:
        try:
            rows = _verify_file(path)
            if api_key:
                _cross_check(rows, api_key, tag=path.name)
            else:
                print("  WARNING: ETHERSCAN_API_KEY not set — skipping on-chain cross-check")
        except AssertionError as exc:
            failures.append(str(exc))
            print(f"  FAIL: {exc}", file=sys.stderr)
        except (ValueError, RuntimeError, requests.RequestException, OSError) as exc:
            failures.append(f"{path.name}: {type(exc).__name__}: {exc}")
            print(f"  FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)

    if failures:
        print(f"\n[verify] {len(failures)} failure(s)", file=sys.stderr)
        return 1
    print("\n[verify] all fixtures OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
