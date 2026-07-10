---
baseline_commit: 0e04db6dc8c2c2891a2daae9d45d31b8e82023c3
type: build
---

# Story 1C.2: Deque Ring Buffer

Status: done

## Story

As a **Kỹ sư Dữ liệu**,
I want **`DequeRingBuffer(capacity=1000)` implement `RingBufferProtocol` dùng `collections.deque(maxlen=capacity)`**,
so that **pipeline có implementation đơn giản, thread-safe với GIL, eviction tự động O(1) cho real-time ingestion**.

## Acceptance Criteria

1. **AC1 — Class tồn tại:** `core/ring_buffer.py` export `DequeRingBuffer`.

2. **AC2 — Implements Protocol:** `isinstance(DequeRingBuffer(10), RingBufferProtocol)` → `True`.

3. **AC3 — O(1) write với auto-eviction:** `write(event)` thêm event vào cuối deque. Khi `len == capacity`, oldest event bị evict tự động bởi `deque(maxlen=...)`. Không cần explicit eviction code.

4. **AC4 — read_all() FIFO order:** Trả về `list(self._buf)` — oldest first, newest last.

5. **AC5 — read_latest(n):** Trả về `list(self._buf)[-n:]` hoặc tất cả nếu `n >= len`.

6. **AC6 — capacity property:** `DequeRingBuffer(50).capacity == 50`.

7. **AC7 — Eviction test:** Write `capacity + 5` events → `len == capacity`, oldest events đã bị evict.

8. **AC8 — Unit tests:** `tests/unit/test_deque_ring_buffer.py` cover:
   - write/read round-trip
   - eviction sau khi vượt capacity
   - read_all() returns FIFO order
   - read_latest(n) với n < len, n == len, n > len
   - len() correct sau mỗi write
   - isinstance check với Protocol

## Tasks / Subtasks

- [x] **Task 1 — Implement DequeRingBuffer** (AC1–AC6)
  - [x] Add `DequeRingBuffer` class vào `core/ring_buffer.py`
  - [x] `__init__(self, capacity: int = 1000)` → `self._buf = deque(maxlen=capacity)`
  - [x] Implement 5 methods của Protocol
  - [x] `capacity` dùng `@property` trả về `self._buf.maxlen`

- [x] **Task 2 — Unit tests** (AC7, AC8)
  - [x] Tạo `tests/unit/test_deque_ring_buffer.py`

### Review Findings

- [x] [Review][Patch] Đã thêm ghi chú contract "events lưu theo tham chiếu / coi như immutable" vào docstring `DequeRingBuffer` (và `NumpyRingBuffer`). [core/ring_buffer.py]
- [x] [Review][Patch] Đã canh `test_eviction_at_capacity` về `capacity + 5` theo AC7 (assert `[5,6,7,8,9]`). [tests/unit/test_deque_ring_buffer.py]

## Dev Notes

**Loại story:** `[BUILD]` — blockedBy: 1C.1 (Protocol phải exist trước).

---

### Implementation Pattern

```python
# Thêm vào core/ring_buffer.py (sau RingBufferProtocol)
from collections import deque


class DequeRingBuffer:
    """Ring buffer backed by collections.deque.

    GIL-protected for single-threaded asyncio pipeline.
    Auto-evicts oldest event when capacity is reached.
    """

    def __init__(self, capacity: int = 1000) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0, got {capacity}")
        self._buf: deque[dict] = deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        return self._buf.maxlen  # type: ignore[return-value]

    def write(self, event: dict) -> None:
        """O(1) insert. Oldest event evicted automatically when full."""
        self._buf.append(event)

    def read_all(self) -> list[dict]:
        """Return all events in FIFO order (oldest first)."""
        return list(self._buf)

    def read_latest(self, n: int) -> list[dict]:
        """Return the n most recent events. Returns all if n >= len."""
        if n <= 0:
            return []
        return list(self._buf)[-n:]

    def __len__(self) -> int:
        return len(self._buf)
```

---

### Test Pattern

