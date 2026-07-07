---
baseline_commit: 55c0cec9cf4d68710d43aee977f63ec0d16bb522
type: build
---

# Story 1A.2: AsyncWeb3 Client Wrapper

Status: done

## Story

As a **Kỹ sư Dữ liệu**,
I want **class `EthereumClient` wrap `AsyncWeb3(WebSocketProvider)` với timeout và context manager**,
so that **mọi consumer (Track 1B, 1D, 1E) dùng cùng interface kết nối WebSocket mà không cần biết internals của web3.py**.

## Acceptance Criteria

1. **AC1 — Module tồn tại:** `ingestion/client.py` export `EthereumClient`.

2. **AC2 — Kết nối thành công:** `await client.connect()` tạo `AsyncWeb3(WebSocketProvider(url, timeout=3))` và lưu vào `client.w3`.

3. **AC3 — Timeout:** Raise `ConnectionError` nếu kết nối không thiết lập được trong 3 giây.

4. **AC4 — Context manager:** `async with EthereumClient(cfg) as client:` — enter gọi connect(), exit gọi disconnect() (close WebSocket).

5. **AC5 — web3 dependency:** `web3>=6.11` phải có trong `[project] dependencies` của `pyproject.toml`.

6. **AC6 — Unit tests:** `tests/unit/test_client.py` cover:
   - Kết nối thành công với mock URL (mock WebSocketProvider)
   - Raise `ConnectionError` khi timeout

7. **AC7 — Integration test (optional, mark skip nếu không có mock WSS):** `tests/integration/test_client_connect.py` — kết nối thật đến `ws://localhost:8546` khi mock WSS đang chạy.

## Tasks / Subtasks

- [x] **Task 1 — Thêm web3 dependency** (AC5)
  - [x] Thêm `"web3>=6.11"` vào `[project] dependencies` trong `pyproject.toml`
  - [x] Chạy `pip install -e ".[dev]"` để verify không conflict

- [x] **Task 2 — Implement EthereumClient** (AC1, AC2, AC3, AC4)
  - [x] Import `AsyncWeb3, WebSocketProvider` từ `web3`
  - [x] `__init__(self, cfg: IngestionConfig)` — lưu config
  - [x] `async connect(self) -> AsyncWeb3` — tạo provider với timeout=3s, trả về `self.w3`
  - [x] `async disconnect(self)` — gọi `await self.w3.provider.disconnect()`
  - [x] `__aenter__` / `__aexit__` cho context manager
  - [x] Wrap exception thành `ConnectionError` nếu web3 raise timeout/connection refused

- [x] **Task 3 — Unit tests** (AC6)
  - [x] Mock `WebSocketProvider` bằng `unittest.mock.AsyncMock`
  - [x] Test timeout bằng cách mock raise `asyncio.TimeoutError`

- [x] **Task 4 — Integration test** (AC7)
  - [x] `pytest.mark.skipif` kiểm tra port 8546 có đang lắng nghe không
  - [x] Nếu mock WSS từ Story 0.5 đang chạy: connect và assert `client.w3.is_connected()`

## Dev Notes

**Loại story:** `[BUILD]` — blockedBy: 1A.1 (cần `IngestionConfig`).

**CRITICAL — web3.py version:** Dùng `web3>=6.11`. API của web3.py 6.x khác đáng kể so với 5.x:
- `from web3 import AsyncWeb3` (không phải `Web3`)
- `from web3.providers import WebSocketProvider` (không phải `WebsocketProvider`)
- Provider là async-native, không cần thread executor

**web3.py 6.x WebSocketProvider pattern:**
```python
from web3 import AsyncWeb3
from web3.providers.websocket import WebSocketProvider

async def connect(url: str, timeout: float = 3.0) -> AsyncWeb3:
    provider = WebSocketProvider(url, websocket_timeout=timeout)
    w3 = AsyncWeb3(provider)
    await w3.provider.connect()  # explicit connect in v6
    return w3
```

