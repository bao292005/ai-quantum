---
baseline_commit: aa9487a
type: build
---

# Story 1A.4: newHeads Subscription

Status: done

## Story

As a **Kỹ sư Dữ liệu**,
I want **async generator `stream_new_heads(client)` subscribe `newHeads` và yield block header mới**,
so that **downstream filter (Track 1B, 1C) tiêu thụ từng block header mà không cần biết internals của WebSocket**.

## Acceptance Criteria

1. **AC1 — Module tồn tại:** `ingestion/streams.py` export `stream_new_heads`.

2. **AC2 — Async generator signature:** `async def stream_new_heads(client: EthereumClient) -> AsyncGenerator[dict, None]` — yield từng block header dict.

3. **AC3 — Block header shape:** Mỗi yielded dict phải có ít nhất: `number` (int), `hash` (str), `timestamp` (int), `parentHash` (str). Map từ `newHeads` subscription result của mock WSS.

4. **AC4 — Clean cancel:** Khi consumer `task.cancel()` hoặc break khỏi `async for` → generator exit sạch (no exception leaked, WebSocket connection không bị force-close).

5. **AC5 — Integration test với mock WSS:** `tests/integration/test_streams.py`:
   - Start mock WSS (Story 0.5) hoặc skip nếu port 8546 không open
   - Subscribe → nhận ≥ 5 block headers trong 10s ở speed=asap
   - Assert mỗi header có đủ fields AC3

6. **AC6 — Unit test với mock web3:** `tests/unit/test_streams.py`:
   - Mock `client.w3.eth.subscribe("newHeads")` trả về async iterator giả
   - Assert generator yield đúng số item, đúng shape

## Tasks / Subtasks

- [x] **Task 1 — Implement stream_new_heads** (AC1, AC2, AC3, AC4)
  - [x] `subscription_id = await client.w3.eth.subscribe("newHeads")` — web3.py **7.x** API (returns a HexStr id, NOT an iterator)
  - [x] Loop `async for message in client.w3.socket.process_subscriptions():` → `header = message["result"]` → yield header dict
  - [x] Wrap trong `try/finally` (unsubscribe) để cleanup khi cancelled / break / aclose
  - [x] Convert `HexBytes` hash/parentHash → `0x`-hex str; `number`/`timestamp` đã là `int`

- [x] **Task 2 — Integration test** (AC5)
  - [x] Self-host `MockWssServer` per test (repo Story 0.5 convention) thay vì phụ thuộc external :8546
  - [x] Connect EthereumClient → call stream_new_heads → collect N headers
  - [x] Assert count ≥ 5 và shape đúng, trong 10s ở speed=asap

- [x] **Task 3 — Unit test** (AC6)
  - [x] Mock `w3.eth.subscribe` + `w3.socket.process_subscriptions` (async iterator giả)
  - [x] Test cancel bằng `asyncio.Task.cancel()`, aclose, và unsubscribe-error swallow

## Dev Notes

**Loại story:** `[BUILD]` — blockedBy: 1A.2 (EthereumClient), 1A.3 (auto_reconnect optional wrapper).

**web3.py 6.x subscribe API:**
```python
# web3.py 6.x — eth.subscribe returns async generator
subscription = await w3.eth.subscribe("newHeads")
async for header in subscription:
    # header is AttributeDict with Python types (not hex strings for numbers)
    yield {
        "number": header["number"],
        "hash": header["hash"].hex() if isinstance(header["hash"], bytes) else header["hash"],
        "timestamp": header["timestamp"],
        "parentHash": header["parentHash"].hex() if isinstance(header["parentHash"], bytes) else header["parentHash"],
    }
```

**Full implementation pattern:**
```python
# ingestion/streams.py
from __future__ import annotations
from typing import AsyncGenerator
from ingestion.client import EthereumClient

async def stream_new_heads(client: EthereumClient) -> AsyncGenerator[dict, None]:
    subscription = await client.w3.eth.subscribe("newHeads")
    try:
        async for header in subscription:
            yield {
                "number": header["number"],
                "hash": _to_hex(header.get("hash")),
                "timestamp": header["timestamp"],
                "parentHash": _to_hex(header.get("parentHash")),
            }
    finally:
        # Cleanup: unsubscribe gracefully
        try:
            await client.w3.eth.unsubscribe(subscription)
        except Exception:
            pass  # Best-effort cleanup

def _to_hex(value) -> str:
    if isinstance(value, bytes):
        return "0x" + value.hex()
    return str(value) if value is not None else ""
```

