---
baseline_commit: 0e04db60825409ad60bf9c50f73db6977cb733f6
type: build
---

# Story 1D.2: CSV Streamer

Status: done

## Story

As a **Data Analyst**,
I want **an async generator `stream_csv(path)` that yields normalized tick-data dicts from a fixture CSV(.gz) in timestamp (block) order with a bounded memory footprint**,
so that **Epic 4 backtest replay (and Story 1D.3 ReplayDriver) can consume historical events through the same async interface as the realtime WebSocket stream (`ingestion/streams.py::stream_new_heads`)**.

## Acceptance Criteria

1. **AC1 — Async generator tồn tại:** `ingestion/csv_loader.py` export `async def stream_csv(path, *, error_log=..., validate=True) -> AsyncIterator[dict]`.

2. **AC2 — Yield theo thứ tự thời gian:** Event được yield theo `block_number` không giảm dần (⇒ `block_timestamp` không giảm). Fixtures Epic 0 đã pre-sorted theo block ascending (đã xác minh: luna/ftx/normal đều 0 out-of-order) → streamer **giữ nguyên thứ tự file (lazy), KHÔNG sort in-memory**.

3. **AC3 — Order guard:** Nếu gặp row có `block_number` < block trước đó (input không sorted ngoài dự kiến), ghi log WARN JSON (`event="csv_out_of_order"`) nhưng **vẫn yield** (không drop, không raise) — streamer không tự ý buffer-sort để giữ memory bounded.

4. **AC4 — Memory footprint < 50MB:** Stream toàn bộ `luna_2022_05_09.csv.gz` (26,540 row) với peak allocation < 50MB (đo bằng `tracemalloc`). Lazy per-row, KHÔNG load cả file vào list/sort.

5. **AC5 — Reuse 1D.1 mapping:** Dùng lại `iter_csv_events` (Story 1D.1) cho parse + validate + error-logging. KHÔNG viết lại logic map/validate; KHÔNG viết lại gzip-open.

6. **AC6 — Async-friendly:** Generator định kỳ nhường control cho event loop (`await asyncio.sleep(0)`) để không chặn loop khi replay file lớn.

7. **AC7 — Unit tests:** `tests/unit/test_csv_streamer.py` cover:
   - `async for` yield đúng số event từ một CSV nhỏ, đúng thứ tự block tăng dần
   - Bad row (từ 1D.1) được skip + ghi error log, stream tiếp (không raise)
   - Đọc `.csv.gz` trong suốt
   - Out-of-order input → log WARN, vẫn yield đủ event
   - Memory: stream full luna fixture, `tracemalloc` peak < 50MB

## Tasks / Subtasks

- [x] **Task 1 — Implement `stream_csv`** (AC1–AC3, AC5, AC6)
  - [x] Thêm `async def stream_csv(...)` vào `ingestion/csv_loader.py`
  - [x] Iterate `iter_csv_events(path, error_log=..., validate=...)` (sync generator từ 1D.1)
  - [x] Track `prev_block`; nếu `event["block_number"] < prev_block` → log WARN, vẫn yield
  - [x] `await asyncio.sleep(0)` mỗi ~1000 event để nhường loop

- [x] **Task 2 — Unit tests** (AC4, AC7)
  - [x] Tạo `tests/unit/test_csv_streamer.py`
  - [x] Test memory bằng `tracemalloc` trên fixture luna thật (path: `fixtures/backtest/luna_2022_05_09.csv.gz`)

## Dev Notes

**Loại story:** `[BUILD]` — Track 1D (Historical CSV Ingestion), story 2/3.
**blockedBy:** **Story 1D.1** (`iter_csv_events`, `map_csv_row`, `CsvRowError` trong `ingestion/csv_loader.py`). KHÔNG phụ thuộc Track 1B/1A.

---

### 🔗 Previous Story Intelligence — 1D.1 (bắt buộc đọc)

Story 1D.1 đã tạo `ingestion/csv_loader.py` với:
- `map_csv_row(raw: dict[str,str], *, validate=True) -> dict` — CSV row → dict khớp `tick_data.schema.json`.
- `iter_csv_events(path, *, error_log="csv_errors.log", validate=True) -> Iterator[dict]` — **sync generator**: mở `.csv`/`.csv.gz` trong suốt (gzip), `csv.DictReader` (file CÓ header), map từng row, row lỗi → ghi 1 dòng JSON vào `error_log` rồi skip (không raise).
- `CsvRowError(ValueError)` — lỗi map/validate của 1 row.
- **Output là `dict`** (11 field schema), KHÔNG phải `TickDataEvent` (class đó thuộc Track 1B chưa build). Ring buffer (`core/ring_buffer.py`) consume `dict`.

→ 1D.2 chỉ là **lớp async + đảm bảo thứ tự** mỏng bọc quanh `iter_csv_events`. KHÔNG lặp lại parse/validate/gzip.

**Guardrails kế thừa từ 1D.1 (đừng vi phạm):**
- `amount0`/`amount1` giữ `str` (không cast số).
- Chỉ `block_number`, `log_index` là `int`.
- `protocol` enum có `aave_v2`.

---