**Timeout handling:** WebSocketProvider raise `asyncio.TimeoutError` hoặc `ConnectionRefusedError` nếu không kết nối được. Wrap cả hai thành `ConnectionError`:
```python
try:
    await asyncio.wait_for(w3.provider.connect(), timeout=3.0)
except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as exc:
    raise ConnectionError(f"Cannot connect to {url}: {exc}") from exc
```

**Context manager pattern:**
```python
@dataclass
class EthereumClient:
    cfg: IngestionConfig
    w3: AsyncWeb3 | None = field(default=None, init=False)

    async def connect(self) -> AsyncWeb3:
        ...

    async def disconnect(self) -> None:
        if self.w3 and self.w3.provider:
            await self.w3.provider.disconnect()

    async def __aenter__(self) -> "EthereumClient":
        await self.connect()
        return self

    async def __aexit__(self, *_) -> None:
        await self.disconnect()
```

**Mock WSS cho integration test:** Story 0.5 tạo mock WSS tại `ws://localhost:8546`. Kiểm tra port trước khi chạy integration test:
```python
import socket
def is_port_open(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("localhost", port)) == 0

pytestmark = pytest.mark.skipif(
    not is_port_open(8546),
    reason="mock WSS not running on :8546"
)
```

**Không dùng `websockets` library trực tiếp** trong story này — web3.py 6.x tự quản lý websockets internally. Story 1A.4 (`stream_new_heads`) mới gọi subscribe qua `client.w3`.

### Project Structure Notes

```
ingestion/
  client.py          ← TẠO MỚI
tests/
  unit/
    test_client.py   ← TẠO MỚI
  integration/
    test_client_connect.py  ← TẠO MỚI (optional/skip)
pyproject.toml       ← UPDATE (thêm web3>=6.11 vào dependencies)
```

### References

- `ingestion/config.py` — `IngestionConfig` (Story 1A.1, phải done trước)
- `pyproject.toml` — cần update dependencies
- `_bmad-output/epics.md#Story 1A.2`
- Architecture AD-4: phải dùng WebSocket `eth_subscribe`, không REST polling
- Story 0.5: mock WSS tại `ws://localhost:8546` cho integration test
- web3.py 6.x docs: https://web3py.readthedocs.io/en/stable/web3.providers.html#websocket-provider

### Review Findings

- [ ] [Review][Decision] — N/A (no decision-needed for this story)
- [x] [Review][Patch] `disconnect()` swallows all exceptions silently without logging [ingestion/client.py:33-37] — fixed: added logger.debug with exc_info
- [x] [Review][Patch] Double-connect: `connect()` called twice leaks first provider — no guard for `self.w3 is not None` [ingestion/client.py:17] — fixed: early return if self.w3 is not None
- [x] [Review][Defer] Provider not cleaned up when `wait_for` times out (partial-connect leak) [ingestion/client.py:24] — deferred, PoC scope
- [x] [Review][Defer] `web3>=6.11` but 7.16.0 installed — import path already broke once, no upper bound pin [pyproject.toml] — deferred, pre-existing

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- web3 7.16.0 installed (newer than spec's 6.11 minimum); import path changed from `web3.providers.websocket` to `web3.providers` — fixed in client.py.

### Completion Notes List

- `ingestion/client.py` tạo mới với `EthereumClient` dataclass dùng web3.py 7.x API
- Import path thực tế: `from web3.providers import WebSocketProvider` (không phải `web3.providers.websocket`)
- `asyncio.wait_for(connect(), timeout=3.0)` wrap timeout + ConnectionRefusedError + OSError → `ConnectionError`
- `disconnect()` dùng try/except để swallow provider exceptions
- Context manager `__aenter__`/`__aexit__` hoạt động đúng
- 10 unit tests (mock WebSocketProvider bằng AsyncMock): tất cả pass
- 1 integration test (skipif port 8546 chưa mở): correctly skipped
- Full suite: 102 passed, 1 skipped — no regressions

### File List

- `ingestion/client.py` (NEW)
- `tests/unit/test_client.py` (NEW)
- `tests/integration/test_client_connect.py` (NEW)
- `pyproject.toml` (UPDATE — thêm `web3>=6.11` vào dependencies)
