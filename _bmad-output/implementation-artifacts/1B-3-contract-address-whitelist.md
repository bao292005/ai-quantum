---
baseline_commit: 0e04db6dc8c2c2891a2daae9d45d31b8e82023c3
type: build
---

# Story 1B.3: Contract Address Whitelist

Status: done

## Story

As a **Kỹ sư Dữ liệu**,
I want **`ContractWhitelist` load danh sách contract addresses và protocol metadata từ YAML config**,
so that **EventRouter (1B.4) có thể lookup nhanh protocol và pool metadata từ `log["address"]` để route đến đúng decoder**.

## Acceptance Criteria

1. **AC1 — Module tồn tại:** `ingestion/whitelist.py` export `ContractWhitelist`, `WhitelistEntry`.

2. **AC2 — Load từ YAML:** `ContractWhitelist.from_yaml(path)` đọc `ingestion/whitelist.yaml` và parse thành dict `{address_lower: WhitelistEntry}`.

3. **AC3 — Get by address:** `whitelist.get("0xABC...".lower())` trả về `WhitelistEntry` nếu tồn tại, `None` nếu không.

4. **AC4 — Case-insensitive:** Address matching luôn case-insensitive (normalize về lowercase khi load và khi lookup).

5. **AC5 — WhitelistEntry fields:** Mỗi entry có `protocol: str` và `pool_meta: PoolMeta` (token0, token1).

6. **AC6 — Default whitelist file bundled:** `ingestion/whitelist.yaml` chứa ít nhất:
   - 1 Uniswap V3 pool (USDC/WETH 0.05%)
   - Aave V3 Pool mainnet

7. **AC7 — Unit tests:** `tests/unit/test_whitelist.py` cover:
   - Load từ YAML → assert entry count và field values
   - get() known address → returns entry
   - get() unknown address → returns None
   - get() với uppercase address → still returns entry (case-insensitive)
   - WhitelistEntry.pool_meta.token0/token1 correct

## Tasks / Subtasks

- [x] **Task 1 — Implement ContractWhitelist** (AC1–AC5)
  - [x] Tạo `ingestion/whitelist.py`
  - [x] `@dataclass class WhitelistEntry: protocol: str; pool_meta: PoolMeta`
  - [x] `class ContractWhitelist` với `_entries: dict[str, WhitelistEntry]`
  - [x] `classmethod from_yaml(cls, path: str | Path) -> ContractWhitelist`
  - [x] `def get(self, address: str) -> WhitelistEntry | None`
  - [x] `def __contains__(self, address: str) -> bool`

- [x] **Task 2 — Tạo whitelist.yaml** (AC6)
  - [x] Tạo `ingestion/whitelist.yaml` với 3 entries (2 Uniswap V3 + Aave V3)

- [x] **Task 3 — Unit tests** (AC7)
  - [x] Tạo `tests/unit/test_whitelist.py`
  - [x] Test với temporary YAML file (dùng `tmp_path` fixture của pytest)

## Dev Notes

**Loại story:** `[BUILD]` — blockedBy: 1B.1 (cần `PoolMeta` từ `ingestion.decoders.uniswap_v3`).

---

### Implementation Pattern

```python
# ingestion/whitelist.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from ingestion.decoders.uniswap_v3 import PoolMeta


@dataclass
class WhitelistEntry:
    protocol: str       # "uniswap_v3" | "aave_v3"
    pool_meta: PoolMeta # token0, token1 (ZERO_ADDRESS for Aave single-asset pools)


class ContractWhitelist:
    def __init__(self, entries: dict[str, WhitelistEntry]) -> None:
        # keys already normalized to lowercase
        self._entries = entries

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ContractWhitelist":
        with open(path) as f:
            raw: dict = yaml.safe_load(f)
        entries: dict[str, WhitelistEntry] = {}
        for addr, meta in (raw or {}).items():
            entries[addr.lower()] = WhitelistEntry(
                protocol=meta["protocol"],
                pool_meta=PoolMeta(
                    token0=meta.get("token0", "0x0000000000000000000000000000000000000000"),
                    token1=meta.get("token1", "0x0000000000000000000000000000000000000000"),
                ),
            )
        return cls(entries)

    def get(self, address: str) -> Optional[WhitelistEntry]:
        return self._entries.get(address.lower())

    def __contains__(self, address: str) -> bool:
        return address.lower() in self._entries

    def __len__(self) -> int:
        return len(self._entries)
```

---

### Whitelist YAML Format

