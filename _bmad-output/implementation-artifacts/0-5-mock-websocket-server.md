---
baseline_commit: 186d98f8f25e4da0e1cd16100f350b9dd6f08ddc
---

# Story 0.5: Mock WebSocket Server

Status: done

## Story

As a **Data Engineer (Dev Track 1A/1B/1C/1D)**,
I want **một mock WebSocket server chạy tại `ws://localhost:8546` replay tick-data từ fixture CSV theo tốc độ điều chỉnh được**,
so that **các track downstream có thể phát triển và test Epic 1 (WS client, decoder, ring buffer, CSV loader) mà không cần Alchemy/Infura API key, cũng như dùng trong CI**.

## Acceptance Criteria

1. **AC1 — CLI entrypoint:** `python -m tools.mock_wss --file fixtures/backtest/luna_2022_05_09.csv --speed 1x` khởi động server, listen `ws://localhost:8546`. Support flag `--host`, `--port` (default 8546), `--file` (required), `--speed`, `--scenario`.

2. **AC2 — Speed control:**
   - `--speed 1x`: replay theo timestamp gap thật (dt giữa 2 event trong CSV)
   - `--speed 100x`: replay nhanh 100 lần
   - `--speed asap`: không sleep, phát liên tục
   Verify: ở 1x, wall-clock giữa 2 event xấp xỉ dt timestamp thật trong CSV (±5%); ở 100x nhanh gấp ~100 lần; ở asap toàn bộ fixture phát hết < 10s. (Lưu ý: fixture `luna` trải ~2.6 ngày dữ liệu nén, nên dùng `asap`/`100x` cho CI — không chạy 1x full.)

3. **AC3 — Protocol tương thích `eth_subscribe`:** Client dùng Web3.py `AsyncWeb3(WebSocketProvider(...))` phải subscribe được. Cụ thể:
   - Nhận `eth_subscribe` với params `["newHeads"]` → trả `subscription_id` UUID
   - Nhận `eth_subscribe` với params `["logs", {address, topics}]` → trả `subscription_id`
   - Đẩy notification format `{"jsonrpc": "2.0", "method": "eth_subscription", "params": {"subscription": id, "result": {...}}}`
   - `result` cho `newHeads` là BlockHeader dict (number, hash, timestamp, parentHash)
   - `result` cho `logs` là raw log (address, topics, data, blockNumber, transactionHash, logIndex)

4. **AC4 — Scenario switch:** `--scenario luna|ftx|normal` shortcut mapping đến 3 file fixture Story 0.4 (thay vì phải gõ full path).

5. **AC5 — Health endpoint:** HTTP endpoint `GET http://localhost:8547/health` trả `{"status": "ok", "current_block": N, "events_sent": M, "uptime_seconds": S}`. Port riêng để không lẫn với WS.

6. **AC6 — Graceful shutdown:** SIGTERM/SIGINT → drain queue trong 2s → close tất cả client connection → exit code 0.

7. **AC7 — Docker service:** `docker-compose.yml` (tạo mới hoặc update) có service `mock-wss` với image build từ project. Command: `python -m tools.mock_wss --scenario luna --speed 100x`. Expose port 8546, 8547.

8. **AC8 — Unit + integration test:**
   - `tests/unit/test_mock_wss.py`: test parse CLI arg, test speed calculation
   - `tests/integration/test_mock_wss_client.py`: dùng `websockets` async client connect, send `eth_subscribe`, assert nhận ≥ 100 msg trong 5s ở speed=100x, verify shape khớp JSON-RPC 2.0.

9. **AC9 — Log filter v1 (address-only):** Với subscription `"logs"`, chỉ hỗ trợ **exact match `address`** (string hoặc array of string). Field `topics` trong subscription params được **parse nhưng IGNORE trong v1** — emit tất cả log có address khớp bất kể topic. Ghi WARNING log server-side khi client gửi topics filter để dev biết topics không có tác dụng. Full topics matching (array-of-array OR semantics) là v2.

10. **AC10 — Backpressure trong `--speed asap`:** Server maintain outgoing queue tối đa **10.000 msg/client**. Nếu client chậm (queue đầy) → drop message cũ nhất, emit metric `mock_wss_dropped_total{client_id}`. Log WARNING mỗi 1000 drop. KHÔNG block replay loop để giữ throughput CI.

## Tasks / Subtasks

- [x] **Task 1 — Skeleton server** (AC 1, 3)
  - [x] Dùng library `websockets` (>= 12.0) — async native
  - [x] Handler cho JSON-RPC message
  - [x] Route `eth_subscribe` → generate UUID sub_id, đăng ký vào dict `{sub_id: subscription_type}`
  - [x] Route `eth_unsubscribe` → remove
  - [x] Ping/pong keepalive (websockets default)

