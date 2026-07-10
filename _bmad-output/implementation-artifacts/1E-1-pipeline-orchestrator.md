---
baseline_commit: 0e04db60825409ad60bf9c50f73db6977cb733f6
type: build
---

# Story 1E.1: Pipeline Orchestrator

Status: done

## Story

As a **Data Engineer**,
I want **a `python -m ingestion.pipeline` entrypoint that wires the realtime path (WebSocket newHeads + logs → Track 1B EventRouter → Track 1C ring buffer) and a backtest path (CSV → Track 1D ReplayDriver → ring buffer) behind a single CLI, exposing ingest metrics and shutting down cleanly on SIGTERM**,
so that **the full ingestion pipeline runs end-to-end against the mock WSS (or a real node) and against historical fixtures — feeding a live ring buffer for Epic 2**.

## Acceptance Criteria

1. **AC1 — Entrypoint tồn tại:** `ingestion/pipeline.py` chạy được qua `python -m ingestion.pipeline` với argparse CLI:
   `--source {mock,backtest}` (required), `--scenario {luna,ftx,normal}` (backtest), `--speed` (backtest, default `100x`), `--capacity` (ring buffer, default 1000), `--metrics-port` (default 9090), `--whitelist` (path, default `ingestion/whitelist.yaml`).