```yaml
# ingestion/whitelist.yaml
# Format: contract_address: {protocol, token0, token1}
# All addresses should be lowercase.
# For Aave V3 (single-contract, multi-reserve), token0/token1 = zero address.
# AaveV3Decoder extracts actual reserve addresses from event topics.

# --- Uniswap V3 Pools ---
"0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640":
  protocol: uniswap_v3
  token0: "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC
  token1: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"  # WETH

"0x4e68ccd3e89f51c3074ca5072bbac773960dfa36":
  protocol: uniswap_v3
  token0: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"  # WETH
  token1: "0xdac17f958d2ee523a2206206994597c13d831ec7"  # USDT

# --- Aave V3 Pool (handles all reserves) ---
"0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2":
  protocol: aave_v3
  token0: "0x0000000000000000000000000000000000000000"
  token1: "0x0000000000000000000000000000000000000000"
```

---

### Test Pattern

```python
# tests/unit/test_whitelist.py
import textwrap
import pytest
from ingestion.whitelist import ContractWhitelist

YAML_CONTENT = textwrap.dedent("""\
    "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640":
      protocol: uniswap_v3
      token0: "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
      token1: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2":
      protocol: aave_v3
      token0: "0x0000000000000000000000000000000000000000"
      token1: "0x0000000000000000000000000000000000000000"
""")

@pytest.fixture
def whitelist(tmp_path):
    p = tmp_path / "whitelist.yaml"
    p.write_text(YAML_CONTENT)
    return ContractWhitelist.from_yaml(p)

def test_load_count(whitelist):
    assert len(whitelist) == 2

def test_get_known(whitelist):
    entry = whitelist.get("0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640")
    assert entry is not None
    assert entry.protocol == "uniswap_v3"
    assert entry.pool_meta.token0 == "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"

def test_get_unknown(whitelist):
    assert whitelist.get("0x" + "ff" * 20) is None

def test_case_insensitive(whitelist):
    # uppercase should still match
    assert whitelist.get("0x88E6A0C2DDD26FEEB64F039A2C41296FCB3F5640") is not None

def test_contains(whitelist):
    assert "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2" in whitelist
    assert "0x" + "aa" * 20 not in whitelist

def test_aave_entry(whitelist):
    entry = whitelist.get("0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2")
    assert entry.protocol == "aave_v3"
    assert entry.pool_meta.token0 == "0x0000000000000000000000000000000000000000"
```

---

### Dependencies

- **PyYAML** (`pyyaml`): Check `pyproject.toml` — nếu chưa có thì thêm vào `[project] dependencies`. Likely already present since it's common.
- **1B.1**: `PoolMeta` import từ `ingestion.decoders.uniswap_v3`
- **1B.4** (Router): sẽ import `ContractWhitelist` từ `ingestion.whitelist`

### Check PyYAML

```bash
python -c "import yaml; print(yaml.__version__)"
```

Nếu chưa có: thêm `"pyyaml>=6.0"` vào `pyproject.toml` dependencies.

### Project Conventions

- Python 3.12, pytest
- Tests là sync (no asyncio)
- `ruff check` cho linting
- `tmp_path` pytest fixture cho temp files

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- RED: `pytest tests/unit/test_whitelist.py` → ImportError.
- GREEN: 7 passed.

### Completion Notes List

- `ingestion/whitelist.py`: `WhitelistEntry(protocol, pool_meta)`, `ContractWhitelist.from_yaml/get/__contains__/__len__`; keys normalize lowercase; case-insensitive lookup.
- `ingestion/whitelist.yaml`: 2 Uniswap V3 pool (USDC/WETH, WETH/USDT) + Aave V3 Pool (token0/1=zero, decoder tự extract reserve từ topic).
- Thêm test `test_bundled_whitelist_yaml_loads` verify file ship kèm load được + có cả uniswap_v3/aave_v3.
- `pyyaml 6.0.1` đã cài — thêm khai báo `pyyaml>=6.0` vào `pyproject.toml` (trước đó thiếu).
- ruff không cài local (CI lint).

### File List

- `ingestion/whitelist.py` (NEW)
- `ingestion/whitelist.yaml` (NEW)
- `tests/unit/test_whitelist.py` (NEW)
- `pyproject.toml` (UPDATE — add pyyaml>=6.0)

## Change Log

- 2026-07-09 — Implemented Story 1B.3 ContractWhitelist + bundled whitelist.yaml; 7 tests; declared pyyaml; status → review.