**Mock WSS compatibility (Story 0.5):** Mock WSS tại `ws://localhost:8546` phát `newHeads` notification dạng:
```json
{
  "jsonrpc": "2.0",
  "method": "eth_subscription",
  "params": {
    "subscription": "<uuid>",
    "result": {
      "number": "0xe0ee91",
      "hash": "0x...",
      "timestamp": "0x...",
      "parentHash": "0x..."
    }
  }
}
```
web3.py 6.x xử lý parsing này tự động và trả về Python dict với int/str values.

**Integration test pattern:**
```python
# tests/integration/test_streams.py
import asyncio
import socket
import pytest
from ingestion.config import IngestionConfig
from ingestion.client import EthereumClient
from ingestion.streams import stream_new_heads

def is_mock_wss_up():
    with socket.socket() as s:
        return s.connect_ex(("localhost", 8546)) == 0

pytestmark = pytest.mark.skipif(
    not is_mock_wss_up(),
    reason="mock WSS not running — start with: python -m tools.mock_wss --scenario luna --speed asap"
)

async def test_stream_new_heads_receives_blocks():
    cfg = IngestionConfig(wss_url="ws://localhost:8546")
    headers = []
    async with EthereumClient(cfg) as client:
        async for head in stream_new_heads(client):
            headers.append(head)
            if len(headers) >= 5:
                break
    assert len(headers) >= 5
    for h in headers:
        assert "number" in h
        assert "hash" in h
        assert "timestamp" in h
```

**Cancel-safe pattern:** Quan trọng — consumer có thể `break` khỏi `async for` hoặc cancel task. `try/finally` trong generator đảm bảo cleanup:
```python
async def consumer():
    async with EthereumClient(cfg) as client:
        async for head in stream_new_heads(client):
            process(head)
            if should_stop():
                break  # finally block trong generator chạy, cleanup OK
```

**asyncio_mode=auto đã set** — không cần `@pytest.mark.asyncio` trong bất kỳ test nào.

### Project Structure Notes

```
ingestion/
  streams.py         ← TẠO MỚI
tests/
  unit/
    test_streams.py  ← TẠO MỚI
  integration/
    test_streams.py  ← TẠO MỚI (skip nếu không có mock WSS)
```

### References

- `ingestion/client.py` — `EthereumClient` (Story 1A.2)
- `ingestion/reconnect.py` — `@auto_reconnect` (Story 1A.3, có thể wrap stream_new_heads nếu muốn)
- `tools/mock_wss.py` — mock WSS server (Story 0.5), `ws://localhost:8546`
- `_bmad-output/epics.md#Story 1A.4`
- Architecture AD-4: WebSocket `eth_subscribe` là mandatory — không dùng HTTP polling
- Story 1C.1: Ring buffer sẽ consume từ `stream_new_heads`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (BMad dev-story workflow)

### Debug Log References

- Unit tests: `pytest tests/unit/test_streams.py` → 7 passed
- Integration tests: `pytest tests/integration/test_streams.py` → 2 passed (~0.4s each)
- Full suite: `pytest` → 119 passed, 1 skipped (external :8546 connect test), 0 regressions

### Completion Notes List

- **web3.py version drift (6.x → 7.x):** Story Dev Notes assume the v6 subscription API
  (`subscription = await w3.eth.subscribe("newHeads"); async for header in subscription`).
  The installed runtime is **web3 7.16.0**, where `eth.subscribe(...)` returns a subscription
  **id (HexStr)** and messages are consumed from the shared socket via
  `w3.socket.process_subscriptions()`, which yields `{"subscription": id, "result": <BlockHeader>}`.
  Implemented against the verified v7 API. Empirically confirmed against the mock WSS that
  `result.number`/`result.timestamp` arrive as `int` and `result.hash`/`result.parentHash` as
  `HexBytes` (hexbytes 1.3.1, whose `.hex()` has **no** `0x` prefix — so `_to_hex` prepends `0x`).
- **Pre-existing bug fixed in `ingestion/client.py` (Story 1A.2):** `WebSocketProvider` was
  constructed with `websocket_timeout=` — a valid kwarg in web3 6.x but **removed in 7.x**, raising
  `TypeError: ... unexpected keyword argument 'websocket_timeout'` on every real connection. This was
  never caught because the only test exercising a live connect (`test_client_connect.py`) is skipped
  unless an external server runs on :8546. Removed the kwarg; the connect timeout is still enforced by
  the existing `asyncio.wait_for(w3.provider.connect(), timeout=_CONNECT_TIMEOUT)` wrapper. This
  unblocks AC5 and repairs live connects for the whole 1A track.