- [x] **Task 2 — Replay engine** (AC 2, 4)
  - [x] Load CSV → sort theo (block_number, log_index)
  - [x] Loop: nếu speed=1x → `await asyncio.sleep(dt / 1)`; 100x → `dt / 100`; asap → không sleep
  - [x] Group event theo block → giữa các block emit `newHeads` cho subscriber loại 1 và emit `logs` cho subscriber loại 2

- [x] **Task 3 — Health endpoint** (AC 5)
  - [x] aiohttp mini app trên port riêng 8547 (aiohttp thay FastAPI — đã có sẵn, không thêm dep nặng)
  - [x] Chia sẻ state với WS handler qua `ServerState` singleton

- [x] **Task 4 — Graceful shutdown** (AC 6)
  - [x] `loop.add_signal_handler(SIGTERM/SIGINT, ...)` → set `asyncio.Event`
  - [x] Loop check event, drain queue, close ws
  - [x] Timeout 2s cưỡng bức exit

- [x] **Task 5 — CLI wrapper** (AC 1, 4)
  - [x] `argparse` cho args
  - [x] `--scenario` map thành `--file`
  - [x] `python -m tools.mock_wss --help` show usage rõ

- [x] **Task 6 — Docker** (AC 7)
  - [x] `Dockerfile` (python:3.11-slim, `pip install .`)
  - [x] `docker-compose.yml` service `mock-wss` (+ healthcheck)
  - [x] `docker compose config` validated (compose schema OK)

- [x] **Task 7 — Test** (AC 8)
  - [x] Unit test parse args + speed calc
  - [x] Integration test client với `pytest-asyncio`
  - [x] Integration test start server background, run test, stop

- [x] **Task 8 — Update sprint-status**

### Review Findings (AI)

_Code review 2026-07-05 — 3 adversarial layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor). 13 distinct findings: 3 decision-needed, 6 patch, 4 deferred._

**Decision-needed (resolved 2026-07-05 by bao → all converted to patch, all applied):**

- [x] **[Review][Patch] Expose `dropped_total` in `/health`** (was Decision ①→opt1) — AC10 metric `mock_wss_dropped_total` now surfaced in `ServerState.snapshot()`. [`tools/mock_wss/server.py` — `ServerState.snapshot`] — test: `test_snapshot_includes_dropped_total`.
- [x] **[Review][Patch] Package fixtures as package-data** (was Decision ②→opt1) — added `MANIFEST.in` (ships fixtures in sdist/wheel) + `QR_FIXTURES_DIR` override so resolution no longer relies on the coincidental Docker `COPY`/`parents[2]` path; Dockerfile comment clarifies the COPY is the intended mechanism. [`MANIFEST.in`, `tools/mock_wss/replay.py` — `FIXTURES_DIR`, `Dockerfile`]
- [x] **[Review][Patch] Fix AC2 "5 phút" spec text** (was Decision ③→opt1) — AC2 reworded to a general dt-based description; notes luna spans ~2.6 days, use asap/100x for CI. [`0-5-mock-websocket-server.md` — AC2]

**Patch (unambiguous fixes — all applied):**

- [x] **[Review][Patch] `_replay_loop` has no exception boundary** (HIGH) — per-block/per-row processing now guarded with WARN + skip, so a malformed row (KeyError/ValueError on column/amount/timestamp) can no longer silently kill replay while `/health` reports `ok`. [`tools/mock_wss/server.py` — `_replay_loop`] — test: `test_replay_survives_malformed_row`.
- [x] **[Review][Patch] `enqueue` drop semantics** (HIGH) — rewritten to check `full()`, evict oldest to guarantee room, then place the newest; returns `True` iff an eviction occurred. Guarantees placement (control-plane replies never evicted). [`tools/mock_wss/server.py` — `_Client.enqueue`] — test: `test_enqueue_drops_oldest_and_reports`.
- [x] **[Review][Patch] Fanout iterates live collections without snapshot** — `_fanout_head`/`_fanout_log` now iterate `list(self._clients)` / `list(client.subs.values())`. [`tools/mock_wss/server.py` — `_fanout_head`, `_fanout_log`]
- [x] **[Review][Patch] `__main__` swallows non-(FileNotFoundError,ValueError) errors** — broadened to `(OSError, ValueError)` so mislabeled `.gz`/`.csv` (`BadGzipFile`/`OSError`) exits 2 cleanly. [`tools/mock_wss/__main__.py` — `main`]
- [x] **[Review][Patch] Control-plane reply can be silently dropped** — subsumed by the `enqueue` rewrite (drop-oldest keeps the newest = the reply); documented in `_reply`. [`tools/mock_wss/server.py` — `_reply`]
- [x] **[Review][Patch] Unsubscribe/address input validation** — `eth_unsubscribe` now guards non-list params; `_subscribe` guards non-list params and filters non-string address entries. [`tools/mock_wss/server.py` — `_on_message`, `_subscribe`]

