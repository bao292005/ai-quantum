---
baseline_commit: aa9487a
type: build
---

# Story 1A.5: Heartbeat & Metrics

Status: done

## Story

As a **SRE**,
I want **metric `ingestion_ws_last_message_seconds` (Prometheus Gauge) được cập nhật mỗi khi nhận message và cảnh báo khi luồng stall > 15s**,
so that **on-call engineer phát hiện luồng ingestion bị đứng mà không cần đọc log thủ công**.

## Acceptance Criteria

1. **AC1 — Module tồn tại:** `ingestion/metrics.py` export `record_message()` và `start_stall_watchdog(threshold_s=15)`.

2. **AC2 — Gauge metric:** `ingestion_ws_last_message_seconds` là Prometheus `Gauge` track số giây kể từ message cuối cùng. Cập nhật bằng `record_message()` mỗi khi nhận block header.

3. **AC3 — Stall detection:** `start_stall_watchdog(threshold_s=15)` chạy background coroutine kiểm tra mỗi 5s. Nếu `time.time() - last_message_time > threshold_s` → log WARNING `{"event": "stream_stalled", "seconds_since_last": X}`.

4. **AC4 — /metrics endpoint:** Expose Prometheus text format qua `GET http://localhost:9090/metrics`. Dùng `prometheus_client.start_http_server(9090)` hoặc tích hợp với FastAPI (Epic 5) — cho PoC dùng standalone HTTP server là đủ.

5. **AC5 — prometheus-client dependency:** `prometheus-client>=0.19` phải có trong `[project] dependencies` của `pyproject.toml`.

6. **AC6 — Unit tests:** `tests/unit/test_metrics.py` cover:
   - `record_message()` cập nhật timestamp
   - Sau 15s không gọi `record_message()` → watchdog log WARN
   - Metric name đúng `ingestion_ws_last_message_seconds`

## Tasks / Subtasks

- [x] **Task 1 — Thêm prometheus-client dependency** (AC5)
  - [x] Thêm `"prometheus-client>=0.19"` vào `[project] dependencies` trong `pyproject.toml`
  - [x] Verify `from prometheus_client import Gauge, start_http_server` import được (upgraded installed 0.14.1 → 0.25.0)

- [x] **Task 2 — Implement metrics.py** (AC1, AC2, AC3)
  - [x] Tạo `Gauge("ingestion_ws_last_message_seconds", "Seconds elapsed since the last WebSocket message was received")`
  - [x] `record_message()`: reset `_last_message_time = time.time()` và `gauge.set(0)`
  - [x] `start_stall_watchdog(threshold_s=15)`: asyncio background task loop 5s check (interval configurable for tests)
  - [x] Log dạng JSON structured với `logging` (`{"event":"stream_stalled",...}`)

- [x] **Task 3 — /metrics endpoint** (AC4)
  - [x] `start_metrics_server(port=9090)` gọi `prometheus_client.start_http_server(port)`; trả về `(server, thread)` để shutdown
  - [x] Note: Epic 5 (FastAPI) sẽ integrate endpoint này sau — PoC standalone là đủ

- [x] **Task 4 — Unit tests** (AC6)
  - [x] Control timestamp bằng `_Clock` monkeypatch lên `metrics.time.time`
  - [x] Test watchdog task (interval nhỏ + cancel) + `_check_stall` deterministic; thêm test /metrics endpoint (AC4)

## Dev Notes

**Loại story:** `[BUILD]` — blockedBy: 1A.4 (stream_new_heads là source gọi `record_message()`).

**CRITICAL — prometheus-client package name:** Package trên PyPI là `prometheus-client` (hyphen), import là `prometheus_client` (underscore). Đừng nhầm.