```python
# tests/unit/test_deque_ring_buffer.py
import pytest
from core.ring_buffer import DequeRingBuffer, RingBufferProtocol


def _event(block: int, idx: int = 0) -> dict:
    """Minimal tick_data event dict for testing."""
    return {
        "block_number": block,
        "block_timestamp": "2023-10-24T12:00:00Z",
        "protocol": "uniswap_v3",
        "event_type": "swap",
        "pool_address": "0x" + "aa" * 20,
        "token0": "0x" + "bb" * 20,
        "token1": "0x" + "cc" * 20,
        "amount0": "1000",
        "amount1": "-500",
        "tx_hash": "0x" + "dd" * 32,
        "log_index": idx,
    }


def test_isinstance_protocol():
    assert isinstance(DequeRingBuffer(10), RingBufferProtocol)


def test_capacity():
    buf = DequeRingBuffer(50)
    assert buf.capacity == 50


def test_write_and_read():
    buf = DequeRingBuffer(10)
    e = _event(100)
    buf.write(e)
    assert len(buf) == 1
    assert buf.read_all() == [e]


def test_fifo_order():
    buf = DequeRingBuffer(10)
    events = [_event(i) for i in range(5)]
    for e in events:
        buf.write(e)
    result = buf.read_all()
    assert result == events  # oldest first


def test_eviction_at_capacity():
    capacity = 5
    buf = DequeRingBuffer(capacity)
    for i in range(capacity + 3):
        buf.write(_event(i))
    assert len(buf) == capacity
    # Oldest events (0, 1, 2) should be evicted
    block_numbers = [e["block_number"] for e in buf.read_all()]
    assert block_numbers == [3, 4, 5, 6, 7]


def test_read_latest_n_lt_len():
    buf = DequeRingBuffer(10)
    for i in range(5):
        buf.write(_event(i))
    latest = buf.read_latest(3)
    assert len(latest) == 3
    assert [e["block_number"] for e in latest] == [2, 3, 4]  # newest 3


def test_read_latest_n_gt_len():
    buf = DequeRingBuffer(10)
    buf.write(_event(1))
    assert buf.read_latest(100) == [_event(1)]


def test_read_latest_zero():
    buf = DequeRingBuffer(10)
    buf.write(_event(1))
    assert buf.read_latest(0) == []


def test_invalid_capacity():
    with pytest.raises(ValueError):
        DequeRingBuffer(0)
```

---

### Why `collections.deque` and not `list`?

| Feature | `deque(maxlen=N)` | `list` |
|---|---|---|
| `append()` | O(1) | O(1) amortized |
| Auto-evict oldest | ✓ built-in | ✗ manual `list.pop(0)` O(n) |
| `popleft()` | O(1) | `pop(0)` is O(n) |
| Thread safety | GIL-protected for atomic ops | same |

**Verdict:** `deque(maxlen=capacity)` is perfect for this use case. Auto-eviction is built-in and O(1).

---

### Relationship to NFR4

NFR4 requires "10 most recent blocks in RAM". The default `capacity=1000` covers approximately:
- Ethereum mainnet: ~5 transactions/block × 2 events/tx = ~10 events/block
- Busy DeFi blocks can have 100+ events
- Safe default: `1000` events ≈ 10-100 blocks depending on protocol activity
- Pipeline orchestrator (1E.1) can override capacity via `DequeRingBuffer(capacity=N)`

---

### Project Conventions

- Python 3.12, pytest (sync tests)
- `ruff check` — no unused imports
- `from core.ring_buffer import DequeRingBuffer, RingBufferProtocol`

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- RED: `pytest tests/unit/test_deque_ring_buffer.py` → ImportError (DequeRingBuffer chưa tồn tại).
- GREEN: 12 passed sau khi implement class.
- Regression: full suite 148 passed, 1 skipped (test_client_connect — mock WSS không chạy trên :8546, không liên quan).

### Completion Notes List

- Thêm `DequeRingBuffer` vào `core/ring_buffer.py` dùng `collections.deque(maxlen=capacity)` — auto-eviction O(1), không cần code eviction thủ công.
- `capacity` là `@property` trả `self._buf.maxlen`; `__init__` raise `ValueError` khi `capacity <= 0`.
- `read_latest(n)` trả `[]` khi `n <= 0`, trả toàn bộ khi `n >= len`.
- Tests cover đủ AC7/AC8: round-trip, eviction, FIFO order, read_latest (n<len, n==len, n>len, n=0), len sau mỗi write, isinstance Protocol, invalid capacity, default capacity=1000.
- ruff không cài local (CI chạy lint); code không có import thừa, theo convention project.

### File List

- `core/ring_buffer.py` (UPDATE — add DequeRingBuffer + import deque)
- `tests/unit/test_deque_ring_buffer.py` (NEW)

## Change Log

- 2026-07-09 — Implemented Story 1C.2 DequeRingBuffer; added 12 unit tests; status → review.