**Deferred (real but out of scope for a CI mock tool):**

- [x] **[Review][Defer] `_first_sub` one-shot never re-armed** — a client subscribing after the replay finishes gets a silent dead subscription. Deferred: by-design "replay từ đầu file, không lưu offset"; late-join re-arm is v2. [`tools/mock_wss/server.py`]
- [x] **[Review][Defer] Unbounded `client.subs` (sub-count DoS)** — no cap on subscriptions per client. Deferred: mock/CI tool, not production-exposed. [`tools/mock_wss/server.py`]
- [x] **[Review][Defer] `_drain_and_close` emptiness-based drain races in-flight send** — drain checks queue-empty, not send-complete. Deferred: 2s bounded shutdown is acceptable for a mock. [`tools/mock_wss/server.py`]
- [x] **[Review][Defer] `asyncio.sleep` not interruptible by `_stop` mid-sleep** — a long 1x inter-event gap delays shutdown up to that gap. Deferred: only affects 1x manual runs, not CI (asap/100x). [`tools/mock_wss/server.py` — `_replay_loop`]

## Dev Notes

### Bối cảnh

Đây là **utility duy nhất trong Epic 0 có logic**, không chỉ schema/data. Nó unblock **toàn bộ Track 1A** — Story 1A.4 (newHeads subscription) dependency direct. Cũng dùng trong CI để test Epic 1 pipeline end-to-end mà không cần external API.

### Ràng buộc kiến trúc

- **AD-4:** Real-time dùng WebSocket `eth_subscribe` — mock phải giả đúng protocol này.
- **AD-1:** Async I/O — dùng `websockets` async, không `sync-websocket`.
- **Stack:** Python 3.11+, FastAPI 0.104+ (cho health endpoint, không dùng vào WS).

### Quyết định thiết kế

1. **Port 8546:** convention Ethereum WS (mainnet geth cũng dùng port này). Client copy-paste config production dev-mode chỉ cần đổi host.

2. **JSON-RPC 2.0 format nghiêm ngặt** — không tự chế shape. Test client thật với Web3.py phải hoạt động.

3. **Library `websockets`, không `aiohttp`:** `websockets` chuyên WS, API rõ hơn. `aiohttp` overkill.

4. **Speed=asap để CI:** CI không được chạy 5 phút chỉ để test. `--speed asap` phát burst ngay.

5. **Không persist state:** mỗi lần start là replay từ đầu file. Không lưu offset.

### LLM-mistake prevention

- **KHÔNG dùng `ws://localhost` hardcode trong client test** — dùng fixture URL parametrized để test cả mock lẫn real.
- **KHÔNG quên `subscription_id` phải UUID string** — Web3.py verify format.
- **KHÔNG emit tất cả log cho 1 subscription "logs"** — phải filter theo `address` + `topics` client gửi. Nếu client không gửi filter → emit hết.
- **KHÔNG dùng `time.sleep()`** — blocking event loop. Dùng `await asyncio.sleep()`.
- **KHÔNG để CSV load full vào RAM** với file 100MB — dùng `csv.DictReader` streaming.
- **KHÔNG bỏ pattern JSON-RPC error response** — nếu client gửi method lạ (VD `eth_getBalance`) phải trả `{"error": {"code": -32601, "message": "Method not found"}}`.

### Files tạo mới

- `tools/__init__.py`
- `tools/mock_wss/__init__.py`
- `tools/mock_wss/__main__.py`
- `tools/mock_wss/server.py`
- `tools/mock_wss/replay.py`
- `tools/mock_wss/health.py`
- `Dockerfile` (nếu chưa có)
- `docker-compose.yml` (nếu chưa có) hoặc add service
- `tests/unit/test_mock_wss.py`
- `tests/integration/test_mock_wss_client.py`

### Files update

- `pyproject.toml` — thêm `websockets>=12.0`, `pytest-asyncio>=0.23`
- `_bmad-output/sprint-status.yaml`

### Dependency