**Implementation pattern:**
```python
# ingestion/metrics.py
import asyncio
import json
import logging
import time
from prometheus_client import Gauge, start_http_server

logger = logging.getLogger(__name__)

_GAUGE = Gauge(
    "ingestion_ws_last_message_seconds",
    "Seconds elapsed since the last WebSocket message was received"
)
_last_message_time: float = time.time()

def record_message() -> None:
    global _last_message_time
    _last_message_time = time.time()
    _GAUGE.set(0)  # just received — reset to 0

async def _watchdog_loop(threshold_s: float) -> None:
    while True:
        await asyncio.sleep(5)
        elapsed = time.time() - _last_message_time
        _GAUGE.set(elapsed)
        if elapsed > threshold_s:
            logger.warning(json.dumps({
                "event": "stream_stalled",
                "seconds_since_last": round(elapsed, 1),
                "threshold_s": threshold_s,
            }))

def start_stall_watchdog(threshold_s: float = 15.0) -> asyncio.Task:
    return asyncio.create_task(_watchdog_loop(threshold_s))

def start_metrics_server(port: int = 9090) -> None:
    start_http_server(port)
    logger.info(json.dumps({"event": "metrics_server_started", "port": port}))
```

**Tích hợp với stream_new_heads (Story 1A.4):**
```python
# consumer code (pipeline orchestrator 1E.1 sẽ làm sau)
from ingestion.metrics import record_message, start_stall_watchdog

async def run_ingestion(client):
    start_stall_watchdog(threshold_s=15)
    async for head in stream_new_heads(client):
        record_message()
        # ... process head
```

**Gauge semantics:** `_GAUGE.set(0)` khi nhận message (elapsed=0). Watchdog update mỗi 5s: `_GAUGE.set(time.time() - _last_message_time)`. Prometheus scrape sẽ thấy giá trị tăng dần nếu stream stalled.

**prometheus_client collision với test:** `Gauge` registration là global. Nếu test khởi tạo Gauge nhiều lần → `ValueError: Duplicated timeseries`. Fix: dùng `prometheus_client.REGISTRY.unregister()` trong teardown, hoặc dùng `CollectorRegistry(auto_describe=True)` riêng cho test:
```python
# tests/unit/test_metrics.py — isolate registry
from prometheus_client import CollectorRegistry, Gauge as PGauge

def test_gauge_name(monkeypatch):
    # Import metrics module và check gauge name qua _GAUGE._name
    from ingestion import metrics
    assert metrics._GAUGE._name == "ingestion_ws_last_message_seconds"
```

**asyncio_mode=auto** đã set — không cần mark. Watchdog là `asyncio.Task` — test bằng `asyncio.sleep(0)` hoặc mock `time.time()`.

**Port 9090 vs 8547:** Mock WSS dùng port 8547 cho health. Metrics server dùng port 9090 (Prometheus default). Không conflict.

**Epic 5 integration note:** Khi Epic 5 (FastAPI) được build, `start_metrics_server` sẽ được thay bằng FastAPI route `GET /metrics` dùng `prometheus_client.generate_latest()`. Story này cung cấp standalone server cho PoC — Epic 5 sẽ refactor nếu cần.

### Project Structure Notes

```
ingestion/
  metrics.py         ← TẠO MỚI
tests/
  unit/
    test_metrics.py  ← TẠO MỚI
pyproject.toml       ← UPDATE (thêm prometheus-client>=0.19 vào dependencies)
```

### References

- `ingestion/streams.py` — source events gọi `record_message()` (Story 1A.4)
- `_bmad-output/epics.md#Story 1A.5`
- Architecture AD-1: asyncio — watchdog phải là coroutine, không thread
- Story 1E.1 (pipeline orchestrator): sẽ gọi `start_stall_watchdog()` và `start_metrics_server()`
- Epic 5: FastAPI integration sẽ expose `/metrics` route thay `start_http_server`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (BMad dev-story workflow)

### Debug Log References

- Metrics unit tests: `pytest tests/unit/test_metrics.py` → 8 passed
- Full suite: `pytest` → 127 passed, 1 skipped (external :8546 connect test), 0 regressions
- Endpoint smoke: `GET /metrics` on a free port returns `ingestion_ws_last_message_seconds 0.0`

### Completion Notes List