### ⚠️ Quyết định thiết kế — lazy streaming, KHÔNG sort in-memory

AC gốc: "yield theo thứ tự timestamp" + "memory < 50MB". Hai ràng buộc này giải quyết bằng nhận xét: **fixtures Epic 0 đã pre-sorted theo `block_number` ascending** (đã xác minh bằng script: luna 26,540 / ftx 35,109 / normal 6,899 row — 0 out-of-order). `block_timestamp` là hàm của block ⇒ non-decreasing theo block.

→ Streamer **giữ nguyên thứ tự file, yield lazy từng row** (O(1) memory). KHÔNG đọc cả file vào list rồi `sorted()` — điều đó sẽ phá ràng buộc 50MB với file 35k row.

→ Để an toàn khi input bất ngờ không sorted: **verify** `block_number` non-decreasing, log WARN nếu vi phạm, nhưng **vẫn yield** (không drop, không buffer-sort). Việc sort/pacing đúng nhịp là trách nhiệm của **Story 1D.3 ReplayDriver**, không phải 1D.2.

**Scope 1D.2:** async iteration + order-verify. KHÔNG: pacing theo thời gian thực (1D.3), KHÔNG ghi vào ring buffer (1D.3), KHÔNG sort.

---

### Implementation Pattern

```python
# Thêm vào ingestion/csv_loader.py (dưới iter_csv_events)
import asyncio
from collections.abc import AsyncIterator

_YIELD_EVERY = 1000  # nhường event loop mỗi N event


async def stream_csv(
    path: str | Path,
    *,
    error_log: str | Path = "csv_errors.log",
    validate: bool = True,
) -> AsyncIterator[dict]:
    """Async-yield tick-data dicts from a fixture CSV(.gz) in block order.

    Thin async wrapper over the synchronous ``iter_csv_events`` (Story 1D.1).
    Assumes the fixture is pre-sorted by ``block_number`` (Epic 0 fixtures are);
    verifies non-decreasing order and logs a WARN on violation but never drops
    or buffers rows — memory stays O(1) per row.
    """
    prev_block = -1
    for i, event in enumerate(
        iter_csv_events(path, error_log=error_log, validate=validate)
    ):
        block = event["block_number"]
        if block < prev_block:
            logger.warning(json.dumps({
                "event": "csv_out_of_order",
                "block_number": block,
                "prev_block_number": prev_block,
            }))
        prev_block = block
        yield event
        if i % _YIELD_EVERY == 0:
            await asyncio.sleep(0)  # cooperative yield to the event loop
```

> Note: `iter_csv_events` là sync và đọc file per-row (buffered) — với PoC/backtest scale (10k–35k row) chi phí là chấp nhận được. Nếu sau này cần non-blocking I/O thực sự (offload sang thread), để lại cho 1E.1 orchestrator; KHÔNG over-engineer ở 1D.2.

---

### Test Pattern

```python
# tests/unit/test_csv_streamer.py
import gzip
import tracemalloc
from pathlib import Path

import pytest

from ingestion.csv_loader import stream_csv

_HEADER = ("block_number,block_timestamp,protocol,event_type,pool_address,"
           "token0,token1,amount0,amount1,tx_hash,log_index")


def _row(block: int, log_index: int = 0) -> str:
    return (f"{block},2022-05-06T14:15:06Z,uniswap_v3,swap,"
            "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640,"
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48,"
            "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2,"
            "-13739080501,5130000000000000000,"
            "0xa343dacfff741a8773aa3b85b865c3ff98ed0b2b69d52e3aecd77a9877182d45,"
            f"{log_index}")


async def test_stream_order_and_count(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text(_HEADER + "\n" + "\n".join(_row(b) for b in (1, 2, 3, 10)) + "\n")
    events = [e async for e in stream_csv(p, error_log=tmp_path / "e.log")]
    assert [e["block_number"] for e in events] == [1, 2, 3, 10]


async def test_stream_skips_bad_row(tmp_path):
    p = tmp_path / "s.csv"
    good = _row(1)
    bad = good.replace("1,", "notanumber,", 1)
    p.write_text(f"{_HEADER}\n{good}\n{bad}\n{_row(2)}\n")
    err = tmp_path / "e.log"
    events = [e async for e in stream_csv(p, error_log=err)]
    assert [e["block_number"] for e in events] == [1, 2]
    assert err.exists() and len(err.read_text().strip().splitlines()) == 1


async def test_stream_gzip(tmp_path):
    gz = tmp_path / "s.csv.gz"
    with gzip.open(gz, "wt", encoding="utf-8") as f:
        f.write(_HEADER + "\n" + _row(5) + "\n")
    events = [e async for e in stream_csv(gz, error_log=tmp_path / "e.log")]
    assert len(events) == 1 and events[0]["block_number"] == 5


async def test_stream_out_of_order_still_yields(tmp_path, caplog):
    p = tmp_path / "s.csv"
    p.write_text(_HEADER + "\n" + "\n".join(_row(b) for b in (5, 3)) + "\n")
    events = [e async for e in stream_csv(p, error_log=tmp_path / "e.log")]
    assert [e["block_number"] for e in events] == [5, 3]  # not dropped


async def test_stream_memory_under_50mb():
    fixture = Path("fixtures/backtest/luna_2022_05_09.csv.gz")
    tracemalloc.start()
    count = 0
    async for _ in stream_csv(fixture, error_log="/tmp/csv_errors_test.log"):
        count += 1
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert count == 26540
    assert peak < 50 * 1024 * 1024  # < 50 MB
```

