---
baseline_commit: 0e04db6dc8c2c2891a2daae9d45d31b8e82023c3
type: build
---

# Story 1B.4: Event Router & Normalizer

Status: done

## Story

As a **Kỹ sư Dữ liệu**,
I want **`EventRouter.route(log, block_timestamp)` kiểm tra contract whitelist và dispatch log đến đúng decoder (Uniswap V3 hoặc Aave V3)**,
so that **mọi raw log từ WSS subscription được normalized thành `TickDataEvent` hoặc silently dropped nếu không phải contract quan tâm — một interface duy nhất cho Track 1C ring buffer và Epic 2**.

## Acceptance Criteria

1. **AC1 — Module tồn tại:** `ingestion/router.py` export `EventRouter`.

2. **AC2 — Route Uniswap V3:** Log từ Uniswap V3 pool address → `UniswapV3Decoder.decode()` → trả về `TickDataEvent` với `protocol="uniswap_v3"`.

3. **AC3 — Route Aave V3:** Log từ Aave V3 Pool address → `AaveV3Decoder.decode()` → trả về `TickDataEvent` với `protocol="aave_v3"`.

4. **AC4 — Unknown contract → None:** Log từ contract không có trong whitelist → `return None` (không raise, không log).

5. **AC5 — Unknown topic propagates:** Log từ known contract nhưng topic0 unknown → `ValueError` từ decoder được propagate lên caller (không swallow).

6. **AC6 — Schema validation (optional but recommended):** Router có method `route_validated()` gọi `route()` rồi validate schema trước khi return.

7. **AC7 — Unit tests:** `tests/unit/test_router.py` cover:
   - Uniswap V3 log → TickDataEvent với protocol="uniswap_v3"
   - Aave V3 log → TickDataEvent với protocol="aave_v3"
   - Unknown address → None
   - Known address, unknown topic → ValueError propagated
   - route_validated() → schema valid output

8. **AC8 — Integration: all 7 event types covered** (3 Uniswap + 4 Aave) trong test suite.

## Tasks / Subtasks

- [x] **Task 1 — Implement EventRouter** (AC1–AC6)
  - [x] Tạo `ingestion/router.py`
  - [x] `__init__(self, whitelist: ContractWhitelist)` — store decoders
  - [x] `route(log, block_timestamp) -> TickDataEvent | None`
  - [x] `route_validated(log, block_timestamp) -> TickDataEvent | None` (cached validator)

- [x] **Task 2 — Factory helper** (AC1)
  - [x] `EventRouter.from_yaml(path)` classmethod tạo router với whitelist từ YAML

- [x] **Task 3 — Unit tests** (AC7, AC8)
  - [x] Tạo `tests/unit/test_router.py`
  - [x] Reuse fixtures từ `tests/fixtures/uniswap_v3_logs.py` và `tests/fixtures/aave_v3_logs.py`

## Dev Notes

**Loại story:** `[BUILD]` — blockedBy: 1B.1 (decoder), 1B.2 (decoder), 1B.3 (whitelist).

---

### Implementation Pattern

```python
# ingestion/router.py
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import jsonschema

from ingestion.decoders.aave_v3 import AaveV3Decoder
from ingestion.decoders.uniswap_v3 import PoolMeta, TickDataEvent, UniswapV3Decoder
from ingestion.whitelist import ContractWhitelist

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent.parent / "contracts" / "tick_data.schema.json"


def _load_schema() -> dict:
    with open(_SCHEMA_PATH) as f:
        return json.load(f)


class EventRouter:
    def __init__(self, whitelist: ContractWhitelist) -> None:
        self._whitelist = whitelist
        self._uniswap_decoder = UniswapV3Decoder()
        self._aave_decoder = AaveV3Decoder()
        self._schema: dict | None = None  # lazy-load for route_validated()

    @classmethod
    def from_yaml(cls, path: str | Path) -> "EventRouter":
        return cls(ContractWhitelist.from_yaml(path))

    def route(self, log: dict, block_timestamp: int) -> Optional[TickDataEvent]:
        """Route a raw log to the correct decoder.

        Returns TickDataEvent if log is from a known contract, None otherwise.
        Raises ValueError if contract is known but topic0 is unrecognized.
        """
        address = (
            log["address"].lower()
            if isinstance(log["address"], str)
            else "0x" + log["address"].hex()
        )
        entry = self._whitelist.get(address)
        if entry is None:
            return None  # Unknown contract — silently drop

        pool_meta = PoolMeta(token0=entry.pool_meta.token0, token1=entry.pool_meta.token1)

        if entry.protocol == "uniswap_v3":
            return self._uniswap_decoder.decode(log, pool_meta, block_timestamp)
        elif entry.protocol == "aave_v3":
            return self._aave_decoder.decode(log, pool_meta, block_timestamp)
        else:
            logger.warning(json.dumps({"event": "unknown_protocol", "protocol": entry.protocol, "address": address}))
            return None

    def route_validated(self, log: dict, block_timestamp: int) -> Optional[TickDataEvent]:
        """Like route(), but validates output against tick_data.schema.json."""
        event = self.route(log, block_timestamp)
        if event is not None:
            if self._schema is None:
                self._schema = _load_schema()
            jsonschema.validate(event.to_dict(), self._schema)
        return event
```

