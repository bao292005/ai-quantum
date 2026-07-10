---
baseline_commit: 0e04db6dc8c2c2891a2daae9d45d31b8e82023c3
type: build
---

# Story 1C.4: AsyncIO-Safe Ring Buffer Wrapper

Status: done

## Story

As a **Kỹ sư Dữ liệu**,
I want **`AsyncRingBuffer(backend)` wrap bất kỳ `RingBufferProtocol` implementation nào bằng `asyncio.Lock()`**,
so that **pipeline coroutines (Track 1A WebSocket ingestion và Track 1B router) có thể write concurrently vào ring buffer mà không race condition, và Epic 2 GraphBuilder đọc được snapshot nhất quán**.

## Acceptance Criteria

1. **AC1 — Class tồn tại:** `core/ring_buffer.py` export `AsyncRingBuffer`.

2. **AC2 — Wraps any backend:** `AsyncRingBuffer(backend: RingBufferProtocol)` nhận bất kỳ implementation nào (DequeRingBuffer, NumpyRingBuffer).

3. **AC3 — Async write:** `async def write(event: dict)` acquire lock, call `backend.write(event)`, release lock.

4. **AC4 — Async read:** `async def read_all()` và `async def read_latest(n)` cũng acquire lock.

5. **AC5 — Sync pass-through:** `len(buf)` và `buf.capacity` đọc trực tiếp từ backend (no lock needed — atomic read).

6. **AC6 — Concurrent write safety:** 10 coroutines write 100 events each → total len == min(capacity, 1000). Không lost writes, không exception.

7. **AC7 — Context manager (optional but nice):** `async with buf.snapshot() as events: ...` — acquires lock, yields read_all(), releases lock. Prevents reads during write.

8. **AC8 — Unit tests:** `tests/unit/test_async_ring_buffer.py` cover:
   - Concurrent writes từ multiple coroutines → correct len
   - write/read_all round-trip via async
   - Lock prevents interleaved read-write (verify via mock)
   - Works với cả DequeRingBuffer và NumpyRingBuffer backend

## Tasks / Subtasks

- [x] **Task 1 — Implement AsyncRingBuffer** (AC1–AC5)
  - [x] Thêm `AsyncRingBuffer` vào `core/ring_buffer.py`
  - [x] `__init__(self, backend: RingBufferProtocol)` → `self._lock = asyncio.Lock()`
  - [x] `async def write(event: dict)` với `async with self._lock`
  - [x] `async def read_all()` và `async def read_latest(n)`
  - [x] `__len__()` và `capacity` sync pass-through

- [x] **Task 2 — Snapshot context manager** (AC7)
  - [x] `@asynccontextmanager async def snapshot(self)`

- [x] **Task 3 — Unit tests** (AC6, AC8)
  - [x] Tạo `tests/unit/test_async_ring_buffer.py`
  - [x] Concurrent write test với `asyncio.gather`

### Review Findings

- [x] [Review][Patch] (Decision resolved → option 2) Đã thêm `AsyncRingBufferProtocol` (runtime_checkable, async signatures) làm contract chính thức; docstring ghi rõ caveat runtime_checkable; thêm guard `__init__` từ chối async backend (raise TypeError, chặn silent-drop); test `test_satisfies_async_protocol` + `test_rejects_async_backend`. [core/ring_buffer.py]
- [x] [Review][Patch] Đã sửa `test_concurrent_writes` → 10 coroutine × 100 event = 1000 (capacity=1000, `len == min(capacity,1000)==1000`) + thêm `test_concurrent_writes_evict_at_capacity` (1000 writes vào capacity=500 → len==500). [tests/unit/test_async_ring_buffer.py]

## Dev Notes

**Loại story:** `[BUILD]` — blockedBy: 1C.1 (Protocol), 1C.2 (DequeRingBuffer).

**Project convention:** `pytest-asyncio` mode=auto — không cần `@pytest.mark.asyncio`. Tất cả `async def test_*` chạy tự động.

---

### Implementation Pattern