> `asyncio_mode=auto` trong `pyproject.toml` → `async def test_*` chạy tự động, không cần `@pytest.mark.asyncio`.

---

### File Structure After 1D.2

```
ingestion/
  csv_loader.py       ← UPDATE (1D.2): thêm async stream_csv + import asyncio
                         (1D.1 đã có map_csv_row, iter_csv_events, CsvRowError)
tests/unit/
  test_csv_loader.py  ← EXISTING (1D.1)
  test_csv_streamer.py ← NEW (1D.2)
```

### Track 1D roadmap (giữ scope)

- 1D.1 ✅ (ready-for-dev): row → dict + validate + đọc file sync + error logging.
- **1D.2 (story này):** async generator theo thứ tự block, memory bounded. KHÔNG pacing, KHÔNG ring buffer, KHÔNG sort.
- 1D.3 Backtest Replay Driver: `ReplayDriver(rate="1x"|"100x"|"asap")` bơm event vào ring buffer đúng nhịp timestamp (dùng `stream_csv` làm nguồn).

---

### Project Conventions & Testing

- Python 3.11+ (local anaconda 3.12); pytest, `asyncio_mode=auto` — test là `async def`.
- Chạy test: `python3 -m pytest tests/unit/test_csv_streamer.py`. Console output bị hook lọc → redirect ra file và Read nếu cần full traceback.
- Test memory dùng fixture thật → chạy từ project root để path `fixtures/backtest/...` resolve đúng (`testpaths=["tests"]`, CWD = project root khi chạy pytest).
- Lint `ruff check` chạy trên CI (không cài local); tránh import thừa.
- Logging JSON qua stdout theo convention (ARCHITECTURE-SPINE Consistency Conventions).
- Async pattern tham chiếu: `ingestion/streams.py::stream_new_heads` (async generator hiện có cho realtime path).

### References

- [Source: `_bmad-output/epics.md`#Story-1D.2-CSV-Streamer] — user story + AC gốc (yield theo timestamp, memory < 50MB).
- [Source: `_bmad-output/implementation-artifacts/1D-1-csv-schema-mapping.md`] — `iter_csv_events`/`map_csv_row`/`CsvRowError` contract để reuse.
- [Source: `fixtures/backtest/README.md`] — row counts (luna 26,540), gzip storage, block/timestamp ranges. Pre-sorted-by-block đã verify runtime.
- [Source: `core/ring_buffer.py`] — downstream consume `dict`; khẳng định output dict.
- [Source: `ingestion/streams.py`] — async-generator pattern hiện có cho realtime, để 1D.2 khớp interface consumer.
- [Source: ARCHITECTURE-SPINE.md#AD-4] — "Dữ liệu lịch sử (backtest) dùng CSV/BigQuery."

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- RED: `pytest tests/unit/test_csv_streamer.py` → ImportError (stream_csv chưa có).
- GREEN: 5 passed sau khi thêm `stream_csv`.
- **Perf fix (phát hiện khi test memory):** `jsonschema.validate()` biên dịch lại schema MỖI lần gọi → test memory (26,540 row validate=True dưới `tracemalloc`) chạy >3 phút. Refactor `ingestion/csv_loader.py` dùng **validator biên dịch một lần, cache** (`_get_validator()` thay `_load_schema()` + `jsonschema.validate`). Kết quả: 2000 row validate=True dưới tracemalloc từ 34s → 0.63s. Lợi cho cả 1D.1/1D.3 (validate per-row ở scale).
- 1D-1 + 1D-2 tests: 13 passed in 9.64s; memory test peak << 50MB.

### Completion Notes List

- `stream_csv` là async generator mỏng bọc `iter_csv_events` (1D.1): yield theo thứ tự block, verify non-decreasing + log WARN `csv_out_of_order` nếu vi phạm (vẫn yield), `await asyncio.sleep(0)` mỗi 1000 event.
- Lazy O(1) memory: test `tracemalloc` trên full luna fixture (26,540 row) peak < 50MB.
- **Refactor validator cache** trong `csv_loader.py` (ảnh hưởng `map_csv_row`): thay `jsonschema.validate()` per-call bằng `_get_validator()` cached — sửa perf, không đổi hành vi (1D.1 tests vẫn 8/8 pass).
- ruff không cài local (CI lint); import `asyncio`, `AsyncIterator` đều dùng.

### File List

- `ingestion/csv_loader.py` (UPDATE — add stream_csv; refactor to cached jsonschema validator)
- `tests/unit/test_csv_streamer.py` (NEW)

## Change Log

- 2026-07-09 — Implemented Story 1D.2 async CSV streamer; 5 tests incl. tracemalloc memory guard; cached jsonschema validator (perf fix for per-row validation at scale); status → review.
