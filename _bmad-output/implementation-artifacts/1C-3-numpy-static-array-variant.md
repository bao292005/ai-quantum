---
baseline_commit: 0e04db6dc8c2c2891a2daae9d45d31b8e82023c3
type: build
---

# Story 1C.3: NumPy Static Array Ring Buffer

Status: done

## Story

As a **Kỹ sư Dữ liệu**,
I want **`NumpyRingBuffer(capacity=1000)` implement `RingBufferProtocol` dùng pre-allocated numpy object array với circular write head**,
so that **có alternative implementation O(1) write với bộ nhớ cố định từ đầu (no GC pressure), sẵn sàng cho benchmark so sánh với DequeRingBuffer**.

## Acceptance Criteria

1. **AC1 — Class tồn tại:** `core/ring_buffer.py` export `NumpyRingBuffer`.

2. **AC2 — Implements Protocol:** `isinstance(NumpyRingBuffer(10), RingBufferProtocol)` → `True`.

3. **AC3 — Pre-allocated array:** Constructor allocates `np.empty(capacity, dtype=object)` — fixed memory từ đầu, không reallocate.

4. **AC4 — O(1) write với circular index:** `write()` dùng `self._buf[self._head % self._capacity] = event; self._head += 1`. Không dùng Python list append.

5. **AC5 — Correct eviction:** Sau khi write `capacity + k` events, buffer chứa đúng k events mới nhất và `len == capacity`.

6. **AC6 — read_all() FIFO:** Trả về events theo thứ tự oldest-first, giống DequeRingBuffer.

7. **AC7 — Behavioral equivalence:** Với cùng sequence of writes, `NumpyRingBuffer` và `DequeRingBuffer` trả về identically ordered results.

8. **AC8 — Unit tests:** `tests/unit/test_numpy_ring_buffer.py` cover:
   - isinstance check với Protocol
   - write/eviction/read_all/read_latest (same cases như 1C.2)
   - Pre-allocation: kiểm tra `buf._buf.shape == (capacity,)`
   - Behavioral equivalence test vs DequeRingBuffer

## Tasks / Subtasks

- [x] **Task 1 — Implement NumpyRingBuffer** (AC1–AC6)
  - [x] Thêm `NumpyRingBuffer` vào `core/ring_buffer.py`
  - [x] `__init__`: allocate `np.empty(capacity, dtype=object)`, init `_head=0`, `_size=0`
  - [x] `write()`: circular write với `_head % capacity`, increment `_head`, update `_size`
  - [x] `read_all()`: reconstruct FIFO order từ circular buffer
  - [x] `read_latest(n)`: tail slice của FIFO output
  - [x] `__len__()`: return `self._size`

- [x] **Task 2 — Unit tests** (AC7, AC8)
  - [x] Tạo `tests/unit/test_numpy_ring_buffer.py`
  - [x] Behavioral equivalence test

### Review Findings

- [x] [Review][Patch] (chung với 1C.2) Đã thêm ghi chú contract immutability vào docstring `NumpyRingBuffer`. [core/ring_buffer.py]
- [x] [Review][Defer] `NumpyRingBuffer._head` tăng không giới hạn — xác nhận KHÔNG phải lỗi (Python int arbitrary-precision, `% capacity` luôn đúng). Không cần fix. [core/ring_buffer.py NumpyRingBuffer.write] — dismissed as non-issue.

## Dev Notes

**Loại story:** `[BUILD]` — blockedBy: 1C.1 (Protocol), 1C.2 (test patterns to copy).

**numpy là dependency mới:** Kiểm tra `pyproject.toml` — nếu numpy chưa có, thêm `"numpy>=1.24"`. Likely already present since PyTorch requires numpy.

```bash
python -c "import numpy; print(numpy.__version__)"
```

---

### Implementation Pattern

```python
# Thêm vào core/ring_buffer.py
import numpy as np


class NumpyRingBuffer:
    """Ring buffer backed by a pre-allocated numpy object array.

    Uses a circular write head — O(1) write, fixed memory allocation.
    Behavioral equivalent to DequeRingBuffer; useful for benchmarking.
    """

    def __init__(self, capacity: int = 1000) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0, got {capacity}")
        self._capacity = capacity
        self._buf: np.ndarray = np.empty(capacity, dtype=object)
        self._head: int = 0   # next write position (absolute, wraps modulo capacity)
        self._size: int = 0   # current number of valid events

    @property
    def capacity(self) -> int:
        return self._capacity

    def write(self, event: dict) -> None:
        """O(1) circular write. Overwrites oldest slot when full."""
        slot = self._head % self._capacity
        self._buf[slot] = event
        self._head += 1
        if self._size < self._capacity:
            self._size += 1

    def read_all(self) -> list[dict]:
        """Return all events in FIFO order (oldest first)."""
        if self._size == 0:
            return []
        if self._size < self._capacity:
            # Buffer not yet full — slots 0.._size-1 are in order
            return list(self._buf[:self._size])
        # Buffer is full — oldest slot is _head % capacity
        start = self._head % self._capacity
        # Reconstruct: start..end (wrap around)
        indices = [(start + i) % self._capacity for i in range(self._capacity)]
        return [self._buf[i] for i in indices]

    def read_latest(self, n: int) -> list[dict]:
        """Return the n most recent events (newest last)."""
        if n <= 0:
            return []
        all_events = self.read_all()
        return all_events[-n:] if n < len(all_events) else all_events

    def __len__(self) -> int:
        return self._size
```

