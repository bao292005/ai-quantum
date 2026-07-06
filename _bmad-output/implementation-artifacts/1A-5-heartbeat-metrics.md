---
baseline_commit: aa9487a
type: build
---

# Story 1A.5: Heartbeat & Metrics

Status: ready-for-dev

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

- [ ] **Task 1 — Thêm prometheus-client dependency** (AC5)
  - [ ] Thêm `"prometheus-client>=0.19"` vào `[project] dependencies` trong `pyproject.toml`
  - [ ] Verify `from prometheus_client import Gauge, start_http_server` import được

- [ ] **Task 2 — Implement metrics.py** (AC1, AC2, AC3)
  - [ ] Tạo `Gauge("ingestion_ws_last_message_seconds", "Seconds since last WS message")`
  - [ ] `record_message()`: gọi `gauge.set(time.time() - _last_ts)` và update `_last_ts = time.time()`
  - [ ] `start_stall_watchdog(threshold_s=15)`: asyncio background task loop 5s check
  - [ ] Log dạng JSON structured với `logging`

- [ ] **Task 3 — /metrics endpoint** (AC4)
  - [ ] `start_metrics_server(port=9090)` gọi `prometheus_client.start_http_server(port)`
  - [ ] Note: Epic 5 (FastAPI) sẽ integrate endpoint này sau — PoC standalone là đủ

- [ ] **Task 4 — Unit tests** (AC6)
  - [ ] Mock `time.time()` để control timestamp
  - [ ] Test watchdog bằng `asyncio.sleep(0)` để advance event loop

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

### Debug Log References

### Completion Notes List

### File List

- `ingestion/metrics.py` (NEW)
- `tests/unit/test_metrics.py` (NEW)
- `pyproject.toml` (UPDATE — thêm `prometheus-client>=0.19` vào dependencies)