---

### Test Pattern

```python
# tests/unit/test_router.py
import json
import pytest
from pathlib import Path

from ingestion.router import EventRouter
from ingestion.whitelist import ContractWhitelist, WhitelistEntry
from ingestion.decoders.uniswap_v3 import PoolMeta

from tests.fixtures.uniswap_v3_logs import SWAP_LOG_1, POOL_ADDRESS as UNI_POOL, BLOCK_TS as UNI_BLOCK_TS
from tests.fixtures.aave_v3_logs import SUPPLY_LOG, AAVE_V3_POOL, BLOCK_TS as AAVE_BLOCK_TS

# Build whitelist in-memory (no YAML file needed for unit tests)
WHITELIST = ContractWhitelist({
    UNI_POOL.lower(): WhitelistEntry(
        protocol="uniswap_v3",
        pool_meta=PoolMeta(
            token0="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            token1="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
        ),
    ),
    AAVE_V3_POOL.lower(): WhitelistEntry(
        protocol="aave_v3",
        pool_meta=PoolMeta(
            token0="0x0000000000000000000000000000000000000000",
            token1="0x0000000000000000000000000000000000000000",
        ),
    ),
})

@pytest.fixture
def router():
    return EventRouter(WHITELIST)

def test_route_uniswap_swap(router):
    event = router.route(SWAP_LOG_1, UNI_BLOCK_TS)
    assert event is not None
    assert event.protocol == "uniswap_v3"
    assert event.event_type == "swap"

def test_route_aave_supply(router):
    event = router.route(SUPPLY_LOG, AAVE_BLOCK_TS)
    assert event is not None
    assert event.protocol == "aave_v3"
    assert event.event_type == "supply"

def test_unknown_address_returns_none(router):
    unknown_log = {**SWAP_LOG_1, "address": "0x" + "ee" * 20}
    assert router.route(unknown_log, UNI_BLOCK_TS) is None

def test_known_address_unknown_topic_raises(router):
    bad_log = {
        **SWAP_LOG_1,
        "topics": [bytes.fromhex("deadbeef" * 8)] + list(SWAP_LOG_1["topics"][1:]),
    }
    with pytest.raises(ValueError, match="Unknown Uniswap V3 topic"):
        router.route(bad_log, UNI_BLOCK_TS)

def test_route_validated_passes_schema(router):
    event = router.route_validated(SWAP_LOG_1, UNI_BLOCK_TS)
    assert event is not None  # no ValidationError raised

def test_all_uniswap_event_types(router):
    from tests.fixtures.uniswap_v3_logs import MINT_LOG_1, BURN_LOG_1, BLOCK_TS
    mint = router.route(MINT_LOG_1, BLOCK_TS)
    burn = router.route(BURN_LOG_1, BLOCK_TS)
    assert mint.event_type == "mint"
    assert burn.event_type == "burn"

def test_all_aave_event_types(router):
    from tests.fixtures.aave_v3_logs import BORROW_LOG, WITHDRAW_LOG, LIQUIDATION_LOG, BLOCK_TS
    borrow   = router.route(BORROW_LOG,     BLOCK_TS)
    withdraw = router.route(WITHDRAW_LOG,   BLOCK_TS)
    liq      = router.route(LIQUIDATION_LOG, BLOCK_TS)
    assert borrow.event_type   == "borrow"
    assert withdraw.event_type == "withdraw"
    assert liq.event_type      == "liquidation"
```

