---
baseline_commit: 0e04db60825409ad60bf9c50f73db6977cb733f6
type: build
---

# Story 1D.3: Backtest Replay Driver

Status: done

## Story

As a **Calibration Engineer**,
I want **a `ReplayDriver(buffer, rate="1x"|"100x"|"asap")` that pumps fixture CSV events into a ring buffer paced by their real inter-event timestamp gaps**,
so that **Epic 4 calibration/backtest (LUNA/FTX Fragility replay) exercises the MPS pipeline on a faithful timeline — same ring-buffer interface as the realtime path**.

## Acceptance Criteria

1. **AC1 — Class tồn tại:** `ingestion/csv_loader.py` (hoặc `ingestion/replay.py`) export `ReplayDriver`.

2. **AC2 — Rate parsing:** `rate` nhận `"1x"`, `"100x"`, `"asap"` hoặc số (float). `"asap"` = không delay; `"<N>x"`/số N = tua nhanh N lần (delay = gap/N). Rate không hợp lệ → `ValueError`.

3. **AC3 — Bơm vào ring buffer đúng thứ tự:** `async def run(path)` đọc event qua `stream_csv` (Story 1D.2, đã theo thứ tự block) và gọi `buffer.write(event)` cho từng event, giữ nguyên thứ tự.

4. **AC4 — Pacing theo timestamp:** Giữa event `i-1` và `i`, driver `await asyncio.sleep(gap_seconds / speed)` với `gap_seconds = (ts_i − ts_{i-1})` (parse từ `block_timestamp`). Event cùng block (gap = 0) → không sleep. `asap` → không sleep.

5. **AC5 — Tỉ lệ timestamp chính xác:** Tỉ lệ delay giữa các cặp event đúng bằng `gap/speed` (kiểm định bằng test capture `asyncio.sleep`). "CSV 24h @ 100x" ⇒ tổng wall-clock ≈ 24h/100 = 14.4 phút ≤ 15 phút.

6. **AC6 — Reuse tầng dưới:** Dùng `stream_csv` (1D.2) làm nguồn và một ring buffer từ Track 1C (`DequeRingBuffer`, đã DONE) làm đích. KHÔNG viết lại parse/validate/gzip/ordering.

7. **AC7 — Đếm & trả về:** `run()` trả về số event đã replay (int) để caller assert.

8. **AC8 — Unit tests:** `tests/unit/test_replay_driver.py` cover:
   - Rate parsing: `1x`→1.0, `100x`→100.0, `asap`→∞/no-sleep, số hợp lệ, rate sai → `ValueError`
   - `asap`: mọi event ghi vào `DequeRingBuffer` đúng thứ tự, 0 lần sleep
   - Pacing: monkeypatch `asyncio.sleep` thu delays; event có gap timestamp biết trước → delay == gap/speed
   - Event cùng block (gap=0) → không sleep
   - Integration: replay CSV nhỏ vào `DequeRingBuffer`, `read_all()` khớp thứ tự & số lượng

## Tasks / Subtasks

- [x] **Task 1 — Rate parser** (AC2)
  - [x] `_parse_rate(rate: str | float) -> float` — `"asap"`→`math.inf`, `"<N>x"`/số→`float(N)`, sai→`ValueError`

- [x] **Task 2 — Implement ReplayDriver** (AC1, AC3–AC7)
  - [x] `__init__(self, buffer, *, rate="1x")` — lưu buffer + speed đã parse
  - [x] `async def run(self, path) -> int` — `async for event in stream_csv(path)`, pace theo timestamp gap, `buffer.write(event)`, đếm
  - [x] Parse timestamp bằng `datetime.fromisoformat` (Python 3.11+ hỗ trợ hậu tố `Z`)

- [x] **Task 3 — Unit tests** (AC8)
  - [x] Tạo `tests/unit/test_replay_driver.py`
  - [x] Monkeypatch `asyncio.sleep` để test pacing tất định (không sleep thật)

## Dev Notes

**Loại story:** `[BUILD]` — Track 1D (Historical CSV Ingestion), story 3/3 (cuối track).
**blockedBy:** **Story 1D.2** (`stream_csv`) + **Story 1C.2** (`DequeRingBuffer` — đã DONE). KHÔNG phụ thuộc Track 1A/1B.

---

### 🔗 Previous Story Intelligence — 1D.1 & 1D.2 (bắt buộc đọc)

