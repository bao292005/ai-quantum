---
baseline_commit: 0e04db6dc8c2c2891a2daae9d45d31b8e82023c3
type: build
---

# Story 1B.1: Uniswap V3 Event Decoder

Status: done

## Story

As a **Kỹ sư Dữ liệu**,
I want **`UniswapV3Decoder.decode(log, pool_meta, block_timestamp)` parse `Swap`, `Mint`, `Burn` events của Uniswap V3 pool từ raw Ethereum log**,
so that **raw log được convert thành `TickDataEvent` khớp schema `contracts/tick_data.schema.json` mà mọi downstream (Track 1C, Epic 2) tiêu thụ**.

## Acceptance Criteria

1. **AC1 — Module tồn tại:** `ingestion/decoders/uniswap_v3.py` export `UniswapV3Decoder` và `PoolMeta`.

2. **AC2 — Decode Swap:** `UniswapV3Decoder().decode(swap_log, pool_meta, block_ts)` trả về `TickDataEvent` với:
   - `protocol = "uniswap_v3"`, `event_type = "swap"`
   - `amount0`, `amount1` là decimal string (int signed, từ ABI-decoded `int256`)
   - `pool_address`, `token0`, `token1`, `tx_hash`, `log_index`, `block_number`, `block_timestamp` đầy đủ

3. **AC3 — Decode Mint và Burn:** Tương tự AC2 với `event_type = "mint"` / `"burn"`.

4. **AC4 — Unknown topic raises ValueError:** Log có topic0 không phải Swap/Mint/Burn topic → raise `ValueError("Unknown Uniswap V3 topic: {topic}")`.

5. **AC5 — Schema validation:** Output của `decode()` pass `jsonschema.validate(result, tick_data_schema)`.

6. **AC6 — Unit tests:** `tests/unit/test_uniswap_decoder.py` cover:
   - Decode Swap với ABI-encoded data → assert tất cả fields khớp expected
   - Decode Mint và Burn
   - Unknown topic → ValueError
   - amount0 âm (signed int256) được encode đúng dạng decimal string
   - Schema validation pass cho mỗi event type

7. **AC7 — 5 fixture logs (synthetic ABI-encoded):** `tests/fixtures/uniswap_v3_logs.py` chứa 5 synthetic log dicts ABI-encoded đúng Uniswap V3 format, dùng làm test oracle ổn định.

## Tasks / Subtasks

- [x] **Task 1 — Tạo ingestion/decoders package** (AC1)
  - [x] Tạo `ingestion/decoders/__init__.py` (rỗng)
  - [x] Tạo `ingestion/decoders/uniswap_v3.py`

- [x] **Task 2 — Implement TickDataEvent + PoolMeta dataclass** (AC2, AC3)
  - [x] `@dataclass class PoolMeta: token0: str; token1: str`
  - [x] `@dataclass class TickDataEvent` với tất cả fields theo schema 0.1
  - [x] Helper `to_dict() -> dict` để pass qua jsonschema.validate

- [x] **Task 3 — Implement UniswapV3Decoder.decode()** (AC2, AC3, AC4)
  - [x] Map topic0 → event_type (Swap/Mint/Burn)
  - [x] Dùng `eth_abi.decode()` (bundled với web3) để decode data field
  - [x] Convert signed int256 → decimal string (str(int_value))
  - [x] Convert block_timestamp (unix int) → ISO 8601 UTC string
  - [x] Raise ValueError cho unknown topic

- [x] **Task 4 — Unit tests** (AC5, AC6, AC7)
  - [x] Tạo `tests/fixtures/uniswap_v3_logs.py` với 5 synthetic ABI-encoded logs
  - [x] Tạo `tests/unit/test_uniswap_decoder.py`
  - [x] Test schema validation với `jsonschema.validate`

## Dev Notes

**Loại story:** `[BUILD]` — blockedBy: 1R.2 (Schema↔ABI Reconciliation) là P0 nhưng chưa done (ready-for-dev). Story này implement dựa trên Uniswap V3 ABI đã biết; kết quả 1R.2 sẽ validate sau.

---

### File Structure

```
ingestion/
  decoders/
    __init__.py          ← TẠO MỚI (rỗng)
    uniswap_v3.py        ← TẠO MỚI
tests/
  fixtures/
    uniswap_v3_logs.py   ← TẠO MỚI (5 ABI-encoded synthetic logs)
  unit/
    test_uniswap_decoder.py  ← TẠO MỚI
```

---

### Uniswap V3 Event ABI — Critical Reference