---

### File Structure After 1B.4

```
ingestion/
  __init__.py
  config.py
  client.py
  reconnect.py
  whitelist.py          ← NEW (1B.3)
  whitelist.yaml        ← NEW (1B.3)
  router.py             ← NEW (1B.4)
  decoders/
    __init__.py         ← NEW (1B.1)
    uniswap_v3.py       ← NEW (1B.1) — defines TickDataEvent, PoolMeta
    aave_v3.py          ← NEW (1B.2)
contracts/
  tick_data.schema.json ← EXISTING (Epic 0)
tests/
  fixtures/
    uniswap_v3_logs.py  ← NEW (1B.1)
    aave_v3_logs.py     ← NEW (1B.2)
  unit/
    test_uniswap_decoder.py  ← NEW (1B.1)
    test_aave_decoder.py     ← NEW (1B.2)
    test_whitelist.py        ← NEW (1B.3)
    test_router.py           ← NEW (1B.4)
```

---

### Route Logic Flow

```
raw log (from WSS / CSV replay)
        │
        ▼
EventRouter.route(log, block_ts)
        │
        ├─ log["address"].lower() → ContractWhitelist.get(address)
        │
        ├─ None → return None  (unknown contract, silent drop)
        │
        ├─ entry.protocol == "uniswap_v3"
        │       └─ UniswapV3Decoder.decode(log, pool_meta, block_ts)
        │               └─ TickDataEvent(protocol="uniswap_v3", event_type="swap"|"mint"|"burn")
        │
        └─ entry.protocol == "aave_v3"
                └─ AaveV3Decoder.decode(log, pool_meta, block_ts)
                        └─ TickDataEvent(protocol="aave_v3", event_type="supply"|"borrow"|"withdraw"|"liquidation")
```

---

### Critical Integration Note

**Track 1C (Ring Buffer)** sẽ consume output của `EventRouter.route()`. Interface contract:
```python
# Downstream consumer (1C.1+) expects:
event: TickDataEvent | None = router.route(log, block_ts)
if event:
    ring_buffer.write(event.to_dict())
```

**Epic 2 (Graph Builder)** sẽ read từ ring buffer. Schema phải khớp `tick_data.schema.json`. Do đó `route_validated()` nên được dùng trong production pipeline (1E.1 Integration) để catch schema violations early.

---

### Dependencies

- **1B.1** (done required): `UniswapV3Decoder`, `TickDataEvent`, `PoolMeta` từ `ingestion.decoders.uniswap_v3`
- **1B.2** (done required): `AaveV3Decoder` từ `ingestion.decoders.aave_v3`
- **1B.3** (done required): `ContractWhitelist`, `WhitelistEntry` từ `ingestion.whitelist`
- **jsonschema>=4.20.0**: already in `pyproject.toml`

### Project Conventions

- Python 3.12, pytest
- Tests là sync (decoder và router đều pure functions)
- `ruff check` cho linting
- Re-use fixture objects từ tests/fixtures/

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- RED: `pytest tests/unit/test_router.py` → ImportError.
- GREEN: 9 passed. Full suite 230 passed, 1 skipped (không liên quan).

### Completion Notes List

- `ingestion/router.py`: `EventRouter(whitelist)` + `route(log, block_ts) -> TickDataEvent | None` (unknown address→None; known address + unknown topic→ValueError propagate) + `route_validated` + `from_yaml`.
- **Perf:** `route_validated` dùng **cached compiled validator** (`_get_validator()`) thay vì `jsonschema.validate()` recompile mỗi call — áp dụng bài học từ 1D.2.
- `_log_address` xử lý cả `str` và `bytes`/`HexBytes` (web3 realtime cho address dạng str, nhưng defensive).
- Reuse fixtures 1B.1/1B.2; cover đủ 7 event type (3 Uniswap + 4 Aave) + route_validated + from_yaml.
- ruff không cài local (CI lint).

### File List

- `ingestion/router.py` (NEW)
- `tests/unit/test_router.py` (NEW)

## Change Log

- 2026-07-09 — Implemented Story 1B.4 EventRouter (dispatch + normalize + schema-validate); 9 tests; cached validator; status → review. Closes Track 1B.