- **1D.1** → `ingestion/csv_loader.py`: `map_csv_row`, `iter_csv_events`, `CsvRowError`. Output là **`dict`** khớp `tick_data.schema.json` (11 field). `amount0/amount1` là `str`; chỉ `block_number`/`log_index` là `int`; `protocol` enum có `aave_v2`.
- **1D.2** → cùng file: `async def stream_csv(path, *, error_log, validate) -> AsyncIterator[dict]` — yield theo thứ tự block (đã verify pre-sorted), lazy O(1) memory, cooperative `await asyncio.sleep(0)`. **1D.3 dùng trực tiếp hàm này làm nguồn.**
- **Track 1C** → `core/ring_buffer.py`: `DequeRingBuffer(capacity=1000)` (DONE) với `write(event: dict)` sync O(1), auto-evict. `RingBufferProtocol` là contract. `AsyncRingBuffer` (async write) cũng có nhưng **1D.3 dùng buffer SYNC** (xem quyết định dưới).

---

### ⚠️ Quyết định thiết kế — nhận buffer SYNC, pacing bằng asyncio

- **Đích ghi:** nhận một `RingBufferProtocol` **sync** (mặc định `DequeRingBuffer`). `buffer.write()` là O(1) sync, gọi thẳng trong vòng lặp async giữa các `await sleep`. KHÔNG dùng `AsyncRingBuffer` ở 1D.3 — tránh phụ thuộc lock async không cần thiết cho backtest single-consumer; việc chia sẻ buffer đa-coroutine (realtime) là trách nhiệm của **1E.1 orchestrator**.
- **Nguồn thời gian:** `block_timestamp` (ISO 8601 `...Z`). Parse `datetime.fromisoformat` → tz-aware. Gap = hiệu hai timestamp (giây, float). Event cùng block ⇒ gap 0 ⇒ không sleep.
- **`asap` (speed=∞):** bỏ qua toàn bộ sleep → replay nhanh nhất (đây là mode dùng trong hầu hết test tự động; mock WSS 0.5 cũng dùng `--speed asap`).
- **KHÔNG dùng wall-clock thật trong test.** Test pacing bằng cách **monkeypatch `asyncio.sleep`** để thu các delay được yêu cầu và assert `delay == gap/speed`. Điều này giữ test tất định & nhanh (không chờ thật).

**Scope 1D.3:** rate parse + pacing + write vào buffer. KHÔNG: sort (1D.2 lo), KHÔNG: chạy MPS engine (Epic 2/3), KHÔNG: orchestrate realtime (1E.1).

**Lưu ý AC5 "24h @ 100x ≤ 15 phút":** đây là hệ quả toán học của pacing (24h/100 = 14.4 phút), KHÔNG phải yêu cầu benchmark chạy thật. Fixture luna thực tế trải ~61h (2022-05-06 → 05-09) ⇒ @100x ≈ 36 phút — driver vẫn đúng vì tiêu chí là **tỉ lệ** gap chính xác, không phải con số tuyệt đối 15 phút.

---

### Implementation Pattern

```python
# Thêm vào ingestion/csv_loader.py (hoặc tạo ingestion/replay.py và import stream_csv)
from __future__ import annotations

import asyncio
import math
from datetime import datetime

from core.ring_buffer import RingBufferProtocol


def _parse_rate(rate: str | float) -> float:
    """Return replay speed factor. 'asap' -> inf; '100x'/'1x'/number -> float."""
    if isinstance(rate, (int, float)):
        speed = float(rate)
    elif isinstance(rate, str):
        r = rate.strip().lower()
        if r == "asap":
            return math.inf
        r = r[:-1] if r.endswith("x") else r
        try:
            speed = float(r)
        except ValueError as e:
            raise ValueError(f"invalid rate: {rate!r}") from e
    else:
        raise ValueError(f"invalid rate type: {type(rate).__name__}")
    if speed <= 0:
        raise ValueError(f"rate must be > 0, got {rate!r}")
    return speed


class ReplayDriver:
    """Replay a fixture CSV into a ring buffer paced by event timestamps."""

    def __init__(self, buffer: RingBufferProtocol, *, rate: str | float = "1x") -> None:
        self._buffer = buffer
        self._speed = _parse_rate(rate)

    async def run(self, path, *, error_log="csv_errors.log") -> int:
        """Stream `path` into the buffer with timestamp pacing. Returns count."""
        prev_ts: datetime | None = None
        count = 0
        async for event in stream_csv(path, error_log=error_log):
            ts = datetime.fromisoformat(event["block_timestamp"])
            if prev_ts is not None and not math.isinf(self._speed):
                gap = (ts - prev_ts).total_seconds()
                delay = gap / self._speed
                if delay > 0:
                    await asyncio.sleep(delay)
            prev_ts = ts
            self._buffer.write(event)
            count += 1
        return count
```

