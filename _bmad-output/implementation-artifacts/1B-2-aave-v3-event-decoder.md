---
baseline_commit: 0e04db6dc8c2c2891a2daae9d45d31b8e82023c3
type: build
---

# Story 1B.2: Aave V3 Event Decoder

Status: done

## Story

As a **Kỹ sư Dữ liệu**,
I want **`AaveV3Decoder.decode(log, pool_meta, block_timestamp)` parse `Supply`, `Borrow`, `Withdraw`, `LiquidationCall` events của Aave V3 Pool từ raw Ethereum log**,
so that **raw log được convert thành `TickDataEvent` khớp schema `contracts/tick_data.schema.json` giống như UniswapV3Decoder trong 1B.1**.

## Acceptance Criteria

1. **AC1 — Module tồn tại:** `ingestion/decoders/aave_v3.py` export `AaveV3Decoder`.

2. **AC2 — Decode Supply:** `AaveV3Decoder().decode(supply_log, pool_meta, block_ts)` trả về `TickDataEvent` với:
   - `protocol = "aave_v3"`, `event_type = "supply"`
   - `token0` = reserve address (extracted từ topics[1])
   - `token1` = `"0x0000000000000000000000000000000000000000"` (zero address — single-asset event)
   - `amount0` = supply amount (uint256 từ data), `amount1` = `"0"`
   - `pool_address`, `tx_hash`, `log_index`, `block_number`, `block_timestamp` đầy đủ

3. **AC3 — Decode Borrow:** Tương tự AC2 với `event_type = "borrow"`.

4. **AC4 — Decode Withdraw:** Tương tự AC2 với `event_type = "withdraw"`.

5. **AC5 — Decode LiquidationCall:** `AaveV3Decoder().decode(liq_log, pool_meta, block_ts)` trả về `TickDataEvent` với:
   - `event_type = "liquidation"`
   - `token0` = collateralAsset (topics[1]), `token1` = debtAsset (topics[2])
   - `amount0` = liquidatedCollateralAmount, `amount1` = debtToCover

6. **AC6 — Unknown topic raises ValueError:** topic0 không thuộc 4 event trên → raise `ValueError("Unknown Aave V3 topic: {topic}")`.

7. **AC7 — Schema validation:** Output pass `jsonschema.validate(result.to_dict(), tick_data_schema)`.

8. **AC8 — Unit tests:** `tests/unit/test_aave_decoder.py` cover:
   - Decode Supply → assert all fields
   - Decode Borrow, Withdraw, LiquidationCall
   - LiquidationCall: token0=collateral, token1=debt, amount0=collateralAmount, amount1=debtAmount
   - Unknown topic → ValueError
   - Schema validation pass cho mỗi event type

9. **AC9 — 4 fixture logs (synthetic ABI-encoded):** `tests/fixtures/aave_v3_logs.py` chứa 4 synthetic logs (1 mỗi loại event).

## Tasks / Subtasks

- [x] **Task 1 — Implement AaveV3Decoder** (AC1–AC6)
  - [x] Tạo `ingestion/decoders/aave_v3.py`
  - [x] Import `TickDataEvent`, `PoolMeta`, helpers từ `ingestion.decoders.uniswap_v3`
  - [x] Define SUPPLY/BORROW/WITHDRAW/LIQUIDATION topic0 constants
  - [x] Implement `_topic_to_addr(topic) -> str` helper (extract address từ 32-byte topic)
  - [x] Implement decode() cho 4 event types
  - [x] Raise ValueError cho unknown topic

- [x] **Task 2 — Fixtures** (AC9)
  - [x] Tạo `tests/fixtures/aave_v3_logs.py` với 4 synthetic ABI-encoded logs

- [x] **Task 3 — Unit tests** (AC7, AC8)
  - [x] Tạo `tests/unit/test_aave_decoder.py`
  - [x] Test schema validation

## Dev Notes

**Loại story:** `[BUILD]` — blockedBy: 1B.1 (phải done trước vì re-use TickDataEvent, PoolMeta, helpers).

---

### Aave V3 Event ABI — Critical Reference

**Computed topic0 (via `web3.keccak(text=sig).hex()`):**

```python
SUPPLY_TOPIC       = "0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61"
BORROW_TOPIC       = "0xc6a898309e823ee50bac64e45ca8adba6690e99e7841c45d754e2a38e9019d9b"
WITHDRAW_TOPIC     = "0x3115d1449a7b732c986cba18244e897a450f61e1bb8d589cd2e69e6c8924f9f7"
LIQUIDATION_TOPIC  = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"
```