**Topic0 signatures (keccak256 of event signature):**

```python
SWAP_TOPIC  = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
MINT_TOPIC  = "0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde"
BURN_TOPIC  = "0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c"
```

**Swap event:** `Swap(address indexed sender, address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick)`
- topics[0]: SWAP_TOPIC
- topics[1]: sender (indexed, address)
- topics[2]: recipient (indexed, address)
- data: ABI-encoded `(int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick)`
- **We use:** `amount0` (int256), `amount1` (int256) từ data

**Mint event:** `Mint(address sender, address indexed owner, int24 indexed tickLower, int24 indexed tickUpper, uint128 amount, uint256 amount0, uint256 amount1)`
- topics[0]: MINT_TOPIC
- topics[1]: owner (indexed)
- topics[2]: tickLower (indexed, int24)
- topics[3]: tickUpper (indexed, int24)
- data: ABI-encoded `(address sender, uint128 amount, uint256 amount0, uint256 amount1)`
- **We use:** `amount0` (uint256), `amount1` (uint256) từ data

**Burn event:** `Burn(address indexed owner, int24 indexed tickLower, int24 indexed tickUpper, uint128 amount, uint256 amount0, uint256 amount1)`
- topics[0]: BURN_TOPIC
- topics[1]: owner (indexed)
- topics[2]: tickLower (indexed, int24)
- topics[3]: tickUpper (indexed, int24)
- data: ABI-encoded `(uint128 amount, uint256 amount0, uint256 amount1)`
- **We use:** `amount0` (uint256), `amount1` (uint256) từ data

---

### Implementation Pattern

```python
# ingestion/decoders/uniswap_v3.py
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone

from eth_abi import decode as abi_decode

SWAP_TOPIC = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
MINT_TOPIC = "0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde"
BURN_TOPIC = "0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c"

# Only the types we extract per event (positional order matters)
_SWAP_TYPES = ["int256", "int256", "uint160", "uint128", "int24"]
_MINT_TYPES = ["address", "uint128", "uint256", "uint256"]
_BURN_TYPES = ["uint128", "uint256", "uint256"]


@dataclass
class PoolMeta:
    token0: str  # lowercase 0x address
    token1: str  # lowercase 0x address


@dataclass
class TickDataEvent:
    block_number: int
    block_timestamp: str   # ISO 8601 UTC e.g. "2023-10-24T12:00:11Z"
    protocol: str          # "uniswap_v3"
    event_type: str        # "swap" | "mint" | "burn"
    pool_address: str      # lowercase 0x address
    token0: str
    token1: str
    amount0: str           # decimal string, may be negative
    amount1: str
    tx_hash: str           # 0x + 64 hex chars
    log_index: int

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _topic_hex(raw) -> str:
    return raw.hex() if isinstance(raw, bytes) else str(raw).lower()


def _addr(raw) -> str:
    s = raw.hex() if isinstance(raw, bytes) else str(raw)
    return s if s.startswith("0x") else "0x" + s


def _ts_to_iso(unix_ts: int) -> str:
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class UniswapV3Decoder:
    def decode(
        self,
        log: dict,
        pool_meta: PoolMeta,
        block_timestamp: int,
    ) -> TickDataEvent:
        topics = log["topics"]
        topic0 = _topic_hex(topics[0])
        data: bytes = log["data"] if isinstance(log["data"], bytes) else bytes.fromhex(log["data"].removeprefix("0x"))

        if topic0 == SWAP_TOPIC:
            decoded = abi_decode(_SWAP_TYPES, data)
            amount0, amount1 = decoded[0], decoded[1]
            event_type = "swap"
        elif topic0 == MINT_TOPIC:
            decoded = abi_decode(_MINT_TYPES, data)
            amount0, amount1 = int(decoded[2]), int(decoded[3])
            event_type = "mint"
        elif topic0 == BURN_TOPIC:
            decoded = abi_decode(_BURN_TYPES, data)
            amount0, amount1 = int(decoded[1]), int(decoded[2])
            event_type = "burn"
        else:
            raise ValueError(f"Unknown Uniswap V3 topic: {topic0}")

        pool_address = log["address"].lower() if isinstance(log["address"], str) else _addr(log["address"])
        tx_hash = log["transactionHash"].hex() if isinstance(log["transactionHash"], bytes) else str(log["transactionHash"])
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash

        return TickDataEvent(
            block_number=int(log["blockNumber"]),
            block_timestamp=_ts_to_iso(block_timestamp),
            protocol="uniswap_v3",
            event_type=event_type,
            pool_address=pool_address,
            token0=pool_meta.token0.lower(),
            token1=pool_meta.token1.lower(),
            amount0=str(amount0),
            amount1=str(amount1),
            tx_hash=tx_hash,
            log_index=int(log["logIndex"]),
        )
```

