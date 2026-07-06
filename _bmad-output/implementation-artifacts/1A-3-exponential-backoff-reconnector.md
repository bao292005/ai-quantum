---
baseline_commit: aa9487a
type: build
---

# Story 1A.3: Exponential Backoff Reconnector

Status: ready-for-dev

## Story

As a **Kỹ sư Dữ liệu**,
I want **decorator `@auto_reconnect(max_retries=None, base=0.5, cap=30)` tự retry coroutine khi WebSocket đứt**,
so that **luồng ingestion không tắt khi mạng chập chờn, không cần consumer lo xử lý reconnect**.

## Acceptance Criteria

1. **AC1 — Module tồn tại:** `ingestion/reconnect.py` export `auto_reconnect`.

2. **AC2 — Exponential delay sequence:** Delay sequence: `0.5 → 1 → 2 → 4 → 8 → 16 → 30 → 30 → ...` (cap tại 30s). Formula: `min(base * 2**attempt, cap)`.

3. **AC3 — Unlimited retry mặc định:** `max_retries=None` → retry vô hạn. `max_retries=N` → sau N lần thất bại liên tiếp raise exception gốc.

4. **AC4 — Structured JSON log mỗi retry:** Log dạng `{"event": "reconnect", "attempt": N, "delay_s": X.X, "error": "..."}` ra stdout (sử dụng `logging` với JSON formatter hoặc `json.dumps`).

5. **AC5 — Pass-through khi thành công:** Nếu coroutine chạy xong không exception → return bình thường, không retry.

6. **AC6 — Unit tests:** `tests/unit/test_reconnect.py` cover:
   - Coroutine fail 3 lần rồi thành công → gọi đúng 4 lần
   - Delay sequence đúng 0.5→1→2→4→8→16→30
   - `max_retries=2` fail liên tục → raise sau 2 lần
   - Coroutine thành công ngay → gọi 1 lần, không sleep

## Tasks / Subtasks

- [ ] **Task 1 — Implement auto_reconnect decorator** (AC1, AC2, AC3, AC4, AC5)
  - [ ] Dùng `functools.wraps` để preserve function signature
  - [ ] Detect reconnect-triggering exceptions: `ConnectionError`, `ConnectionResetError`, `websockets.exceptions.ConnectionClosed` (import optional — catch `Exception` type check)
  - [ ] Implement delay với `asyncio.sleep(delay)`
  - [ ] Log bằng `logging.getLogger(__name__)` với JSON format

- [ ] **Task 2 — Unit tests** (AC6)
  - [ ] Dùng `AsyncMock` cho coroutine giả lập fail/success
  - [ ] Mock `asyncio.sleep` để test không bị chậm
  - [ ] Verify số lần gọi và argument delay

## Dev Notes

**Loại story:** `[BUILD]` — blockedBy: 1A.2 (context về exception types từ EthereumClient).

**Decorator pattern cho async function:**
```python
import asyncio
import functools
import json
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

RECONNECT_EXCEPTIONS = (
    ConnectionError,
    ConnectionResetError,
    OSError,
)

def auto_reconnect(max_retries: int | None = None, base: float = 0.5, cap: float = 30.0):
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            while True:
                try:
                    return await fn(*args, **kwargs)
                except RECONNECT_EXCEPTIONS as exc:
                    if max_retries is not None and attempt >= max_retries:
                        raise
                    delay = min(base * (2 ** attempt), cap)
                    logger.warning(json.dumps({
                        "event": "reconnect",
                        "attempt": attempt + 1,
                        "delay_s": delay,
                        "error": str(exc),
                        "function": fn.__qualname__,
                    }))
                    await asyncio.sleep(delay)
                    attempt += 1
        return wrapper
    return decorator
```

**Delay sequence verification:**
```
attempt=0: min(0.5 * 2^0, 30) = 0.5
attempt=1: min(0.5 * 2^1, 30) = 1.0
attempt=2: min(0.5 * 2^2, 30) = 2.0
attempt=3: min(0.5 * 2^3, 30) = 4.0
attempt=4: min(0.5 * 2^4, 30) = 8.0
attempt=5: min(0.5 * 2^5, 30) = 16.0
attempt=6: min(0.5 * 2^6, 30) = 30.0  ← cap
attempt=7: min(0.5 * 2^7, 30) = 30.0  ← cap maintained
```

**Test pattern (asyncio_mode=auto đã set — không cần mark):**
```python
# tests/unit/test_reconnect.py
import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from ingestion.reconnect import auto_reconnect

async def test_retry_then_succeed():
    call_count = 0
    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 4:
            raise ConnectionError("drop")

    decorated = auto_reconnect()(flaky)
    with patch("ingestion.reconnect.asyncio.sleep", AsyncMock()):
        await decorated()
    assert call_count == 4

async def test_delay_sequence():
    delays = []
    async def always_fail():
        raise ConnectionError("fail")

    decorated = auto_reconnect(max_retries=3, base=0.5, cap=30)(always_fail)
    async def capture_sleep(delay):
        delays.append(delay)
    with patch("ingestion.reconnect.asyncio.sleep", capture_sleep):
        with pytest.raises(ConnectionError):
            await decorated()
    assert delays == [0.5, 1.0, 2.0]
```

**Lưu ý websockets exception:** Story 0.5 dùng `websockets>=12.0`. Exception của websockets: `websockets.exceptions.ConnectionClosed`. Nếu muốn catch explicit thêm vào tuple. Tuy nhiên story này không import websockets trực tiếp — catch `OSError` và `ConnectionError` là đủ cho PoC vì web3.py wrap chúng.

**Không dùng `tenacity`** — implement thủ công để kiểm soát delay sequence và logging format.

### Project Structure Notes

```
ingestion/
  reconnect.py       ← TẠO MỚI
tests/
  unit/
    test_reconnect.py ← TẠO MỚI
```

### References

- `ingestion/client.py` — exception types từ 1A.2
- `_bmad-output/epics.md#Story 1A.3`
- Story 1A.4: `stream_new_heads` sẽ wrap bằng `@auto_reconnect`
- Architecture AD-1: asyncio I/O — mọi retry phải dùng `asyncio.sleep`, không `time.sleep`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

- `ingestion/reconnect.py` (NEW)
- `tests/unit/test_reconnect.py` (NEW)