---

### Test Pattern

```python
# tests/unit/test_replay_driver.py
import asyncio

import pytest

from core.ring_buffer import DequeRingBuffer
from ingestion.csv_loader import ReplayDriver, _parse_rate

_HEADER = ("block_number,block_timestamp,protocol,event_type,pool_address,"
           "token0,token1,amount0,amount1,tx_hash,log_index")


def _row(block: int, ts: str, log_index: int = 0) -> str:
    return (f"{block},{ts},uniswap_v3,swap,"
            "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640,"
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48,"
            "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2,"
            "-13739080501,5130000000000000000,"
            "0xa343dacfff741a8773aa3b85b865c3ff98ed0b2b69d52e3aecd77a9877182d45,"
            f"{log_index}")


def test_parse_rate():
    assert _parse_rate("1x") == 1.0
    assert _parse_rate("100x") == 100.0
    assert _parse_rate(50) == 50.0
    import math
    assert math.isinf(_parse_rate("asap"))
    for bad in ("fast", "0x", "-5x", ""):
        with pytest.raises(ValueError):
            _parse_rate(bad)


async def test_asap_no_sleep(tmp_path, monkeypatch):
    sleeps = []
    async def fake_sleep(d): sleeps.append(d)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    p = tmp_path / "s.csv"
    p.write_text(_HEADER + "\n"
                 + _row(1, "2022-05-06T14:15:06Z") + "\n"
                 + _row(2, "2022-05-06T14:15:16Z") + "\n")
    buf = DequeRingBuffer(100)
    n = await ReplayDriver(buf, rate="asap").run(p, error_log=tmp_path / "e.log")
    assert n == 2
    assert [e["block_number"] for e in buf.read_all()] == [1, 2]
    assert sleeps == []  # asap: no real sleeps requested by driver


async def test_pacing_ratio(tmp_path, monkeypatch):
    sleeps = []
    async def fake_sleep(d): sleeps.append(d)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    p = tmp_path / "s.csv"
    p.write_text(_HEADER + "\n"
                 + _row(1, "2022-05-06T14:15:00Z") + "\n"   # t0
                 + _row(2, "2022-05-06T14:15:10Z") + "\n"   # +10s
                 + _row(2, "2022-05-06T14:15:10Z", 1) + "\n"  # same block, +0s
                 + _row(3, "2022-05-06T14:15:40Z") + "\n")  # +30s
    buf = DequeRingBuffer(100)
    await ReplayDriver(buf, rate="10x").run(p, error_log=tmp_path / "e.log")
    # positive delays only: 10s/10=1.0, (0s skipped), 30s/10=3.0
    assert [d for d in sleeps if d > 0] == [1.0, 3.0]


async def test_integration_deque(tmp_path):
    p = tmp_path / "s.csv"
    rows = "\n".join(_row(b, f"2022-05-06T14:15:{b:02d}Z") for b in (1, 2, 3))
    p.write_text(_HEADER + "\n" + rows + "\n")
    buf = DequeRingBuffer(100)
    n = await ReplayDriver(buf, rate="asap").run(p, error_log=tmp_path / "e.log")
    assert n == 3
    assert [e["block_number"] for e in buf.read_all()] == [1, 2, 3]
```

> `asyncio_mode=auto` → `async def test_*` chạy tự động. Monkeypatch `asyncio.sleep` giữ test nhanh & tất định (không chờ wall-clock thật).

---

### File Structure After 1D.3

```
ingestion/
  csv_loader.py       ← UPDATE (1D.3): thêm ReplayDriver + _parse_rate
                         (1D.1: map_csv_row/iter_csv_events; 1D.2: stream_csv)
core/
  ring_buffer.py      ← EXISTING (1C, DONE) — DequeRingBuffer làm đích
tests/unit/
  test_replay_driver.py ← NEW (1D.3)
```