---

### read_all() Logic Explained

```
Example: capacity=5, wrote events [A, B, C, D, E, F, G]

After 7 writes:
  _head = 7,  _size = 5 (full)
  _buf  = [F, G, C, D, E]   (slots: 0=F, 1=G, 2=C, 3=D, 4=E)
  oldest slot = _head % capacity = 7 % 5 = 2  → C

  FIFO order = [C, D, E, F, G]
  indices = [2, 3, 4, 0, 1]
```

---

### Behavioral Equivalence Test

```python
# tests/unit/test_numpy_ring_buffer.py (include this test)
from core.ring_buffer import DequeRingBuffer, NumpyRingBuffer

def test_behavioral_equivalence():
    """NumpyRingBuffer must produce same results as DequeRingBuffer."""
    capacity = 7
    deque_buf = DequeRingBuffer(capacity)
    numpy_buf = NumpyRingBuffer(capacity)

    # Write more than capacity to test eviction
    events = [{"block_number": i, "log_index": i} for i in range(capacity + 5)]
    for e in events:
        deque_buf.write(e)
        numpy_buf.write(e)

    assert deque_buf.read_all() == numpy_buf.read_all()
    assert deque_buf.read_latest(3) == numpy_buf.read_latest(3)
    assert len(deque_buf) == len(numpy_buf)
```

---

### Performance Notes

| | DequeRingBuffer | NumpyRingBuffer |
|---|---|---|
| Memory alloc | Dynamic (GC-managed) | Fixed at init |
| write() | O(1) deque append | O(1) array index |
| read_all() | O(n) list(deque) | O(n) index reconstruction |
| GC pressure | Higher (dicts managed by deque) | Lower (pre-allocated slots) |
| Recommended for | Simplicity, default | Memory-constrained, benchmark |

For real-time pipeline at current scale (100 events/sec), **both are equivalent**. NumpyRingBuffer becomes advantageous at 10k+ events/sec where GC pauses matter.

---

### Project Conventions

- Python 3.12, pytest (sync tests)
- `numpy>=1.24` required (check pyproject.toml)
- `from core.ring_buffer import NumpyRingBuffer, RingBufferProtocol`

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- numpy 1.26.3 đã cài local; thêm `numpy>=1.24` vào `pyproject.toml` dependencies (trước đó thiếu khai báo).
- RED: `pytest tests/unit/test_numpy_ring_buffer.py` → ImportError (NumpyRingBuffer chưa tồn tại).
- GREEN: 16 passed sau khi implement class.
- Regression: full suite 164 passed, 1 skipped (test_client_connect — mock WSS không chạy trên :8546, không liên quan).

### Completion Notes List

- Thêm `NumpyRingBuffer` vào `core/ring_buffer.py`: pre-allocated `np.empty(capacity, dtype=object)`, circular write head (`_head % capacity`), `_size` track số event hợp lệ. Không dùng list append.
- `read_all()` xử lý 2 nhánh: chưa đầy (slots `0.._size-1` đã đúng thứ tự) và đã đầy (walk từ `_head % capacity` wrap-around) → FIFO oldest-first.
- `read_latest(n)`: `[]` khi n<=0, tail slice của FIFO, trả toàn bộ khi n>=len.
- Behavioral equivalence test xác nhận output identical với `DequeRingBuffer` cho cùng chuỗi write (kể cả wrap-around).
- ruff không cài local (CI chạy lint); import `numpy as np` được dùng, không có import thừa.

### File List

- `core/ring_buffer.py` (UPDATE — add NumpyRingBuffer + import numpy)
- `tests/unit/test_numpy_ring_buffer.py` (NEW)
- `pyproject.toml` (UPDATE — add numpy>=1.24)

## Change Log

- 2026-07-09 — Implemented Story 1C.3 NumpyRingBuffer; added 16 unit tests (incl. behavioral equivalence vs Deque); declared numpy dependency; status → review.