```python
# Thêm vào core/ring_buffer.py
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator


class AsyncRingBuffer:
    """asyncio.Lock-protected wrapper for any RingBufferProtocol backend.

    Design: single lock per buffer instance. Writers and readers contend.
    For the QuantumRadar pipeline (single asyncio event loop, ~100 events/sec),
    lock contention is negligible.
    """

    def __init__(self, backend: RingBufferProtocol) -> None:
        self._backend = backend
        self._lock = asyncio.Lock()

    @property
    def capacity(self) -> int:
        return self._backend.capacity  # atomic int read — no lock needed

    async def write(self, event: dict) -> None:
        """Acquire lock and write to backend."""
        async with self._lock:
            self._backend.write(event)

    async def read_all(self) -> list[dict]:
        """Acquire lock and return all events FIFO."""
        async with self._lock:
            return self._backend.read_all()

    async def read_latest(self, n: int) -> list[dict]:
        """Acquire lock and return n most recent events."""
        async with self._lock:
            return self._backend.read_latest(n)

    def __len__(self) -> int:
        return len(self._backend)  # atomic int read — no lock needed

    @asynccontextmanager
    async def snapshot(self) -> AsyncGenerator[list[dict], None]:
        """Context manager: hold lock for the entire read operation.

        Use when you need a consistent view during processing:

            async with buf.snapshot() as events:
                result = graph_builder.build(events)
        """
        async with self._lock:
            yield self._backend.read_all()
```

---

### Test Pattern

```python
# tests/unit/test_async_ring_buffer.py
import asyncio
import pytest
from core.ring_buffer import AsyncRingBuffer, DequeRingBuffer, NumpyRingBuffer


def _event(i: int) -> dict:
    return {"block_number": i, "log_index": i, "protocol": "uniswap_v3",
            "event_type": "swap", "pool_address": "0x" + "aa" * 20,
            "token0": "0x" + "bb" * 20, "token1": "0x" + "cc" * 20,
            "amount0": "100", "amount1": "-50",
            "tx_hash": "0x" + "dd" * 32, "block_timestamp": "2023-10-24T12:00:00Z"}


async def test_write_and_read():
    buf = AsyncRingBuffer(DequeRingBuffer(100))
    e = _event(1)
    await buf.write(e)
    result = await buf.read_all()
    assert result == [e]


async def test_concurrent_writes():
    """10 coroutines write 10 events each = 100 total, capacity=200."""
    capacity = 200
    buf = AsyncRingBuffer(DequeRingBuffer(capacity))

    async def writer(start: int):
        for i in range(10):
            await buf.write(_event(start + i))

    await asyncio.gather(*[writer(i * 10) for i in range(10)])
    assert len(buf) == 100


async def test_eviction_concurrent():
    """100 events into capacity=50 → exactly 50 remain."""
    buf = AsyncRingBuffer(DequeRingBuffer(50))
    await asyncio.gather(*[buf.write(_event(i)) for i in range(100)])
    assert len(buf) == 50


async def test_read_latest():
    buf = AsyncRingBuffer(DequeRingBuffer(100))
    for i in range(10):
        await buf.write(_event(i))
    latest = await buf.read_latest(3)
    assert len(latest) == 3
    assert latest[-1]["block_number"] == 9  # newest


async def test_snapshot_context_manager():
    buf = AsyncRingBuffer(DequeRingBuffer(10))
    for i in range(5):
        await buf.write(_event(i))
    async with buf.snapshot() as events:
        assert len(events) == 5
        assert events[0]["block_number"] == 0


async def test_capacity_passthrough():
    buf = AsyncRingBuffer(NumpyRingBuffer(42))
    assert buf.capacity == 42


async def test_len_passthrough():
    buf = AsyncRingBuffer(DequeRingBuffer(100))
    await buf.write(_event(1))
    assert len(buf) == 1


async def test_works_with_numpy_backend():
    buf = AsyncRingBuffer(NumpyRingBuffer(100))
    for i in range(20):
        await buf.write(_event(i))
    result = await buf.read_all()
    assert len(result) == 20
    assert result[0]["block_number"] == 0  # FIFO order preserved
```

---

### Why asyncio.Lock and not threading.Lock?