2. **AC2 — Realtime wiring (`--source=mock`):** Kết nối `EthereumClient` tới `WSS_URL` (mock ws://localhost:8546), subscribe **newHeads** + **logs** (address filter = các contract trong whitelist), route mỗi log qua `EventRouter.route(log, block_ts)`; nếu ra `TickDataEvent` → `ring_buffer.write(event.to_dict())`.

3. **AC3 — Counters tăng:** Prometheus counters `blocks_processed_total` (mỗi newHeads) và `events_ingested_total` (mỗi event ghi vào ring buffer) tồn tại trong `ingestion/metrics.py` và tăng đúng. Expose qua `/metrics` (dùng `start_metrics_server`).

4. **AC4 — Backtest wiring (`--source=backtest`):** `ReplayDriver(DequeRingBuffer(capacity), rate=speed).run(fixture)` bơm event vào ring buffer; `events_ingested_total` tăng theo số event replay. Fixture resolve từ `--scenario` (reuse `tools.mock_wss.replay.resolve_scenario_file` hoặc path trực tiếp `fixtures/backtest/`).

5. **AC5 — Graceful shutdown:** Bắt `SIGTERM`/`SIGINT` → set stop event → dừng consumer, unsubscribe + disconnect (realtime) hoặc dừng replay (backtest), teardown < 2s. Không treo, không zombie task; log JSON `{"event":"pipeline_shutdown", ...}`.

6. **AC6 — Metrics/heartbeat khởi động:** `start_metrics_server(port)` + `start_stall_watchdog()` chạy; `record_message()` gọi mỗi message realtime (heartbeat). Watchdog task bị cancel sạch lúc shutdown.

7. **AC7 — Integration test:** `tests/integration/test_pipeline.py` self-host `MockWssServer` trên ephemeral port (theo convention project), chạy orchestrator `--source=mock` một lúc ngắn → assert ring buffer nhận > 0 event, `events_ingested_total`/`blocks_processed_total` > 0, và shutdown sạch. Backtest: chạy `--source=backtest --scenario luna --speed asap` trên fixture trimmed → ring buffer đầy tới capacity, `events_ingested_total` > 0.

8. **AC8 — Unit tests:** `tests/unit/test_pipeline.py` cover: CLI arg parsing, backtest orchestration (mock ring buffer), counter increments, SIGTERM handler set stop event.

## Tasks / Subtasks

- [x] **Task 1 — Counters trong metrics.py** (AC3)
  - [x] Thêm `EVENTS_INGESTED = Counter("events_ingested_total")`, `BLOCKS_PROCESSED = Counter("blocks_processed_total")` (expose trực tiếp, `.inc()`).

- [x] **Task 2 — Orchestrator core** (AC1, AC2, AC4, AC5, AC6)
  - [x] `ingestion/pipeline.py`: argparse; `run_backtest`, `run_realtime`, `_amain`/`main`.
  - [x] Realtime: combined subscription loop (newHeads + logs, một loop `process_subscriptions()`, dispatch theo subscription id, `wait_for` timeout để poll stop khi idle).
  - [x] Backtest: `ReplayDriver(DequeRingBuffer(capacity), rate).run(fixture)`.
  - [x] SIGTERM/SIGINT handler qua `loop.add_signal_handler` → `asyncio.Event`.

- [x] **Task 3 — Tests** (AC7, AC8)
  - [x] `tests/unit/test_pipeline.py` (5) + `tests/integration/test_pipeline.py` (1, self-host mock).

## Dev Notes

**Loại story:** `[BUILD]` — Track 1E, story tích hợp.
**blockedBy (tất cả DONE/review):** 1A (client/streams/metrics/reconnect/config), **1B (router/decoders/whitelist)**, 1C (DequeRingBuffer), 1D (ReplayDriver), **0.6 (mock emit ABI thật — bắt buộc để realtime decode được)**.

---

### 🔗 Previous Story Intelligence (bắt buộc)

- **1A:** `EthereumClient(cfg)` async ctx mgr, `.w3` sau connect (`ingestion/client.py`). `stream_new_heads(client)` (`streams.py`) subscribe newHeads, yield `{number,hash,timestamp,parentHash}`. `metrics.py`: `record_message()`, `start_stall_watchdog()→Task`, `start_metrics_server(port,addr)→(server,thread)`. web3 **7.16.0**: `sub_id = await w3.eth.subscribe("newHeads")`; consume `async for msg in w3.socket.process_subscriptions()` → `{"subscription":id,"result":...}`.
- **1B:** `EventRouter.from_yaml(path)` / `.route(log, block_ts) -> TickDataEvent|None` (unknown addr→None). `ContractWhitelist.from_yaml`; `whitelist._entries` keys = addresses (lowercase) — dùng làm address filter cho logs subscription.
- **1C:** `DequeRingBuffer(capacity)` sync `.write(dict)`. (Dùng buffer SYNC — single-consumer orchestrator; `AsyncRingBuffer` chỉ cần nếu nhiều coroutine ghi.)
- **1D:** `ReplayDriver(buffer, rate="asap"|"100x"|...).run(path) -> int`. `stream_csv`/`iter_csv_events` cho CSV.
- **0.6:** mock `build_raw_log` giờ emit ABI thật; decoder 1B `_to_int` xử lý blockNumber/logIndex hex-string → **realtime mock logs decode được**. Whitelist đã có Aave V2 pool.
- **Mock (0.5):** replay LẦN 1 duy nhất/lifetime, lazy-start khi có subscription đầu. Integration test **self-host `MockWssServer`** trên ephemeral port (xem `tests/integration/test_mock_wss_client.py`), KHÔNG phụ thuộc :8546 ngoài. Ở `speed=asap` với luna đầy đủ (26k) sẽ flood → **trim fixture ~10 block** cho test.

---

### ⚠️ Design Decision — combined subscription loop (KHÔNG reuse stream_new_heads cho realtime)

`w3.socket.process_subscriptions()` là **một iterator dùng chung** cho MỌI subscription trên connection. KHÔNG thể có 2 coroutine (một cho newHeads, một cho logs) cùng iterate nó — chúng sẽ giành/mất message của nhau. Vì vậy orchestrator realtime **tự subscribe cả newHeads + logs và chạy MỘT loop duy nhất**, dispatch theo `msg["subscription"]`:
- msg là newHeads → cập nhật `current_block_ts` (từ `result["timestamp"]`, hex→int), `blocks_processed_total += 1`, `record_message()`.
- msg là logs → `router.route(result, current_block_ts)`; nếu event → `ring_buffer.write(event.to_dict())`, `events_ingested_total += 1`, `record_message()`.

**block_timestamp cho log:** mock emit head(N) TRƯỚC logs(N) (xem `_replay_loop`), nên `current_block_ts` cập nhật từ head luôn có sẵn khi log tới. Với node thật thứ tự không đảm bảo → fallback dùng `current_block_ts` gần nhất (đủ cho PoC; ghi chú giới hạn). KHÔNG gọi `w3.eth.get_block` per-log (đắt).

---

### Implementation Pattern

```python
# ingestion/metrics.py  (thêm)
from prometheus_client import Counter

EVENTS_INGESTED = Counter("events_ingested_total", "Events written to the ring buffer")
BLOCKS_PROCESSED = Counter("blocks_processed_total", "Block headers processed")
```

```python
# ingestion/pipeline.py
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal

from core.ring_buffer import DequeRingBuffer
from ingestion import metrics
from ingestion.client import EthereumClient
from ingestion.config import load as load_config
from ingestion.csv_loader import ReplayDriver
from ingestion.router import EventRouter
from tools.mock_wss.replay import resolve_scenario_file

logger = logging.getLogger(__name__)
_NEWHEADS_TOPIC0 = None  # newHeads msgs have no topics; distinguish by subscription id


async def run_backtest(buffer, scenario, speed) -> int:
    path = resolve_scenario_file(scenario)
    n = await ReplayDriver(buffer, rate=speed).run(path)
    metrics.EVENTS_INGESTED.inc(n)
    return n


async def run_realtime(buffer, router, wss_url, stop: asyncio.Event) -> None:
    addresses = list(router._whitelist._entries)  # lowercase addresses
    async with EthereumClient(_cfg(wss_url)) as client:
        w3 = client.w3
        heads_id = await w3.eth.subscribe("newHeads")
        logs_id = await w3.eth.subscribe("logs", {"address": addresses})
        current_ts = 0
        try:
            async for msg in w3.socket.process_subscriptions():
                if stop.is_set():
                    break
                metrics.record_message()
                result = msg["result"]
                if msg["subscription"] == heads_id:
                    current_ts = int(result["timestamp"], 16) if isinstance(result["timestamp"], str) else int(result["timestamp"])
                    metrics.BLOCKS_PROCESSED.inc()
                elif msg["subscription"] == logs_id:
                    event = router.route(result, current_ts)
                    if event is not None:
                        buffer.write(event.to_dict())
                        metrics.EVENTS_INGESTED.inc()
        finally:
            for sid in (heads_id, logs_id):
                try:
                    await w3.eth.unsubscribe(sid)
                except Exception:
                    pass

# main(): parse args, start metrics server + watchdog, install SIGTERM handler
# (loop.add_signal_handler → stop.set()), dispatch to run_backtest/run_realtime,
# teardown in finally (cancel watchdog, shutdown metrics server).
```

> `_to_int`-style hex handling: newHeads `timestamp` là hex string trên wire (mock) hoặc int (web3 parsed) — guard cả hai. Logs `result` truyền thẳng vào `router.route` (decoder 1B `_to_int` đã lo blockNumber/logIndex hex).

### Guardrails

- **Buffer SYNC** (`DequeRingBuffer`) — orchestrator single-consumer, `write` là O(1) sync giữa các `await`. KHÔNG cần `AsyncRingBuffer`.
- **KHÔNG** tạo generator `stream_logs` riêng chạy song song với `stream_new_heads` (shared-iterator trap). Dùng combined loop.
- Shutdown < 2s: `loop.add_signal_handler(SIGTERM, stop.set)`; loop thoát ở `stop.is_set()`; unsubscribe best-effort; `EthereumClient.__aexit__` disconnect. Cancel watchdog task + `metrics` server shutdown.
- `--source=mock` giả định mock server đã chạy (`python -m tools.mock_wss --scenario luna`) trên `WSS_URL`. Integration test tự host `MockWssServer`.
- Mock replay 1 lần/lifetime → orchestrator subscribe SỚM (trước khi replay chạy hết). Với `speed=asap` + luna đầy → flood; test dùng fixture trim ~10 block.
- Reuse `resolve_scenario_file` (tools.mock_wss.replay) cho backtest path — KHÔNG hardcode fixture path.

### File Structure After 1E.1

```
ingestion/
  pipeline.py         ← NEW (orchestrator + __main__)
  metrics.py          ← UPDATE (2 counters)
  client.py/streams.py/router.py/whitelist.py/csv_loader.py ← EXISTING (reuse)
core/ring_buffer.py   ← EXISTING (DequeRingBuffer)
tests/unit/test_pipeline.py           ← NEW
tests/integration/test_pipeline.py    ← NEW
```

### Testing

- Python 3.11+; pytest `asyncio_mode=auto`. Integration test self-host mock (ephemeral port), trim fixture. Console output bị hook lọc → redirect file + Read.
- `python3 -m pytest tests/unit/test_pipeline.py tests/integration/test_pipeline.py`.
- ruff trên CI.

### References

- [Source: `_bmad-output/epics.md`#Story-1E.1] — nối 1A→1B→1C, `--source=mock`, counters, graceful shutdown SIGTERM drain<2s.
- [Source: `ingestion/streams.py`] — web3 v7 subscription pattern (process_subscriptions).
- [Source: `ingestion/router.py`, `whitelist.py`] — route + address filter.
- [Source: `ingestion/csv_loader.py`] — ReplayDriver backtest.
- [Source: `tools/mock_wss/{server,replay}.py`] — MockWssServer self-host; resolve_scenario_file; head-then-logs ordering.
- [Source: ARCHITECTURE-SPINE.md#AD-1,AD-2] — asyncio I/O tách lõi; ring buffer in-memory.

---

### Review Findings

- [x] [Review][Decision→Patch] Đổi realtime sang `route_validated()` — validate schema mỗi event live (validator cache rẻ), bọc trong try/except nên ValidationError chỉ skip 1 log. [ingestion/pipeline.py]
- [x] [Review][Patch] **HIGH:** bọc per-message dispatch trong try/except → log `log_route_error` + skip; 1 log lỗi (missing key / unknown topic / bad ts / schema fail) không còn giết loop. [ingestion/pipeline.py run_realtime]
- [x] [Review][Patch] Backtest chạy như task, race với `stop.wait()` → SIGTERM/SIGINT hủy được replay dài. [ingestion/pipeline.py _amain]
- [x] [Review][Patch] `--speed` làm rõ backtest-only trong help (orchestrator không điều khiển tốc độ mock; realtime bỏ qua --speed). [ingestion/pipeline.py]
- [x] [Review][Patch] Teardown bọc `asyncio.wait_for(..., timeout=2.0)` (unsubscribe) → shutdown trong ngân sách <2s. [ingestion/pipeline.py run_realtime finally]
- [x] [Review][Patch] Guard `current_ts==0` → skip + warn `log_before_first_head_skipped` (không stamp epoch-0). [ingestion/pipeline.py run_realtime]
- [x] [Review][Patch] Thêm `ContractWhitelist.addresses()` + `EventRouter.whitelist` property; `run_realtime` dùng `router.whitelist.addresses()` (hết chọc private). [ingestion/whitelist.py, router.py, pipeline.py]

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- Unit 5 passed ngay. Integration ban đầu FAIL (buffer rỗng).
- **Root cause (quan trọng):** ở `speed=asap`, mock replay chạy tới HẾT đồng bộ (delay=0, không await) NGAY khi có subscription đầu (newHeads) → logs subscription đăng ký quá muộn → 0 log. Debug: `heads=5 logs=0`. **Fix:** integration test dùng `speed=100x` (replay `await sleep` giữa các block → logs sub kịp attach, nhận blocks 2..N). Verify `100x`: heads=8 logs=16 decoded=16.
- GREEN: 6 passed. Full suite 244 passed, 1 skipped.

### Completion Notes List

- `ingestion/metrics.py`: thêm 2 Counter module-level `EVENTS_INGESTED`/`BLOCKS_PROCESSED`.
- `ingestion/pipeline.py`: CLI (`--source mock|backtest`, scenario/speed/capacity/metrics-port/whitelist/wss-url); `run_backtest` (ReplayDriver→ring buffer, `path=` override cho test); `run_realtime` (combined loop, `wait_for(__anext__, timeout=0.5)` để poll stop khi idle → shutdown <2s); `_amain` (metrics server best-effort, watchdog, SIGTERM/SIGINT handler, teardown trong finally).
- **Combined loop** đúng như thiết kế: một `process_subscriptions()`, dispatch theo `subscription id` (không dùng 2 generator vì shared-iterator).
- `_to_int` cho newHeads `timestamp` (hex str mock / int web3). Logs `result` truyền thẳng router (decoder `_to_int` lo blockNumber/logIndex).
- Buffer SYNC `DequeRingBuffer` (single-consumer).
- **Test learning (ghi nhớ):** mock KHÔNG dùng được ở `asap` cho path cần >1 subscription — dùng speed hữu hạn (100x) để 2 sub kịp register trước replay.
- ruff không cài local (CI lint).

### File List

- `ingestion/pipeline.py` (NEW)
- `ingestion/metrics.py` (UPDATE — counters)
- `tests/unit/test_pipeline.py` (NEW)
- `tests/integration/test_pipeline.py` (NEW)

## Change Log

- 2026-07-09 — Story 1E.1 pipeline orchestrator (realtime mock + backtest → ring buffer, counters, graceful shutdown); 6 tests incl. self-hosted mock integration; status → review.