- Story 0.1 (`validate_tick`) — để verify event emit đúng schema. **Cũng phụ thuộc `pyproject.toml` init từ 0.1** (thêm `websockets>=12.0`, `pytest-asyncio>=0.23` vào cùng file).
- Story 0.4 (fixtures) — nguồn dữ liệu (nếu 0.4 chọn `.csv.gz`, mock server phải support `gzip.open`).

### Testing

- `pytest tests/integration/test_mock_wss_client.py -v` phải pass local + CI
- Manual smoke test:
  ```bash
  python -m tools.mock_wss --scenario normal --speed 100x &
  sleep 1
  curl http://localhost:8547/health
  # verify status=ok
  kill %1
  ```

### References

- [Source: _bmad-output/architecture/architecture-mps-defi-risk/ARCHITECTURE-SPINE.md#AD-4] — WebSocket protocol
- [Source: _bmad-output/epics.md#Story-0.5] — AC gốc
- [Source: _bmad-output/implementation-artifacts/0-1-tick-data-json-schema.md] — Schema dependency
- [Source: _bmad-output/implementation-artifacts/0-4-historical-backtest-fixtures.md] — Fixture files
- Ethereum JSON-RPC eth_subscribe spec: https://geth.ethereum.org/docs/interacting-with-geth/rpc/pubsub
- `websockets` library docs: https://websockets.readthedocs.io/en/12.0/

## Dev Agent Record

### Agent Model Used
claude-opus-4-6 (BMad dev-story workflow)

### Debug Log References

- **Replay-timing bug (fixed):** initial design started `_replay_loop` immediately in
  `run()`. At `--speed asap` the whole fixture burst-replayed in <1s — before a client
  connected and subscribed — so late subscribers received zero notifications. Fix: lazy
  start. `_replay_loop` now awaits `_await_first_subscription()` (an `asyncio.Event` set
  in `_subscribe`) before walking the fixture, consistent with Dev Notes "mỗi lần start
  là replay từ đầu file. Không lưu offset." Verified via smoke test: heads=2832, logs=7168
  received by a client connecting 0.4s after server start.
- **AC10 backpressure confirmed:** asap-speed smoke against a deliberately slow reader
  logged `mock_wss_dropped_total` every 1000 drops and never stalled the replay loop.
- **AC6 graceful shutdown confirmed:** `kill -TERM` → drain → close → `EXIT_CODE=0`.
- **AC5 health confirmed:** `GET /health` → `200` with
  `{"status":"ok","current_block":N,"events_sent":M,"uptime_seconds":S}`.

### Completion Notes List

- Health endpoint implemented with **aiohttp** (already a lightweight transitive dep,
  no FastAPI/uvicorn added) per user decision — served on a separate port (8547) so it
  never collides with WS traffic (8546).
- Pure replay helpers (`replay.py`) are side-effect-free and unit-tested without a live
  server; the live JSON-RPC round-trip is covered by the integration suite.
- AC9 v1 scope honored: `logs` subscriptions filter on **address only**; a `topics`
  filter is parsed but ignored with a server-side WARNING.
- All 81 tests pass (55 pre-existing + 26 new), no regressions.

### File List

**New:**
- `tools/__init__.py`
- `tools/mock_wss/__init__.py`
- `tools/mock_wss/__main__.py`
- `tools/mock_wss/server.py`
- `tools/mock_wss/replay.py`
- `tools/mock_wss/health.py`
- `Dockerfile`
- `docker-compose.yml`
- `tests/unit/test_mock_wss.py`
- `tests/integration/test_mock_wss_client.py`

**New (code review):**
- `MANIFEST.in` — ship fixtures in sdist/wheel builds
- `_bmad-output/implementation-artifacts/deferred-work.md` — 4 deferred review findings

**Modified:**
- `pyproject.toml` — added `websockets>=12.0`, `aiohttp>=3.9.0`; set pytest `asyncio_mode = "auto"`
- `_bmad-output/sprint-status.yaml` — status transitions

## Change Log

| Date       | Change                                                              |
|------------|---------------------------------------------------------------------|
| 2026-07-05 | Implemented Story 0.5 mock WebSocket server (Tasks 1–8, all ACs). Lazy replay-loop start fixes late-subscriber timing. Status → review. |
| 2026-07-05 | Code review (3 adversarial layers): 9 patches applied (replay exception boundary, enqueue drop-oldest semantics, `dropped_total` in /health, fanout snapshotting, broadened CLI error handling, input validation, fixtures packaging via MANIFEST.in + `QR_FIXTURES_DIR`, AC2 spec-text fix). 4 findings deferred (see deferred-work.md). +4 regression tests (85 pass). Status → done. |