The QuantumRadar pipeline is **single-process asyncio** (Architecture Decision AD-2). All coroutines share one event loop. `asyncio.Lock` is the correct primitive because:
- No thread switching → no GIL overhead
- `async with self._lock` yields to event loop when waiting → no blocking
- `threading.Lock` would be incorrect here (would block the event loop)

**EXCEPTION:** The MPS engine (Epic 2) runs in a separate `multiprocessing.Process`. It does NOT share AsyncRingBuffer directly — it receives a snapshot via `multiprocessing.Queue`. AsyncRingBuffer is for the asyncio pipeline only.

---

### Integration with Pipeline (1E.1 context)

```python
# Future: ingestion/pipeline.py (1E.1)
# AsyncRingBuffer created once, shared across coroutines:

ring_buffer = AsyncRingBuffer(DequeRingBuffer(capacity=1000))

# Writer (Track 1A → 1B):
async def on_log(log: dict, block_ts: int):
    event = router.route(log, block_ts)
    if event:
        await ring_buffer.write(event.to_dict())

# Reader (Epic 2 GraphBuilder feeder):
async def feed_graph_builder():
    while True:
        async with ring_buffer.snapshot() as events:
            if events:
                mps_queue.put_nowait(events)
        await asyncio.sleep(0.1)  # 100ms cadence
```

---

### File Structure After 1C.4

```
core/
  __init__.py           ← NEW (1C.1)
  ring_buffer.py        ← GROWS across 1C.1–1C.4:
                           RingBufferProtocol  (1C.1)
                           DequeRingBuffer     (1C.2)
                           NumpyRingBuffer     (1C.3)
                           AsyncRingBuffer     (1C.4)
tests/unit/
  test_ring_buffer_interface.py  (1C.1)
  test_deque_ring_buffer.py      (1C.2)
  test_numpy_ring_buffer.py      (1C.3)
  test_async_ring_buffer.py      (1C.4)
```

---

### Project Conventions

- Python 3.12, `pytest-asyncio` mode=auto
- Không cần `@pytest.mark.asyncio` — `async def test_*` chạy tự động
- `from core.ring_buffer import AsyncRingBuffer, DequeRingBuffer`

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- RED: `pytest tests/unit/test_async_ring_buffer.py` → ImportError (AsyncRingBuffer chưa tồn tại).
- GREEN: 10 passed sau khi implement class + snapshot CM.
- Regression: full suite 174 passed, 1 skipped (test_client_connect — mock WSS không chạy trên :8546, không liên quan).

### Completion Notes List

- Thêm `AsyncRingBuffer` vào `core/ring_buffer.py`: `asyncio.Lock()` bảo vệ `write/read_all/read_latest`; `capacity` và `__len__` là atomic int read nên pass-through không cần lock.
- `snapshot()` là `@asynccontextmanager` giữ lock suốt quá trình đọc → yield `read_all()`, ngăn write interleave khi consumer đang xử lý.
- Test bổ sung `test_lock_serializes_write_and_snapshot`: xác minh mutual exclusion — write bị block cho tới khi snapshot context thoát (kiểm qua thứ tự event + độ dài buffer).
- **Lưu ý về Protocol:** `RingBufferProtocol` là `@runtime_checkable` nên chỉ kiểm tra sự HIỆN DIỆN của tên method, không kiểm tra async. Vì vậy `isinstance(AsyncRingBuffer(...), RingBufferProtocol)` trả `True` dù các method là async → KHÔNG được coi AsyncRingBuffer là drop-in sync buffer. Test đổi thành kiểm tra `buf._backend` là Protocol và ghi chú rõ trong test.
- Hoạt động với cả `DequeRingBuffer` và `NumpyRingBuffer` backend (AC2 verified).
- ruff không cài local (CI chạy lint); imports `asyncio`, `asynccontextmanager`, `AsyncGenerator` đều dùng, không có import thừa.

### File List

- `core/ring_buffer.py` (UPDATE — add AsyncRingBuffer + imports asyncio/contextlib/typing)
- `tests/unit/test_async_ring_buffer.py` (NEW)

## Change Log

- 2026-07-09 — Implemented Story 1C.4 AsyncRingBuffer (asyncio.Lock wrapper + snapshot CM); added 10 unit tests incl. concurrent-write and lock-serialization; status → review.
