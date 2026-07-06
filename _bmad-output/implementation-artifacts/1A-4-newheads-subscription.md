---
baseline_commit: aa9487a
type: build
---

# Story 1A.4: newHeads Subscription

Status: ready-for-dev

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

- [ ] **Task 1 — Implement stream_new_heads** (AC1, AC2, AC3, AC4)
  - [ ] Dùng `await client.w3.eth.subscribe("newHeads")` — API của web3.py 6.x
  - [ ] Loop `async for header in subscription:` → yield header dict
  - [ ] Wrap trong `try/finally` để cleanup khi cancelled
  - [ ] Convert hex values nếu cần (web3.py 6.x trả về `AttributeDict` với Python types)

- [ ] **Task 2 — Integration test** (AC5)
  - [ ] Check port 8546 trước, skipif nếu không có
  - [ ] Connect EthereumClient → call stream_new_heads → collect N headers
  - [ ] Assert count ≥ 5 và shape đúng

- [ ] **Task 3 — Unit test** (AC6)
  - [ ] Mock `AsyncWeb3` và subscription object
  - [ ] Test cancel bằng `asyncio.Task.cancel()`

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

### Debug Log References

### Completion Notes List

### File List

- `ingestion/streams.py` (NEW)
- `tests/unit/test_streams.py` (NEW)
- `tests/integration/test_streams.py` (NEW)