> Nếu file `csv_loader.py` trở nên quá lớn, được phép tách `ReplayDriver` sang `ingestion/replay.py` và `from ingestion.csv_loader import stream_csv`. Giữ nhất quán import; cập nhật File List cho đúng.

### Track 1D roadmap — hoàn tất sau story này

- 1D.1 (ready-for-dev): row → dict + validate + error log.
- 1D.2 (ready-for-dev): async `stream_csv` theo thứ tự, memory bounded.
- **1D.3 (story này):** `ReplayDriver` pacing timestamp → bơm ring buffer. **Đóng Track 1D.**
- Downstream: **1E.1 Pipeline Orchestrator** nối realtime (1A→1B→1C) và có thể dùng `ReplayDriver` cho chế độ backtest.

---

### Project Conventions & Testing

- Python 3.11+ (local anaconda 3.12); pytest, `asyncio_mode=auto` — test là `async def`.
- Chạy test: `python3 -m pytest tests/unit/test_replay_driver.py`. Console output bị hook lọc → redirect ra file và Read nếu cần full traceback.
- `datetime.fromisoformat` hỗ trợ hậu tố `Z` từ Python 3.11 (đã verify trên 3.12.4 local) → không cần thư viện parse ngoài.
- Lint `ruff check` chạy trên CI (không cài local); tránh import thừa. `math`, `asyncio`, `datetime` đều dùng.
- Logging JSON qua stdout theo convention.

### References

- [Source: `_bmad-output/epics.md`#Story-1D.3-Backtest-Replay-Driver] — user story + AC gốc (rate 1x/100x/asap, pacing timestamp, 24h@100x ≤15 phút).
- [Source: `_bmad-output/implementation-artifacts/1D-2-csv-streamer.md`] — `stream_csv` async source để reuse.
- [Source: `_bmad-output/implementation-artifacts/1D-1-csv-schema-mapping.md`] — dict schema, guardrails (amount là str).
- [Source: `core/ring_buffer.py`] — `DequeRingBuffer.write(event: dict)` sync O(1), `RingBufferProtocol` contract.
- [Source: `fixtures/backtest/README.md`] — luna span ~61h, timestamp ranges (căn cứ note AC5 tuyệt đối vs tỉ lệ).
- [Source: `tools/mock_wss`] — tiền lệ `--speed asap|1x|100x` (thuật ngữ rate nhất quán toàn dự án).
- [Source: ARCHITECTURE-SPINE.md#AD-2] — ring buffer in-memory (deque) là đích lưu trữ backtest.

---

### Review Findings

- [x] [Review][Patch] `_parse_rate` reject non-finite (`math.isfinite`) → `"inf"`/`"nan"`/`"-inf"` raise ValueError. Test bổ sung trong `test_replay_driver.py::test_parse_rate`. [ingestion/csv_loader.py]

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- RED: `pytest tests/unit/test_replay_driver.py` → ImportError (ReplayDriver chưa có).
- GREEN (sau 1 fix test): `test_asap_no_sleep` ban đầu fail vì bắt được `sleep(0)` cooperative-yield của `stream_csv` (không phải pacing) → sửa assertion thành "không có delay > 0". 4 passed.
- Regression: full suite 194 passed, 1 skipped (test_client_connect — không liên quan).

### Completion Notes List

- `_parse_rate`: `"asap"`→`inf`, `"<N>x"`/số→float, reject `bool`/≤0/chuỗi sai → `ValueError`.
- `ReplayDriver(buffer, *, rate="1x").run(path)`: `async for` qua `stream_csv` (1D.2), pace `sleep(gap/speed)` giữa event, `buffer.write(event)`, trả count. `asap`/gap-0 → no sleep.
- Nhận buffer SYNC (`DequeRingBuffer`), không dùng `AsyncRingBuffer` (chia sẻ đa-coroutine để 1E.1 lo).
- Timestamp parse `datetime.fromisoformat` (hỗ trợ `Z` từ 3.11; verified 3.12.4).
- Test pacing tất định bằng monkeypatch `asyncio.sleep` (không chờ wall-clock).
- ruff không cài local; import `math`, `datetime`, `asyncio` đều dùng.

### File List

- `ingestion/csv_loader.py` (UPDATE — add ReplayDriver + _parse_rate)
- `tests/unit/test_replay_driver.py` (NEW)

## Change Log

- 2026-07-09 — Implemented Story 1D.3 ReplayDriver (timestamp-paced CSV→ring buffer); 4 tests; status → review. Closes Track 1D.
