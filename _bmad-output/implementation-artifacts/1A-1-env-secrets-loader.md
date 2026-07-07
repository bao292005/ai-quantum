---
baseline_commit: 55c0cec9cf4d68710d43aee977f63ec0d16bb522
type: build
---

# Story 1A.1: Environment & Secrets Loader

Status: review

## Story

As a **Kỹ sư Dữ liệu**,
I want **một module đọc `.env` (WSS_URL, ALCHEMY_KEY) với validation và trả về dataclass `IngestionConfig`**,
so that **không hard-code credential và mọi Track 1A-1E import cùng một interface cấu hình**.

## Acceptance Criteria

1. **AC1 — Module tồn tại:** `ingestion/config.py` export `load() -> IngestionConfig` và `ConfigError`.

2. **AC2 — Dataclass typed:** `IngestionConfig` là `dataclass` với ít nhất các field:
   - `wss_url: str` (required — biến env `WSS_URL`)
   - `wss_fallback_url: str | None` (optional — `WSS_FALLBACK_URL`, default `None`)
   - `alchemy_key: str | None` (optional — `ALCHEMY_KEY`, default `None`)
   - `etherscan_api_key: str | None` (optional — `ETHERSCAN_API_KEY`, default `None`)

3. **AC3 — Raise ConfigError:** Nếu `WSS_URL` không tồn tại hoặc rỗng, raise `ConfigError` với message rõ ràng.

4. **AC4 — .env.example:** File `.env.example` tồn tại ở project root với tất cả env var được comment hướng dẫn.

5. **AC5 — pyproject.toml include ingestion:** `[tool.setuptools.packages.find] include` phải thêm `"ingestion*"` để package được đóng gói đúng.

6. **AC6 — Unit tests:** `tests/unit/test_config.py` cover:
   - load() thành công khi `WSS_URL` có trong env
   - ConfigError khi `WSS_URL` thiếu
   - Optional fields default là `None` khi không set

7. **AC7 — Module init:** `ingestion/__init__.py` tồn tại (có thể rỗng) để package hợp lệ.

## Tasks / Subtasks

- [x] **Task 1 — Tạo ingestion package** (AC5, AC7)
  - [x] Tạo `ingestion/__init__.py` (rỗng)
  - [x] Cập nhật `pyproject.toml`: thêm `"ingestion*"` vào `include` list
  - [x] Retire legacy story overlap: ghi note trong `_bmad-output/sprint-status.yaml` rằng `1-1-web3-rpc-websocket-connection` được thay thế bởi 1A.1-1A.4 (không xóa file để preserve history)

- [x] **Task 2 — Implement config.py** (AC1, AC2, AC3)
  - [x] Dùng `os.environ` hoặc `python-dotenv` để đọc env
  - [x] Tạo `@dataclass class IngestionConfig` với 4 fields trên
  - [x] Hàm `load() -> IngestionConfig`: đọc env, validate WSS_URL, raise `ConfigError` nếu thiếu
  - [x] `class ConfigError(Exception): pass`

- [x] **Task 3 — Tạo .env.example** (AC4)
  - [x] Ghi rõ từng biến: mục đích, ví dụ value, required/optional

- [x] **Task 4 — Viết unit tests** (AC6)
  - [x] `tests/unit/test_config.py`
  - [x] Dùng `monkeypatch.setenv` của pytest để set/unset biến env trong test
  - [x] Không cần `@pytest.mark.asyncio` (module này sync)

## Dev Notes

**Loại story:** `[BUILD]` — output là module Python production + tests.

**CRITICAL — Legacy overlap:** Story `1-1-web3-rpc-websocket-connection` đang ở `ready-for-dev` trong sprint-status.yaml và cover cùng phạm vi 1A.1-1A.4. **Đừng implement nó.** Track 1A stories (1A.1-1A.5) là bản refactor atomic để thay thế. Sau khi 1A.1-1A.4 done, đổi status `1-1-web3-rpc-websocket-connection` → `done` (retired/superseded).

**CRITICAL — ingestion/ chưa tồn tại:** Package `ingestion/` chưa có trong repo. Story này tạo skeleton. **Phải tạo `ingestion/__init__.py` trước khi import bất cứ gì**.