- **Integration test design:** Follows the repo's Story 0.5 convention (self-hosted `MockWssServer`
  per test on an ephemeral port) instead of the fragile external-:8546 skipif, so AC5 runs in CI. The
  fixture is trimmed to the first ~10 blocks: at `speed=asap` an unbounded luna replay (26,540 events)
  floods web3's internal subscription queue faster than a 5-header consumer drains it (`QueueFull`),
  which also stalls a clean `unsubscribe`. A small bounded replay keeps subscribe/consume/teardown
  deterministic and fast (~0.4s/test) while still delivering ≥5 headers at asap.
- **AC coverage:** AC1–AC4 via `ingestion/streams.py` + unit tests (shape, ordering, subscribe call,
  cleanup on exhaustion/aclose/cancel, unsubscribe-error swallow); AC5 via integration tests;
  AC6 via unit tests.

### File List

- `ingestion/streams.py` (NEW)
- `tests/unit/test_streams.py` (NEW)
- `tests/integration/test_streams.py` (NEW)
- `ingestion/client.py` (MODIFIED — removed web3 6.x-only `websocket_timeout` kwarg)

## Change Log

- 2026-07-08: Implemented `stream_new_heads` async generator against web3.py 7.x subscription API;
  added unit + integration tests; fixed `websocket_timeout` regression in `ingestion/client.py`.
  Story 1A.4 → review.
- 2026-07-08: Code review — applied 4 patches (subscription_id filter, not-connected guard,
  `web3>=7.0` floor, free-port integration tests) + 2 new tests. 130 passed. Story 1A.4 → done.

## Review Findings

Code review (2026-07-08, adversarial 3-layer: Blind Hunter + Edge Case Hunter + Acceptance Auditor).

### Patch (resolved 2026-07-08)

- [x] [Review][Patch] Filter `process_subscriptions()` messages by `subscription_id` — a shared socket iterator yields ALL subscriptions; a future logs sub (Track 1B) on the same client would be mis-yielded as a block header [ingestion/streams.py] — FIXED + test `test_ignores_messages_from_other_subscriptions`
- [x] [Review][Patch] Guard `client.w3 is None` with a clear error instead of a cryptic `AttributeError` when the caller forgot to connect [ingestion/streams.py] — FIXED + test `test_raises_when_client_not_connected`
- [x] [Review][Patch] Bump dependency floor to `web3>=7.0` — code hard-requires the 7.x `w3.socket.process_subscriptions()` API; a fresh install resolving 6.x would silently break [pyproject.toml] — FIXED
- [x] [Review][Patch] Integration test uses fixed ports 8621/8622 → collision under `pytest -n` / TIME_WAIT; reuse the `_free_port()` pattern already in test_metrics.py [tests/integration/test_streams.py] — FIXED

### Deferred

- [x] [Review][Defer] Reorg/duplicate block numbers are yielded as-is — dedup is Track 1B/1C responsibility; document the contract [ingestion/streams.py]
- [x] [Review][Defer] `running_server` uses a fixed 0.3s readiness sleep (repo convention) — replace with a bind-readiness event later [tests/integration/test_streams.py:~50]
- [x] [Review][Defer] `_first_n_blocks` returns fewer than n for tiny fixtures → `_collect_heads(5)` would time out; add an assert guard [tests/integration/test_streams.py:~30]
- [x] [Review][Defer] Fixture missing in CI → `FileNotFoundError` instead of a clean skip [tests/integration/test_streams.py]

### Dismissed (false positives / over-defensive / spec-conformant)

- Reviewer claimed integration test omits `parentHash` assertion — FALSE: it is asserted (test_streams.py, `_collect_heads` loop).
- Reviewer claimed mock hex-string `number`/`timestamp` cause a TypeError — FALSE: web3 7.x middleware normalizes them to `int` (verified empirically; integration tests pass).
- `message["result"]` / `header["number"]`/`["timestamp"]` KeyError — web3 guarantees a formatted BlockHeader for a filtered newHeads subscription; over-defensive.
- `_to_hex(None)`/`_to_hex(b"")`/bare-str branch — cannot occur for real headers; over-defensive.
- AC6 "mock returns async iterator" & AC5 ":8546 skipif" wording divergences — intent satisfied (web3 7.x API + self-hosted mock is an improvement).
