"""Extract historical backtest fixtures from Etherscan V2 API.

Fetches raw event logs for Uniswap V3 + Aave V2/V3 for three block-range
windows (LUNA depeg, FTX collapse, normal-market control), decodes them,
and writes CSVs matching the Story 0.1 tick-data schema.

Usage:
    python tools/extract_fixtures.py [--period luna|ftx|normal|all]

Env:
    ETHERSCAN_API_KEY  (loaded from repo-root .env if present)

Design notes:
  * Etherscan V2 unified endpoint; chainid=1 for Ethereum mainnet.
  * eth_getLogs returns up to 1000 rows/call — we chunk the block range.
  * For Aave events (single-asset), token1 is set to the zero-address so the
    output still conforms to the 40-hex schema.
  * Uniswap V3 amount0/amount1 are signed int256 — decoded as two's-complement.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "fixtures" / "backtest"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

ETHERSCAN_URL = "https://api.etherscan.io/v2/api"
CHAIN_ID = 1
ZERO_ADDR = "0x0000000000000000000000000000000000000000"

# ---------------------------------------------------------------------------
# Contract & topic registry
# ---------------------------------------------------------------------------

# Uniswap V3 USDC/WETH 0.05% pool (deepest ETH/USDC liquidity)
UNIV3_USDC_WETH = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
UNIV3_USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
UNIV3_WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
UNIV3_SWAP_TOPIC = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"

# Aave V2 LendingPool (LUNA/FTX era)
AAVE_V2_POOL = "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9"
AAVE_V2_BORROW_TOPIC = "0xc6a898309e823ee50bac64e45ca8adba6690e99e7841c45d754e2a38e9019d9b"
AAVE_V2_DEPOSIT_TOPIC = "0xde6857219544bb5b7746f48ed30be6386fefc61b2f864cacf559893bf50fd951"
# Aave V2 & V3 share the same LiquidationCall topic hash.
LIQUIDATION_TOPIC = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"

# Aave V3 Pool (normal-market era)
AAVE_V3_POOL = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
AAVE_V3_BORROW_TOPIC = "0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0"
AAVE_V3_SUPPLY_TOPIC = "0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61"

CSV_HEADER = [
    "block_number",
    "block_timestamp",
    "protocol",
    "event_type",
    "pool_address",
    "token0",
    "token1",
    "amount0",
    "amount1",
    "tx_hash",
    "log_index",
]


@dataclass(frozen=True)
class Period:
    name: str
    from_block: int
    to_block: int
    filename: str
    aave_version: str  # "v2" or "v3"
    description: str


PERIODS = {
    "luna": Period(
        name="luna",
        from_block=14_724_000,
        to_block=14_740_000,
        filename="luna_2022_05_09.csv",
        aave_version="v2",
        # First cascading Aave V2 liquidation is block 14731270 (2022-05-07T17:59:54Z).
        # from_block=14724000 is ~7270 blocks (~24h) earlier to satisfy AC1's >=24h runway;
        # to_block=14740000 keeps >=12h after the first liquidation.
        description="LUNA/UST depeg window with >=24h pre-liquidation runway (first Aave V2 liq @ block 14731270).",
    ),
    "ftx": Period(
        name="ftx",
        from_block=15_900_000,
        to_block=15_925_000,
        filename="ftx_2022_11_08.csv",
        aave_version="v2",
        description="FTX collapse window 2022-11-08 → 2022-11-11.",
    ),
    "normal": Period(
        name="normal",
        from_block=16_820_000,
        to_block=16_825_000,
        filename="normal_2023_03_15.csv",
        aave_version="v3",
        description="Control set 2023-03-15 (Aave V3 mainnet is live).",
    ),
}


# ---------------------------------------------------------------------------
# Env / .env loading
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
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _get_api_key() -> str:
    _load_env_file()
    key = os.environ.get("ETHERSCAN_API_KEY", "").strip()
    if not key:
        sys.exit("ETHERSCAN_API_KEY not set (checked env + .env)")
    return key


# ---------------------------------------------------------------------------
# Etherscan client
# ---------------------------------------------------------------------------

_SESSION = requests.Session()
_LAST_CALL_TS = 0.0
_RATE_LIMIT_SEC = 0.5  # 2 req/s, safely under the 3 req/s free-tier ceiling.
_MAX_RETRIES = 5
_RETRY_BACKOFF_SEC = 1.5  # linear backoff for transient disconnects/rate-limit


def _throttle() -> None:
    global _LAST_CALL_TS
    delta = time.time() - _LAST_CALL_TS
    if delta < _RATE_LIMIT_SEC:
        time.sleep(_RATE_LIMIT_SEC - delta)
    _LAST_CALL_TS = time.time()


def etherscan_get_logs(
    *,
    from_block: int,
    to_block: int,
    address: str,
    topic0: str,
    api_key: str,
) -> list[dict]:
    """Call Etherscan V2 logs API with automatic pagination via block splitting."""
    params = {
        "chainid": CHAIN_ID,
        "module": "logs",
        "action": "getLogs",
        "fromBlock": from_block,
        "toBlock": to_block,
        "address": address,
        "topic0": topic0,
        "apikey": api_key,
    }
    data = None
    last_err: str | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        _throttle()
        try:
            resp = _SESSION.get(ETHERSCAN_URL, params=params, timeout=30)
            resp.raise_for_status()
            body = resp.json()
        except requests.RequestException as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BACKOFF_SEC * attempt)
            continue
        result = body.get("result")
        # Etherscan signals rate-limit as a string `result` (HTTP 200) — retry it.
        if isinstance(result, str) and "rate limit" in result.lower():
            last_err = f"rate limit: {result}"
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BACKOFF_SEC * attempt)
            continue
        data = body
        break
    if data is None:
        raise RuntimeError(
            f"Etherscan getLogs failed after {_MAX_RETRIES} retries "
            f"(blocks {from_block}..{to_block}, {address}): {last_err}"
        )
    result = data.get("result")
    if isinstance(result, str):
        # Etherscan returns error message as string in `result`.
        if "No records" in result:
            return []
        raise RuntimeError(f"Etherscan error [{data.get('message')}]: {result}")
    if not isinstance(result, list):
        raise RuntimeError(f"Unexpected Etherscan response: {data}")

    # Etherscan caps at 1000 rows/call. If we hit the cap, split the range.
    if len(result) >= 1000:
        if from_block >= to_block:
            # Single block already at the cap — we cannot split further, so more
            # rows may exist that we would silently drop. Fail loudly instead.
            raise RuntimeError(
                f"block {from_block} returned >=1000 logs for {address}/{topic0}; "
                "cannot paginate a single block — rows would be silently truncated"
            )
        mid = (from_block + to_block) // 2
        left = etherscan_get_logs(
            from_block=from_block, to_block=mid, address=address, topic0=topic0, api_key=api_key
        )
        right = etherscan_get_logs(
            from_block=mid + 1, to_block=to_block, address=address, topic0=topic0, api_key=api_key
        )
        return left + right
    return result


# ---------------------------------------------------------------------------
# Log decoders
# ---------------------------------------------------------------------------

def _int_from_hex(hexstr: str, *, signed: bool = False, bits: int = 256) -> int:
    n = int(hexstr, 16)
    if signed:
        limit = 1 << bits
        if n >= (limit >> 1):
            n -= limit
    return n


def _slice_data(data_hex: str, offset: int) -> str:
    """Return the 32-byte word at `offset` (0-indexed) from a `0x...` blob."""
    if not data_hex.startswith("0x"):
        raise ValueError(f"data must start with 0x: {data_hex[:12]}")
    start = 2 + offset * 64
    word = data_hex[start : start + 64]
    if len(word) != 64:
        raise ValueError(
            f"data too short for word {offset}: need 32 bytes at offset "
            f"{offset}, got {len(word) // 2} bytes (data len={len(data_hex) - 2} hex chars)"
        )
    return "0x" + word


def _hex_to_addr(hex_word: str) -> str:
    # 32-byte word → last 20 bytes are the address.
    return "0x" + hex_word.lower().replace("0x", "").rjust(64, "0")[-40:]


def _ts_from_hex(hex_ts: str) -> str:
    return (
        datetime.fromtimestamp(int(hex_ts, 16), tz=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def decode_univ3_swap(log: dict) -> dict:
    data = log["data"]
    amount0 = _int_from_hex(_slice_data(data, 0), signed=True)
    amount1 = _int_from_hex(_slice_data(data, 1), signed=True)
    return {
        "block_number": int(log["blockNumber"], 16),
        "block_timestamp": _ts_from_hex(log["timeStamp"]),
        "protocol": "uniswap_v3",
        "event_type": "swap",
        "pool_address": UNIV3_USDC_WETH.lower(),
        "token0": UNIV3_USDC.lower(),
        "token1": UNIV3_WETH.lower(),
        "amount0": str(amount0),
        "amount1": str(amount1),
        "tx_hash": log["transactionHash"].lower(),
        "log_index": int(log["logIndex"], 16),
    }


def decode_aave_borrow(log: dict, *, version: str) -> dict:
    reserve = _hex_to_addr(log["topics"][1])
    # V2 Borrow: reserve (t1), user (d0), onBehalfOf (t2 indexed), amount (d1), borrowRateMode (d2), borrowRate (d3), referral (t3 indexed)
    # V3 Borrow: reserve (t1), user (d0), onBehalfOf (t2 indexed), amount (d1), interestRateMode (d2), borrowRate (d3), referralCode (t3 indexed)
    # amount is non-indexed word #1 in BOTH V2 and V3 (word 3 is borrowRate, ray-scaled ~1e27).
    amount = _int_from_hex(_slice_data(log["data"], 1))
    return {
        "block_number": int(log["blockNumber"], 16),
        "block_timestamp": _ts_from_hex(log["timeStamp"]),
        "protocol": f"aave_{version}",
        "event_type": "borrow",
        "pool_address": (AAVE_V2_POOL if version == "v2" else AAVE_V3_POOL).lower(),
        "token0": reserve.lower(),
        "token1": ZERO_ADDR,
        "amount0": str(amount),
        "amount1": "0",
        "tx_hash": log["transactionHash"].lower(),
        "log_index": int(log["logIndex"], 16),
    }


def decode_aave_supply(log: dict, *, version: str) -> dict:
    reserve = _hex_to_addr(log["topics"][1])
    # V2 Deposit: reserve (t1), user (d0), onBehalfOf (t2), amount (d1), referral (t3)
    # V3 Supply:  reserve (t1), user (d0), onBehalfOf (t2), amount (d1), referralCode (t3)
    amount = _int_from_hex(_slice_data(log["data"], 1))
    return {
        "block_number": int(log["blockNumber"], 16),
        "block_timestamp": _ts_from_hex(log["timeStamp"]),
        "protocol": f"aave_{version}",
        "event_type": "supply",
        "pool_address": (AAVE_V2_POOL if version == "v2" else AAVE_V3_POOL).lower(),
        "token0": reserve.lower(),
        "token1": ZERO_ADDR,
        "amount0": str(amount),
        "amount1": "0",
        "tx_hash": log["transactionHash"].lower(),
        "log_index": int(log["logIndex"], 16),
    }


def decode_aave_liquidation(log: dict, *, version: str) -> dict:
    collateral = _hex_to_addr(log["topics"][1])
    debt = _hex_to_addr(log["topics"][2])
    debt_to_cover = _int_from_hex(_slice_data(log["data"], 0))
    liquidated_collateral = _int_from_hex(_slice_data(log["data"], 1))
    return {
        "block_number": int(log["blockNumber"], 16),
        "block_timestamp": _ts_from_hex(log["timeStamp"]),
        "protocol": f"aave_{version}",
        "event_type": "liquidation",
        "pool_address": (AAVE_V2_POOL if version == "v2" else AAVE_V3_POOL).lower(),
        "token0": collateral.lower(),
        "token1": debt.lower(),
        "amount0": str(liquidated_collateral),
        "amount1": str(debt_to_cover),
        "tx_hash": log["transactionHash"].lower(),
        "log_index": int(log["logIndex"], 16),
    }


# ---------------------------------------------------------------------------
# Per-period fetch
# ---------------------------------------------------------------------------

def _fetch_period(period: Period, api_key: str) -> list[dict]:
    print(f"[{period.name}] blocks {period.from_block}..{period.to_block} ({period.description})", flush=True)
    rows: list[dict] = []

    # Uniswap V3 swaps
    swaps = etherscan_get_logs(
        from_block=period.from_block,
        to_block=period.to_block,
        address=UNIV3_USDC_WETH,
        topic0=UNIV3_SWAP_TOPIC,
        api_key=api_key,
    )
    print(f"  uniswap_v3 swap: {len(swaps)}", flush=True)
    rows.extend(decode_univ3_swap(log) for log in swaps)

    if period.aave_version == "v2":
        borrow_topic = AAVE_V2_BORROW_TOPIC
        supply_topic = AAVE_V2_DEPOSIT_TOPIC
        pool = AAVE_V2_POOL
    else:
        borrow_topic = AAVE_V3_BORROW_TOPIC
        supply_topic = AAVE_V3_SUPPLY_TOPIC
        pool = AAVE_V3_POOL

    borrows = etherscan_get_logs(
        from_block=period.from_block,
        to_block=period.to_block,
        address=pool,
        topic0=borrow_topic,
        api_key=api_key,
    )
    print(f"  aave_{period.aave_version} borrow: {len(borrows)}", flush=True)
    rows.extend(decode_aave_borrow(log, version=period.aave_version) for log in borrows)

    supplies = etherscan_get_logs(
        from_block=period.from_block,
        to_block=period.to_block,
        address=pool,
        topic0=supply_topic,
        api_key=api_key,
    )
    print(f"  aave_{period.aave_version} supply: {len(supplies)}", flush=True)
    rows.extend(decode_aave_supply(log, version=period.aave_version) for log in supplies)

    liquidations = etherscan_get_logs(
        from_block=period.from_block,
        to_block=period.to_block,
        address=pool,
        topic0=LIQUIDATION_TOPIC,
        api_key=api_key,
    )
    print(f"  aave_{period.aave_version} liquidation: {len(liquidations)}", flush=True)
    rows.extend(decode_aave_liquidation(log, version=period.aave_version) for log in liquidations)

    rows.sort(key=lambda r: (r["block_number"], r["log_index"]))
    return rows


def _write_csv(rows: Iterable[dict], path: Path) -> int:
    count = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=list(PERIODS.keys()) + ["all"], default="all")
    args = parser.parse_args()

    api_key = _get_api_key()
    targets = [PERIODS[args.period]] if args.period != "all" else list(PERIODS.values())

    for period in targets:
        rows = _fetch_period(period, api_key)
        out = FIXTURES_DIR / period.filename
        n = _write_csv(rows, out)
        print(f"[{period.name}] wrote {n} rows -> {out.relative_to(REPO_ROOT)}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
