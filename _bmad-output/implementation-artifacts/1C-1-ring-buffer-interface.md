---
baseline_commit: 0e04db6dc8c2c2891a2daae9d45d31b8e82023c3
type: build
---

# Story 1C.1: Ring Buffer Interface

Status: review

## Story

As a **Kỹ sư Dữ liệu**,
I want **`RingBufferProtocol` định nghĩa interface chuẩn cho ring buffer**,
so that **mọi implementation (deque, numpy) đều interchangeable, và downstream consumers (Epic 2 GraphBuilder, 1E.1 Pipeline) không phụ thuộc vào implementation cụ thể**.

## Acceptance Criteria

1. **AC1 — Package tồn tại:** `core/__init__.py` và `core/ring_buffer.py` tồn tại.

2. **AC2 — Protocol defined:** `RingBufferProtocol` là `typing.Protocol` export từ `core/ring_buffer.py` với methods:
   - `write(event: dict) -> None` — O(1) insert, evict oldest khi đầy
   - `read_all() -> list[dict]` — trả về tất cả events theo thứ tự FIFO (oldest first)
   - `read_latest(n: int) -> list[dict]` — trả về n events gần nhất
   - `__len__() -> int` — số events hiện tại
   - `capacity` property → `int` — max events

3. **AC3 — Protocol is structural (duck-typing):** Không cần `class Foo(RingBufferProtocol)` explicit inheritance — chỉ cần implement các methods là đủ.

4. **AC4 — Unit tests:** `tests/unit/test_ring_buffer_interface.py` verify:
   - `isinstance(DequeRingBuffer(10), RingBufferProtocol)` → True (sau khi 1C.2 done)
   - Protocol methods có signature đúng
   - `runtime_checkable` decorator cho phép isinstance check

## Tasks / Subtasks

- [x] **Task 1 — Tạo core package** (AC1)
  - [x] `core/__init__.py` (đã tồn tại từ trước — Track 0/schemas)
  - [x] Tạo `core/ring_buffer.py`

- [x] **Task 2 — Define RingBufferProtocol** (AC2, AC3)
  - [x] Import `typing.Protocol, runtime_checkable`
  - [x] Define `@runtime_checkable class RingBufferProtocol(Protocol)`
  - [x] Implement all 5 members (capacity property + write/read_all/read_latest/__len__, body = `...`)

- [x] **Task 3 — Unit tests** (AC4)
  - [x] Tạo `tests/unit/test_ring_buffer_interface.py`
  - [x] Verify runtime_checkable, duck-typing isinstance (conforming + non-conforming), protocol members, và signatures

## Dev Notes

**Loại story:** `[BUILD]` — không có blocker. Độc lập hoàn toàn.

---

### Implementation Pattern

```python
# core/ring_buffer.py
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RingBufferProtocol(Protocol):
    """Interface cho ring buffer lưu TickDataEvent dicts.

    Implementations:
    - DequeRingBuffer  (1C.2): dùng collections.deque — đơn giản, GIL-protected
    - NumpyRingBuffer  (1C.3): dùng numpy pre-allocated array — O(1) circular write
    - AsyncRingBuffer  (1C.4): asyncio.Lock wrapper cho any implementation
    """

    @property
    def capacity(self) -> int:
        """Maximum number of events the buffer can hold."""
        ...

    def write(self, event: dict) -> None:
        """Insert event. If buffer is full, silently evict oldest event."""
        ...

    def read_all(self) -> list[dict]:
        """Return all events in FIFO order (oldest first, newest last)."""
        ...

    def read_latest(self, n: int) -> list[dict]:
        """Return the n most recent events (newest last).

        If n > len(self), return all events.
        """
        ...

    def __len__(self) -> int:
        """Current number of events in the buffer."""
        ...
```

---

### Design Decisions

**Why individual events, not blocks?**
- `write(event: dict)` gives O(1) insertion with deque
- Downstream (Epic 2 GraphBuilder) receives `read_all()` output and groups by `block_number` field
- Simpler interface — ring buffer does NOT need to know about block semantics
- NFR4 "10 most recent blocks" is enforced at the pipeline level (1E.1) by setting `capacity` appropriately (e.g., 10 blocks × ~100 events/block = 1000 capacity)

**Why `@runtime_checkable`?**
- Allows `isinstance(obj, RingBufferProtocol)` for validation
- Without it, Protocol only works for static type checking (mypy/pyright)

**Event format:** Each `event` dict must conform to `tick_data.schema.json` (TickDataEvent.to_dict() output from Track 1B).

---

### NFR Requirements Relevant to This Story

- **NFR1 (latency <50ms):** Ring buffer write must be O(1) — implementation constraint enforced via test
- **NFR4:** "10 most recent blocks in RAM via collections.deque or static numpy array; no disk write"
  - `capacity` default = 1000 events (covers ~10 blocks at ~100 events/block)
  - Implementations MUST NOT write to disk

---

### File Structure

```
core/
  __init__.py    ← NEW (empty)
  ring_buffer.py ← NEW (RingBufferProtocol + future classes)
tests/
  unit/
    test_ring_buffer_interface.py ← NEW
```

---

### Project Conventions

- Python 3.12, pytest (sync tests, no asyncio here)
- `ruff check` cho linting
- `from core.ring_buffer import RingBufferProtocol`

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (BMad dev-story workflow)

### Debug Log References

- Ring buffer tests: `pytest tests/unit/test_ring_buffer_interface.py` → 6 passed
- Full suite: `pytest` → 136 passed, 1 skipped (external :8546 connect test), 0 regressions

### Completion Notes List

- **`core/__init__.py` already existed** (from the Track 0 schemas package); AC1 only required creating
  `core/ring_buffer.py`. Both files now present.
- **Protocol shape:** `@runtime_checkable class RingBufferProtocol(Protocol)` with a read-only
  `capacity` property plus `write`, `read_all`, `read_latest`, `__len__` (all bodies `...`). Pure
  interface — no implementation logic (that arrives in 1C.2/1C.3/1C.4).
- **AC4 adaptation:** the spec's `isinstance(DequeRingBuffer(10), RingBufferProtocol)` check depends on
  1C.2 (not yet built). Substituted an equivalent structural test using a local `_ConformingBuffer`
  (duck-typing, no explicit inheritance → proves AC3) and a `_MissingMethods` negative case. Also
  asserted `_is_runtime_protocol`, the `__protocol_attrs__` membership, and each member signature.
- **runtime_checkable caveat (documented for 1C.2+):** `isinstance` against a runtime_checkable Protocol
  only checks attribute *presence*, not signatures/types — real conformance of concrete buffers is still
  the job of their own unit tests.

### File List

- `core/ring_buffer.py` (NEW)
- `tests/unit/test_ring_buffer_interface.py` (NEW)
- `core/__init__.py` (pre-existing, unchanged)

## Change Log

- 2026-07-09: Defined `RingBufferProtocol` (runtime_checkable structural interface) in
  `core/ring_buffer.py` with unit tests. Story 1C.1 → review.