**⚠️ BORROW topic0 CRITICAL NOTE:**
Aave V3 `DataTypes.InterestRateMode` là enum có thể ABI-encode thành `uint8` hoặc `uint256`. Hai candidates:
- `uint256` version (recommended): `0xc6a898309e823ee50bac64e45ca8adba6690e99e7841c45d754e2a38e9019d9b`
- `uint8` version: `0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0`

**Cách verify:** Kiểm tra 1 mainnet Borrow tx trên Etherscan (Aave V3 Pool: `0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2`) để xem topic0 thực tế. Nếu fixture tests pass với uint256 thì đó là đúng. Trong code, define cả 2:

```python
BORROW_TOPIC_UINT256 = "0xc6a898309e823ee50bac64e45ca8adba6690e99e7841c45d754e2a38e9019d9b"
BORROW_TOPIC_UINT8   = "0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0"
BORROW_TOPIC = BORROW_TOPIC_UINT256  # default; flip if fixtures fail
```

**Verified LiquidationCall topic0:** `0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286` — confirmed via [QuickNode Aave Liquidation Tracker](https://www.quicknode.com/sample-app-library/ethereum-aave-liquidation-tracker).

---

**Supply event:** `Supply(address indexed reserve, address user, address indexed onBehalfOf, uint256 amount, uint16 indexed referralCode)`
- topics[0]: SUPPLY_TOPIC
- topics[1]: reserve (indexed, address) ← **token0**
- topics[2]: onBehalfOf (indexed, address)
- topics[3]: referralCode (indexed, uint16)
- data: ABI-encoded `(address user, uint256 amount)`
- **We use:** `amount0 = amount`, `token0 = reserve`, `token1 = ZERO_ADDRESS`, `amount1 = "0"`

**Borrow event:** `Borrow(address indexed reserve, address user, address indexed onBehalfOf, uint256 amount, uint256 interestRateMode, uint256 borrowRate, uint16 indexed referralCode)`
- topics[0]: BORROW_TOPIC
- topics[1]: reserve (indexed, address) ← **token0**
- topics[2]: onBehalfOf (indexed, address)
- topics[3]: referralCode (indexed, uint16)
- data: ABI-encoded `(address user, uint256 amount, uint256 interestRateMode, uint256 borrowRate)`
- **We use:** `amount0 = amount = data[1]`

**Withdraw event:** `Withdraw(address indexed reserve, address indexed user, address indexed to, uint256 amount)`
- topics[0]: WITHDRAW_TOPIC
- topics[1]: reserve (indexed, address) ← **token0**
- topics[2]: user (indexed, address)
- topics[3]: to (indexed, address)
- data: ABI-encoded `(uint256 amount)` (only 1 non-indexed param)
- **We use:** `amount0 = amount = data[0]`

**LiquidationCall event:** `LiquidationCall(address indexed collateralAsset, address indexed debtAsset, address indexed user, uint256 debtToCover, uint256 liquidatedCollateralAmount, address liquidator, bool receiveAToken)`
- topics[0]: LIQUIDATION_TOPIC
- topics[1]: collateralAsset (indexed) ← **token0**
- topics[2]: debtAsset (indexed) ← **token1**
- topics[3]: user (indexed)
- data: ABI-encoded `(uint256 debtToCover, uint256 liquidatedCollateralAmount, address liquidator, bool receiveAToken)`
- **We use:** `amount0 = liquidatedCollateralAmount = data[1]`, `amount1 = debtToCover = data[0]`

---

### Implementation Pattern

```python
# ingestion/decoders/aave_v3.py
from __future__ import annotations

from eth_abi import decode as abi_decode

from ingestion.decoders.uniswap_v3 import (
    PoolMeta,
    TickDataEvent,
    _addr,
    _topic_hex,
    _ts_to_iso,
)

SUPPLY_TOPIC      = "0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61"
BORROW_TOPIC      = "0xc6a898309e823ee50bac64e45ca8adba6690e99e7841c45d754e2a38e9019d9b"
WITHDRAW_TOPIC    = "0x3115d1449a7b732c986cba18244e897a450f61e1bb8d589cd2e69e6c8924f9f7"
LIQUIDATION_TOPIC = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

_SUPPLY_TYPES     = ["address", "uint256"]                              # user, amount
_BORROW_TYPES     = ["address", "uint256", "uint256", "uint256"]        # user, amount, rateMode, borrowRate
_WITHDRAW_TYPES   = ["uint256"]                                         # amount
_LIQUIDATION_TYPES = ["uint256", "uint256", "address", "bool"]          # debtToCover, collateralAmt, liquidator, receiveAToken


def _topic_to_addr(topic) -> str:
    """Extract lowercase 0x-prefixed address from a 32-byte topic."""
    b = topic if isinstance(topic, bytes) else bytes.fromhex(str(topic).removeprefix("0x"))
    return "0x" + b[-20:].hex()


class AaveV3Decoder:
    def decode(
        self,
        log: dict,
        pool_meta: PoolMeta,
        block_timestamp: int,
    ) -> TickDataEvent:
        topics = log["topics"]
        topic0 = _topic_hex(topics[0])
        data: bytes = (
            log["data"]
            if isinstance(log["data"], bytes)
            else bytes.fromhex(log["data"].removeprefix("0x"))
        )

        if topic0 == SUPPLY_TOPIC:
            decoded = abi_decode(_SUPPLY_TYPES, data)
            amount0, amount1 = int(decoded[1]), 0
            token0 = _topic_to_addr(topics[1])   # reserve
            token1 = ZERO_ADDRESS
            event_type = "supply"

        elif topic0 == BORROW_TOPIC:
            decoded = abi_decode(_BORROW_TYPES, data)
            amount0, amount1 = int(decoded[1]), 0
            token0 = _topic_to_addr(topics[1])   # reserve
            token1 = ZERO_ADDRESS
            event_type = "borrow"

        elif topic0 == WITHDRAW_TOPIC:
            decoded = abi_decode(_WITHDRAW_TYPES, data)
            amount0, amount1 = int(decoded[0]), 0
            token0 = _topic_to_addr(topics[1])   # reserve
            token1 = ZERO_ADDRESS
            event_type = "withdraw"

        elif topic0 == LIQUIDATION_TOPIC:
            decoded = abi_decode(_LIQUIDATION_TYPES, data)
            amount0 = int(decoded[1])  # liquidatedCollateralAmount
            amount1 = int(decoded[0])  # debtToCover
            token0 = _topic_to_addr(topics[1])   # collateralAsset
            token1 = _topic_to_addr(topics[2])   # debtAsset
            event_type = "liquidation"

        else:
            raise ValueError(f"Unknown Aave V3 topic: {topic0}")

        pool_address = (
            log["address"].lower()
            if isinstance(log["address"], str)
            else _addr(log["address"])
        )
        tx_hash = (
            log["transactionHash"].hex()
            if isinstance(log["transactionHash"], bytes)
            else str(log["transactionHash"])
        )
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash

        return TickDataEvent(
            block_number=int(log["blockNumber"]),
            block_timestamp=_ts_to_iso(block_timestamp),
            protocol="aave_v3",
            event_type=event_type,
            pool_address=pool_address,
            token0=token0,
            token1=token1,
            amount0=str(amount0),
            amount1=str(amount1),
            tx_hash=tx_hash,
            log_index=int(log["logIndex"]),
        )
```

---

### Fixture Pattern

```python
# tests/fixtures/aave_v3_logs.py
"""
Synthetic ABI-encoded Aave V3 logs for unit testing.
Aave V3 Pool: 0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2 (mainnet)
"""
from eth_abi import encode as abi_encode

AAVE_V3_POOL   = "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"
USDC           = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
WETH           = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
WBTC           = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
USER1          = "0x" + "aa" * 20
USER2          = "0x" + "bb" * 20
TX_HASH        = "0x" + "cd" * 32
BLOCK_TS       = 1698148811   # 2023-10-24T12:00:11Z

SUPPLY_TOPIC      = "0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61"
BORROW_TOPIC      = "0xc6a898309e823ee50bac64e45ca8adba6690e99e7841c45d754e2a38e9019d9b"
WITHDRAW_TOPIC    = "0x3115d1449a7b732c986cba18244e897a450f61e1bb8d589cd2e69e6c8924f9f7"
LIQUIDATION_TOPIC = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"

def _b(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str.removeprefix("0x"))

def _addr_topic(addr: str) -> bytes:
    """Pad address to 32-byte topic."""
    return bytes(12) + _b(addr)

# Log 1: Supply — 1000 USDC
SUPPLY_LOG = {
    "address": AAVE_V3_POOL,
    "topics": [_b(SUPPLY_TOPIC), _addr_topic(USDC), _addr_topic(USER2), (0).to_bytes(32, "big")],
    "data": abi_encode(["address", "uint256"], [USER1, 1_000_000_000]),
    "blockNumber": 19000000,
    "transactionHash": _b(TX_HASH),
    "logIndex": 10,
}

# Log 2: Borrow — 0.5 WETH variable rate
BORROW_LOG = {
    "address": AAVE_V3_POOL,
    "topics": [_b(BORROW_TOPIC), _addr_topic(WETH), _addr_topic(USER2), (0).to_bytes(32, "big")],
    "data": abi_encode(["address", "uint256", "uint256", "uint256"], [USER1, 500_000_000_000_000_000, 2, 50_000_000_000_000_000]),
    "blockNumber": 19000001,
    "transactionHash": _b(TX_HASH),
    "logIndex": 5,
}

# Log 3: Withdraw — 500 USDC
WITHDRAW_LOG = {
    "address": AAVE_V3_POOL,
    "topics": [_b(WITHDRAW_TOPIC), _addr_topic(USDC), _addr_topic(USER1), _addr_topic(USER2)],
    "data": abi_encode(["uint256"], [500_000_000]),
    "blockNumber": 19000002,
    "transactionHash": _b(TX_HASH),
    "logIndex": 3,
}

# Log 4: LiquidationCall — WBTC collateral, USDC debt
LIQUIDATION_LOG = {
    "address": AAVE_V3_POOL,
    "topics": [_b(LIQUIDATION_TOPIC), _addr_topic(WBTC), _addr_topic(USDC), _addr_topic(USER1)],
    "data": abi_encode(
        ["uint256", "uint256", "address", "bool"],
        [5_000_000_000, 100_000_000, USER2, False],  # debtToCover=5000USDC, collateral=100WBTC-units
    ),
    "blockNumber": 19000003,
    "transactionHash": _b(TX_HASH),
    "logIndex": 0,
}
```

---

### TickDataEvent Mapping for Aave V3

| Schema field | Supply | Borrow | Withdraw | LiquidationCall |
|---|---|---|---|---|
| `protocol` | `"aave_v3"` | `"aave_v3"` | `"aave_v3"` | `"aave_v3"` |
| `event_type` | `"supply"` | `"borrow"` | `"withdraw"` | `"liquidation"` |
| `token0` | topics[1]=reserve | topics[1]=reserve | topics[1]=reserve | topics[1]=collateralAsset |
| `token1` | `ZERO_ADDRESS` | `ZERO_ADDRESS` | `ZERO_ADDRESS` | topics[2]=debtAsset |
| `amount0` | data: amount | data: amount | data: amount | data: liquidatedCollateralAmt |
| `amount1` | `"0"` | `"0"` | `"0"` | data: debtToCover |
| `pool_address` | `log["address"]` | same | same | same |

**Note:** All Aave V3 amounts are `uint256` → always non-negative → `str(int_value)` without sign.

---

### Dependencies Known

- **1B.1** (done required): Imports `TickDataEvent`, `PoolMeta`, `_topic_hex`, `_addr`, `_ts_to_iso` from `ingestion.decoders.uniswap_v3`
- **1B.3** (Contract Whitelist): AaveV3Decoder là stateless — caller (1B.4 Router) cung cấp log và pool_meta
- **eth_abi** via web3>=6.11: bundled, no extra install needed

### Project Conventions

- Python 3.12 (anaconda), `pytest-asyncio` mode=auto
- `ruff check` cho linting
- Không dùng `@pytest.mark.asyncio` — tests này đều sync (decoder là pure function)
- Test import: `from ingestion.decoders.aave_v3 import AaveV3Decoder`

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- RED: `pytest tests/unit/test_aave_decoder.py` → ImportError.
- GREEN: 9 passed.

### Completion Notes List

- `ingestion/decoders/aave_v3.py`: `AaveV3Decoder.decode()` cho supply/borrow/withdraw/liquidation; reuse `TickDataEvent`/`PoolMeta`/helpers từ 1B.1; `_topic_to_addr` extract address từ 32-byte topic.
- **BORROW topic0 = `0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0`** (real mainnet, uint8 interestRateMode) — dùng bản này thay vì default `0xc6a898...` (uint256) trong story, xác nhận bằng `keccak` + khớp research 1R.2. Data decode `["address","uint256","uint256","uint256"]` vẫn đúng (uint8 pad thành 1 word; chỉ đọc `amount=data[1]`).
- Aave lấy `token0/token1` từ **topics** (reserve / collateral+debt), không từ pool_meta; single-asset → `token1`=ZERO, `amount1`="0". LiquidationCall: `amount0`=liquidatedCollateralAmount (data[1]), `amount1`=debtToCover (data[0]).
- Output dict khớp `tick_data.schema.json` (verified 4 event type).
- **Scope note:** decoder là **Aave V3** (realtime mainnet). Backtest LUNA/FTX là Aave V2 → đi path CSV pre-decoded (1D), không qua decoder này (quyết định đã chốt).

### File List

- `ingestion/decoders/aave_v3.py` (NEW)
- `tests/fixtures/aave_v3_logs.py` (NEW)
- `tests/unit/test_aave_decoder.py` (NEW)

## Change Log

- 2026-07-09 — Implemented Story 1B.2 AaveV3Decoder; 9 tests; BORROW topic0 = real mainnet 0xb3d084; status → review.