**pyproject.toml hiện tại (phải cập nhật):**
```toml
[tool.setuptools.packages.find]
include = ["core*", "tools*"]   # ← THÊM "ingestion*" vào đây
```
Sau khi sửa:
```toml
include = ["core*", "tools*", "ingestion*"]
```

**Dependency:** Story này chỉ dùng stdlib (`os`, `dataclasses`). Không cần thêm package vào `pyproject.toml` dependencies (python-dotenv là optional — dùng `os.environ` là đủ cho PoC).

**Pattern ưu tiên — stdlib only:**
```python
# ingestion/config.py
import os
from dataclasses import dataclass

class ConfigError(Exception):
    pass

@dataclass
class IngestionConfig:
    wss_url: str
    wss_fallback_url: str | None = None
    alchemy_key: str | None = None
    etherscan_api_key: str | None = None

def load() -> IngestionConfig:
    wss_url = os.environ.get("WSS_URL", "").strip()
    if not wss_url:
        raise ConfigError("WSS_URL is required but not set or empty")
    return IngestionConfig(
        wss_url=wss_url,
        wss_fallback_url=os.environ.get("WSS_FALLBACK_URL") or None,
        alchemy_key=os.environ.get("ALCHEMY_KEY") or None,
        etherscan_api_key=os.environ.get("ETHERSCAN_API_KEY") or None,
    )
```

**Test pattern (asyncio_mode=auto đã set, nhưng test này sync):**
```python
# tests/unit/test_config.py
import pytest
from ingestion.config import load, ConfigError

def test_load_success(monkeypatch):
    monkeypatch.setenv("WSS_URL", "wss://localhost:8546")
    cfg = load()
    assert cfg.wss_url == "wss://localhost:8546"
    assert cfg.alchemy_key is None

def test_load_missing_wss_url(monkeypatch):
    monkeypatch.delenv("WSS_URL", raising=False)
    with pytest.raises(ConfigError):
        load()
```

**Env var naming (align với Story 1R.1 decision doc):**
- `WSS_URL` — primary WSS endpoint (Alchemy, Infura, etc.)
- `WSS_FALLBACK_URL` — fallback endpoint
- `ALCHEMY_KEY` — Alchemy API key (embedded trong WSS_URL hoặc dùng riêng)
- `ETHERSCAN_API_KEY` — cho Story 1E.2 reconciliation tool

### Project Structure Notes

```
ingestion/
  __init__.py        ← TẠO MỚI (rỗng)
  config.py          ← TẠO MỚI
tests/
  unit/
    test_config.py   ← TẠO MỚI
.env.example         ← TẠO MỚI (project root)
pyproject.toml       ← UPDATE (thêm ingestion* vào include)
```

### References

- `pyproject.toml` — cần update include list
- `_bmad-output/epics.md#Story 1A.1` — story gốc
- `_bmad-output/implementation-artifacts/1R-1-data-source-assessment.md` — env var decision
- Story 1A.2: `ingestion/client.py` import `IngestionConfig` từ story này
- Legacy: `_bmad-output/implementation-artifacts/1-1-web3-rpc-websocket-connection.md` — superseded

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

None — implementation straightforward, stdlib only.

### Completion Notes List

- Tạo `ingestion/` package với `__init__.py` và `config.py` (stdlib only: os + dataclasses)
- `IngestionConfig` dataclass với 4 fields (wss_url required, 3 optional)
- `load()` validate WSS_URL và raise `ConfigError` nếu rỗng/thiếu
- `pyproject.toml` đã thêm `"ingestion*"` vào include list
- `.env.example` ghi rõ required/optional với dev/CI note
- 7 unit tests — tất cả pass; 92/92 full suite — no regressions
- Legacy story `1-1-web3-rpc-websocket-connection` đã được đổi sang `done` trong sprint-status.yaml

### File List

- `ingestion/__init__.py` (NEW)
- `ingestion/config.py` (NEW)
- `tests/unit/test_config.py` (NEW)
- `.env.example` (NEW)
- `pyproject.toml` (UPDATE — thêm `"ingestion*"` vào include)
- `_bmad-output/sprint-status.yaml` (UPDATE — 1A-1 → review, 1-1-web3 → done)