- **prometheus-client version:** Env had 0.14.1 (< AC5's `>=0.19`). Added `prometheus-client>=0.19`
  to `pyproject.toml` and upgraded the installed package to **0.25.0** so the environment honestly
  satisfies the declared floor. All APIs used (`Gauge`, `start_http_server`, `REGISTRY`) are stable.
- **Design for testability:** Extracted `_check_stall(threshold_s)` (pure: refreshes gauge + logs the
  structured WARNING, returns elapsed) out of the 5s loop so AC3 stall detection is tested
  deterministically with a controllable clock — no real sleeping. `start_stall_watchdog` keeps the
  AC-specified `threshold_s=15` default and adds an optional `interval_s` (default 5.0) so the watchdog
  task can be exercised quickly in tests.
- **Gauge semantics (AC2):** `record_message()` sets the gauge to 0 on each message; the watchdog sets
  it to the elapsed seconds every interval, so a Prometheus scrape sees the value climb while stalled.
- **/metrics endpoint (AC4):** `start_metrics_server(port=9090)` wraps `start_http_server` and returns
  the `(WSGIServer, thread)` pair (prometheus-client 0.18+) so the server is shutdownable — used by the
  endpoint test and available for the Epic 5 / pipeline (1E.1) lifecycle. Epic 5 will later replace this
  standalone server with a FastAPI `/metrics` route via `generate_latest()`.
- **Global gauge registration:** `_GAUGE` registers once in the default `REGISTRY` at import; no
  duplicate-timeseries issue (single import) and the full suite shows no cross-test interference.
- **AC coverage:** AC1/AC2 (module + gauge), AC3 (stall watchdog + WARNING), AC4 (endpoint), AC5
  (dependency) all satisfied; AC6 unit tests cover record_message, stall/no-stall, metric name,
  watchdog task, and the endpoint.

### File List

- `ingestion/metrics.py` (NEW)
- `tests/unit/test_metrics.py` (NEW)
- `pyproject.toml` (MODIFIED — added `prometheus-client>=0.19` to dependencies)

## Change Log

- 2026-07-08: Implemented `ingestion/metrics.py` (gauge `ingestion_ws_last_message_seconds`,
  `record_message`, stall watchdog, `/metrics` server); added unit tests; declared and upgraded
  `prometheus-client>=0.19`. Story 1A.5 → review.
- 2026-07-08: Code review — applied 2 patches (`/metrics` bind `127.0.0.1` default, watchdog clock
  reset on start) + 1 regression test. 130 passed. Story 1A.5 → done.

## Review Findings

Code review (2026-07-08, adversarial 3-layer: Blind Hunter + Edge Case Hunter + Acceptance Auditor).

### Patch (resolved 2026-07-08)

- [x] [Review][Patch] `start_metrics_server` default `addr="0.0.0.0"` exposes /metrics on all interfaces; AC4 says `localhost:9090` — default to `127.0.0.1`, keep addr as opt-in [ingestion/metrics.py] — FIXED
- [x] [Review][Patch] `_last_message_time` seeded at import time → the watchdog can emit a false `stream_stalled` before the first message; reset the clock when `start_stall_watchdog` starts [ingestion/metrics.py] — FIXED + regression test `test_watchdog_reset_prevents_startup_false_stall`

### Deferred

- [x] [Review][Defer] Watchdog `asyncio.Task` lifecycle/cancellation is caller responsibility — wire cancel-on-shutdown in 1E.1 [ingestion/metrics.py:~76]
- [x] [Review][Defer] Module-level `Gauge` registration would raise `ValueError: Duplicated timeseries` on re-import/reload — add a registry guard if/when needed [ingestion/metrics.py:~24]
- [x] [Review][Defer] `start_metrics_server`/`start_stall_watchdog` are not wired into any running process yet — 1E.1 pipeline orchestrator will start them [ingestion/metrics.py]

### Dismissed (false positives / over-defensive / spec-conformant)

- `record_message()` sets gauge to `0.0` — this is the AC2/spec pattern (reset on message, watchdog climbs the value each interval).
- `_last_message_time` thread-safety — single asyncio loop + CPython GIL; prometheus-client locks its own value; over-cautious.
- `_check_stall` uses `elapsed > threshold_s` — matches AC3 wording "stall > 15s".
- `start_stall_watchdog` requires a running loop / `start_metrics_server` may raise `OSError` on port-in-use — standard asyncio/socket semantics; caller responsibility.
- AC1 extra `interval_s` param, AC3 extra `threshold_s` log key, AC6 test-approach — additive/stronger; intent satisfied.