---

### Fixture Pattern (ABI-encoded Synthetic Logs)

```python
# tests/fixtures/uniswap_v3_logs.py
"""
Synthetic ABI-encoded Uniswap V3 logs for unit testing.
Values are realistic but not from real mainnet transactions.
Pool: USDC/WETH 0.05% — 0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640
token0: USDC  0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
token1: WETH  0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2
"""
from eth_abi import encode as abi_encode

POOL_ADDRESS = "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"
TOKEN0 = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC
TOKEN1 = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"  # WETH
BLOCK_TS = 1698148811  # 2023-10-24T12:00:11Z

SWAP_TOPIC  = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
MINT_TOPIC  = "0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde"
BURN_TOPIC  = "0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c"
SENDER      = "0x" + "aa" * 20
RECIPIENT   = "0x" + "bb" * 20
OWNER       = "0x" + "cc" * 20
TX_HASH     = "0x" + "ab" * 32

def _b(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str.removeprefix("0x"))

# Log 1: Swap — amount0=-1000000000 USDC (negative), amount1=+500000000000000000 WETH
SWAP_LOG_1 = {
    "address": POOL_ADDRESS,
    "topics": [_b(SWAP_TOPIC), _b(SENDER.replace("0x", "").zfill(64)), _b(RECIPIENT.replace("0x", "").zfill(64))],
    "data": abi_encode(["int256","int256","uint160","uint128","int24"], [-1000000000, 500000000000000000, 2**80, 10**18, 0]),
    "blockNumber": 18500000,
    "transactionHash": _b(TX_HASH),
    "logIndex": 42,
}

# Log 2: Swap — amount0 positive, amount1 negative (reverse direction)
SWAP_LOG_2 = {
    "address": POOL_ADDRESS,
    "topics": [_b(SWAP_TOPIC), _b(SENDER.replace("0x","").zfill(64)), _b(RECIPIENT.replace("0x","").zfill(64))],
    "data": abi_encode(["int256","int256","uint160","uint128","int24"], [2000000000, -999000000000000000, 2**79, 10**18, -100]),
    "blockNumber": 18500001,
    "transactionHash": _b(TX_HASH),
    "logIndex": 7,
}

# Log 3: Mint — add liquidity, amount0=5000000 USDC, amount1=2500000000000000000 WETH
MINT_LOG_1 = {
    "address": POOL_ADDRESS,
    "topics": [_b(MINT_TOPIC), _b(OWNER.replace("0x","").zfill(64)), ((-887272).to_bytes(32,"big",signed=True)), (887272).to_bytes(32,"big")],
    "data": abi_encode(["address","uint128","uint256","uint256"], [SENDER, 10**15, 5000000, 2500000000000000000]),
    "blockNumber": 18500002,
    "transactionHash": _b(TX_HASH),
    "logIndex": 1,
}

# Log 4: Burn — remove liquidity
BURN_LOG_1 = {
    "address": POOL_ADDRESS,
    "topics": [_b(BURN_TOPIC), _b(OWNER.replace("0x","").zfill(64)), ((-887272).to_bytes(32,"big",signed=True)), (887272).to_bytes(32,"big")],
    "data": abi_encode(["uint128","uint256","uint256"], [5*10**14, 2500000, 1250000000000000000]),
    "blockNumber": 18500003,
    "transactionHash": _b(TX_HASH),
    "logIndex": 3,
}

# Log 5: Swap with zero amount1 (edge case)
SWAP_LOG_ZERO = {
    "address": POOL_ADDRESS,
    "topics": [_b(SWAP_TOPIC), _b(SENDER.replace("0x","").zfill(64)), _b(RECIPIENT.replace("0x","").zfill(64))],
    "data": abi_encode(["int256","int256","uint160","uint128","int24"], [1, 0, 2**80, 10**18, 0]),
    "blockNumber": 18500004,
    "transactionHash": _b(TX_HASH),
    "logIndex": 0,
}
```

---

### eth_abi Usage

`eth_abi` is bundled with `web3>=6.11` — no additional dependency needed.

```python
from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode  # for test fixtures only
```

**Verify:**
```python
python -c "from eth_abi import decode; print('ok')"
```

---

### Schema Validation Pattern

```python
import json
import jsonschema

with open("contracts/tick_data.schema.json") as f:
    SCHEMA = json.load(f)

def validate_event(event: TickDataEvent):
    jsonschema.validate(event.to_dict(), SCHEMA)
```

Note: `jsonschema>=4.20.0` already in `pyproject.toml` dependencies.

---

### TickDataEvent → Schema Mapping

| Schema field | Source |
|---|---|
| `block_number` | `log["blockNumber"]` (int) |
| `block_timestamp` | `block_timestamp` param → ISO 8601 UTC |
| `protocol` | hardcoded `"uniswap_v3"` |
| `event_type` | topic0 → `"swap"` \| `"mint"` \| `"burn"` |
| `pool_address` | `log["address"]` (checksummed → lowercased) |
| `token0` | `pool_meta.token0` |
| `token1` | `pool_meta.token1` |
| `amount0` | ABI-decoded int256/uint256 → `str()` |
| `amount1` | ABI-decoded int256/uint256 → `str()` |
| `tx_hash` | `log["transactionHash"]` hex |
| `log_index` | `log["logIndex"]` (int) |

**Mint/Burn: amount sign convention** — Mint = positive (tokens entering pool), Burn = positive (tokens leaving pool). Both are `uint256` in ABI so never negative. Swap `amount0`/`amount1` are `int256` — negative means tokens leaving the pool.

---

### Known Dependencies

- **1R.2 Schema↔ABI Reconciliation** (`ready-for-dev`): Story này implement dựa trên ABI đã biết. Khi 1R.2 done, kết quả `research/schema_abi_gap.md` có thể yêu cầu adjust field mapping.
- **1B.3 Contract Address Whitelist** (`backlog`): Story này KHÔNG load whitelist — caller (1B.4 Router) chịu trách nhiệm cung cấp `PoolMeta`. Decoder là stateless.
- **1A.2 EthereumClient** (`done`): Không cần — decoder là pure function, không cần WebSocket.

---

### Project-wide Conventions (từ các story 1A.x đã done)

- Python 3.12 (anaconda), `pytest-asyncio` mode=auto
- `ruff check` cho linting
- Test imports: `from ingestion.decoders.uniswap_v3 import UniswapV3Decoder, PoolMeta`
- Không dùng `@pytest.mark.asyncio` — tất cả test async chạy auto
- `eth_abi` available qua `web3>=6.11` (web3 7.16.0 installed)

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- RED: `pytest tests/unit/test_uniswap_decoder.py` → ImportError (module chưa có).
- GREEN: 11 passed.
- Verify topic0: `keccak(text=sig)` xác nhận Swap/Mint/Burn topic0 khớp constants.

### Completion Notes List

- `ingestion/decoders/uniswap_v3.py`: `PoolMeta`, `TickDataEvent(.to_dict())`, `UniswapV3Decoder.decode(log, pool_meta, block_ts)`; helpers `_topic_hex/_addr/_ts_to_iso/_to_data_bytes/_tx_hash` (reuse bởi 1B.2).
- **Fix bug so với story pattern:** `_topic_hex` trong story trả `bytes.hex()` KHÔNG có prefix `0x` → không bao giờ khớp constant `0x...` (luôn ValueError). Implement lại chuẩn hoá về `0x`-prefixed lowercase → so khớp đúng cả khi topic là `HexBytes`/bytes (web3 realtime) lẫn str.
- amount0/amount1: Swap = signed int256 (giữ dấu âm, decimal string); Mint/Burn = uint256 (từ data[2]/[3] và data[1]/[2]).
- token0/token1 lấy từ `pool_meta` (không có trong event) — decoder stateless, khớp research 1R.2.
- Output dict 11-field khớp `tick_data.schema.json` (verified qua jsonschema cho cả 5 fixture). Khớp dict contract của ring buffer (1C) / csv_loader (1D).
- ruff không cài local (CI lint); tạo `tests/fixtures/__init__.py` để `tests.fixtures.*` import được (package).

### File List

- `ingestion/decoders/__init__.py` (NEW)
- `ingestion/decoders/uniswap_v3.py` (NEW)
- `tests/fixtures/__init__.py` (NEW)
- `tests/fixtures/uniswap_v3_logs.py` (NEW)
- `tests/unit/test_uniswap_decoder.py` (NEW)

## Change Log

- 2026-07-09 — Implemented Story 1B.1 UniswapV3Decoder + TickDataEvent/PoolMeta; 11 tests; fixed _topic_hex 0x-prefix bug; status → review.
