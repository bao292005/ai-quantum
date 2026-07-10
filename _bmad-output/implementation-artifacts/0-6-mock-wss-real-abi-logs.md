---
baseline_commit: 0e04db60825409ad60bf9c50f73db6977cb733f6
type: build
---

# Story 0.6: Mock WSS — Real ABI-Encoded Logs

Status: done

## Story

As a **Data Engineer**,
I want **the mock WebSocket server (`tools/mock_wss`) to emit `logs` notifications as real ABI-encoded Ethereum logs (correct `topic0`, indexed topics, and non-indexed `data` layout) instead of the simplified 2-word placeholder**,
so that **the Track 1B decoders/`EventRouter` can decode mock-replayed events end-to-end, unblocking the realtime `--source=mock` path of the pipeline orchestrator (1E.1)**.

## Context — why this story exists

`tools/mock_wss/replay.py::build_raw_log` currently emits a **simplified** log:
`topics=[topic0_only]`, `data = word(amount0)+word(amount1)` (2 words). The Track 1B
decoders (`ingestion/decoders/`) expect **real ABI encoding**: Uniswap Swap `data`
is 5 words `(int256,int256,uint160,uint128,int24)`, Aave carries the asset
addresses in **indexed topics** (`topics[1..3]`), etc. Consequently the mock's
logs are undecodable by 1B (`abi_decode` size mismatch / `topics[1]` IndexError),
so the realtime mock path cannot feed the ring buffer. This story makes the mock
faithful so 1E.1 realtime works against it.

## Acceptance Criteria

1. **AC1 — Real topic0 per event_type:** `_EVENT_TOPIC0` maps all 7 normalized event types to the **real mainnet topic0** matching the Track 1B decoder constants:
   - swap `0xc42079..`, mint `0x7a5308..`, burn `0x0c396c..`
   - supply `0x2b6277..`, borrow `0xb3d084..` (real uint8 variant), withdraw `0x3115d1..`, liquidation `0xe413a3..`

2. **AC2 — Real ABI data + indexed topics per event:** `build_raw_log(row)` builds the log so a Track 1B decoder reads back the **same normalized values** the fixture row holds:
   - **Uniswap swap:** `topics=[SWAP, sender, recipient]`; `data=abi_encode(["int256","int256","uint160","uint128","int24"], [amount0, amount1, 0, 0, 0])`.
   - **Uniswap mint:** `topics=[MINT, owner, tickLower, tickUpper]`; `data=abi_encode(["address","uint128","uint256","uint256"], [ZERO, 0, amount0, amount1])`.
   - **Uniswap burn:** `topics=[BURN, owner, tickLower, tickUpper]`; `data=abi_encode(["uint128","uint256","uint256"], [0, amount0, amount1])`.
   - **Aave supply:** `topics=[SUPPLY, reserve=token0, onBehalfOf, referralCode]`; `data=abi_encode(["address","uint256"], [ZERO, amount0])`.
   - **Aave borrow:** `topics=[BORROW, reserve=token0, onBehalfOf, referralCode]`; `data=abi_encode(["address","uint256","uint256","uint256"], [ZERO, amount0, 0, 0])`.
   - **Aave withdraw:** `topics=[WITHDRAW, reserve=token0, user, to]`; `data=abi_encode(["uint256"], [amount0])`.
   - **Aave liquidation:** `topics=[LIQUIDATION, collateralAsset=token0, debtAsset=token1, user]`; `data=abi_encode(["uint256","uint256","address","bool"], [amount1, amount0, ZERO, False])` — note **debtToCover=amount1 first, then liquidatedCollateralAmount=amount0** so the decoder's `amount0=data[1]`, `amount1=data[0]` round-trips the fixture.

3. **AC3 — Round-trip correctness:** For every event type, `EventRouter.route(build_raw_log(row), block_ts).to_dict()` reproduces the fixture row's `protocol`, `event_type`, `token0`, `token1`, `amount0`, `amount1`, `pool_address`, `tx_hash`, `log_index` (given the row's pool is whitelisted). Uniswap `token0/token1` come from the whitelist (pool metadata); Aave from the log topics.

4. **AC4 — Whitelist covers fixture pools:** `ingestion/whitelist.yaml` includes the LUNA/FTX **Aave V2 Pool** `0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9` as `protocol: aave_v3` (router dispatches to `AaveV3Decoder`, which matches on the normalized V3 topic0 the mock emits). Rationale documented inline in the YAML. (Uniswap `0x88e6..5640` and Aave V3 `0x87870b..` already present.)

5. **AC5 — Negative amounts preserved:** Uniswap swap `amount0`/`amount1` may be negative (int256); the two's-complement helper is replaced by `eth_abi.encode(["int256",...])` which handles the sign. Round-trip preserves the exact signed decimal string.

6. **AC6 — Existing mock behavior preserved:** `MockWssServer` replay loop still works (per-row guard on malformed rows still catches `ValueError`); `build_raw_log` still raises on non-numeric amount; block-header emission, health snapshot, backpressure, and speed control are unchanged. All existing `tests/unit/test_mock_wss.py` tests pass (update only the assertions that hard-coded the 2-word `data` length / minimal row shape).

7. **AC7 — Tests:**
   - Update `test_build_raw_log_shape` for the real ABI shape (row now includes `protocol`, `token0`, `token1`).
   - New `tests/unit/test_mock_router_roundtrip.py`: build a synthetic normalized row per event type → `build_raw_log` → `EventRouter.route_validated(...)` → assert decoded dict equals the expected normalized values (schema-valid).
   - An integration-style check: take the first Uniswap row and one Aave row from a real fixture (`load_events`), pass through `build_raw_log` → router, assert decoded `amount0/amount1/token0/token1` match the fixture row.

## Tasks / Subtasks

- [x] **Task 1 — Real topic0 map** (AC1)
  - [x] Rewrite `_EVENT_TOPIC0` in `tools/mock_wss/replay.py` với 7 real topic0 (thêm mint/burn/withdraw; sửa supply/borrow khớp 1B).

- [x] **Task 2 — Rewrite build_raw_log with real ABI** (AC2, AC5)
  - [x] Per-event `eth_abi.encode` của `data`; build indexed `topics` (`_addr_topic` helper); tách `_encode_event`.
  - [x] Đọc `row["token0"]`, `row["token1"]` để đặt Aave asset topics.
  - [x] Giữ numeric hex fields + `address`/`transactionHash`/`removed`.
  - [x] Giữ raise `ValueError` cho amount phi số (AC6).

- [x] **Task 3 — Whitelist Aave V2 pool** (AC4)
  - [x] Thêm `0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9` (aave_v3) vào `ingestion/whitelist.yaml` kèm rationale.

- [x] **Task 4 — Tests** (AC6, AC7)
  - [x] Cập nhật `tests/unit/test_mock_wss.py::test_build_raw_log_shape`.
  - [x] Thêm `tests/unit/test_mock_router_roundtrip.py` (8 test).
  - [x] Full suite 238 passed — no regressions.

## Dev Notes

**Loại story:** `[BUILD]` — re-opens/extends Story 0.5. blockedBy: **Track 1B DONE** (decoders + router + whitelist — all `review`).

---

### 🔗 Previous Story Intelligence — Track 1B (bắt buộc đọc)

- Decoder constants (`ingestion/decoders/uniswap_v3.py`, `aave_v3.py`) — dùng CHÍNH XÁC các topic0 này (đã verify bằng `keccak`):
  - Uniswap: `SWAP_TOPIC/MINT_TOPIC/BURN_TOPIC` = `0xc42079../0x7a5308../0x0c396c..`
  - Aave: `SUPPLY 0x2b6277..`, **`BORROW 0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0`** (uint8 real mainnet — KHÔNG dùng `0xc6a898`), `WITHDRAW 0x3115d1..`, `LIQUIDATION 0xe413a3..`.
- **Cách decoder đọc** (phải encode khớp): Uniswap swap `data[0],data[1]`; mint `data[2],data[3]`; burn `data[1],data[2]`; token0/1 từ **pool_meta (whitelist)**. Aave supply/borrow `data[1]`, withdraw `data[0]` → amount0; `token0=topics[1]`; liquidation `amount0=data[1]` (liquidatedCollateral), `amount1=data[0]` (debtToCover), `token0=topics[1]`, `token1=topics[2]`.
- Router: `EventRouter.route(log, block_ts)` → `TickDataEvent | None` (unknown address → None). Consumer: `if e: ring_buffer.write(e.to_dict())`.
- `TickDataEvent.to_dict()` = dict 11-field khớp `tick_data.schema.json`.
- `eth_abi` bundled với web3 7.16.0: `from eth_abi import encode`.

### Round-trip amount/token mapping (fixture row → mock log → decoder → dict)

| event_type | topics (indexed) | data (abi_encode) | decoder reads → dict |
|---|---|---|---|
| swap | [SWAP, sender, recipient] | int256,int256,uint160,uint128,int24 = [a0,a1,0,0,0] | amount0=a0, amount1=a1; token0/1←whitelist |
| mint | [MINT, owner, tickLo, tickHi] | address,uint128,uint256,uint256 = [ZERO,0,a0,a1] | amount0=a0, amount1=a1 |
| burn | [BURN, owner, tickLo, tickHi] | uint128,uint256,uint256 = [0,a0,a1] | amount0=a0, amount1=a1 |
| supply | [SUPPLY, token0, onBehalfOf, refCode] | address,uint256 = [ZERO,a0] | amount0=a0, amount1="0", token0=topics[1] |
| borrow | [BORROW, token0, onBehalfOf, refCode] | address,uint256,uint256,uint256 = [ZERO,a0,0,0] | amount0=a0, amount1="0", token0=topics[1] |
| withdraw | [WITHDRAW, token0, user, to] | uint256 = [a0] | amount0=a0, amount1="0", token0=topics[1] |
| liquidation | [LIQUIDATION, token0, token1, user] | uint256,uint256,address,bool = [a1,a0,ZERO,False] | amount0=a0(=data[1]), amount1=a1(=data[0]), token0=topics[1], token1=topics[2] |

`a0=int(row["amount0"])`, `a1=int(row["amount1"])`. Uniswap token0/token1 do decoder lấy từ whitelist nên fixture row's token phải khớp whitelist (pool `0x88e6..` = USDC/WETH ✓).

### Implementation sketch (`build_raw_log`)

```python
from eth_abi import encode as abi_encode

ZERO = "0x0000000000000000000000000000000000000000"

_TOPIC0 = {
    "swap": "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67",
    "mint": "0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde",
    "burn": "0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c",
    "supply": "0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61",
    "borrow": "0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0",
    "withdraw": "0x3115d1449a7b732c986cba18244e897a450f61e1bb8d589cd2e69e6c8924f9f7",
    "liquidation": "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286",
}

def _addr_topic(addr: str) -> str:
    return "0x" + "00" * 12 + addr.lower().removeprefix("0x")

def build_raw_log(row: dict) -> dict:
    et = row["event_type"]
    a0, a1 = int(row["amount0"]), int(row["amount1"])   # raises ValueError (AC6)
    t0, t1 = row.get("token0", ZERO), row.get("token1", ZERO)
    topic0 = _TOPIC0.get(et, "0x" + "00" * 32)
    if et == "swap":
        topics = [topic0, _addr_topic(ZERO), _addr_topic(ZERO)]
        data = abi_encode(["int256","int256","uint160","uint128","int24"], [a0, a1, 0, 0, 0])
    elif et == "mint":
        topics = [topic0, _addr_topic(ZERO), "0x"+"00"*32, "0x"+"00"*32]
        data = abi_encode(["address","uint128","uint256","uint256"], [ZERO, 0, a0, a1])
    elif et == "burn":
        topics = [topic0, _addr_topic(ZERO), "0x"+"00"*32, "0x"+"00"*32]
        data = abi_encode(["uint128","uint256","uint256"], [0, a0, a1])
    elif et == "supply":
        topics = [topic0, _addr_topic(t0), _addr_topic(ZERO), "0x"+"00"*32]
        data = abi_encode(["address","uint256"], [ZERO, a0])
    elif et == "borrow":
        topics = [topic0, _addr_topic(t0), _addr_topic(ZERO), "0x"+"00"*32]
        data = abi_encode(["address","uint256","uint256","uint256"], [ZERO, a0, 0, 0])
    elif et == "withdraw":
        topics = [topic0, _addr_topic(t0), _addr_topic(ZERO), _addr_topic(ZERO)]
        data = abi_encode(["uint256"], [a0])
    elif et == "liquidation":
        topics = [topic0, _addr_topic(t0), _addr_topic(t1), _addr_topic(ZERO)]
        data = abi_encode(["uint256","uint256","address","bool"], [a1, a0, ZERO, False])
    else:
        topics = [topic0]
        data = abi_encode(["int256","int256"], [a0, a1])
    return {
        "address": row["pool_address"],
        "topics": topics,                       # hex strings (0x...) — router/decoder handle str & bytes
        "data": "0x" + data.hex(),
        "blockNumber": hex(int(row["block_number"])),
        "blockHash": _block_hash(int(row["block_number"])),
        "transactionHash": row["tx_hash"],
        "logIndex": hex(int(row["log_index"])),
        "removed": False,
    }
```

> Decoder `_topic_hex`/`_topic_to_addr` chấp nhận cả `str` (0x...) lẫn `bytes` → emit topics dạng hex string OK. `data` là hex string `0x...` → decoder `_to_data_bytes` xử lý.

### Guardrails

- Liquidation: **thứ tự data là [debtToCover=a1, liquidatedCollateral=a0, ...]** — dễ đảo. Round-trip test phải bắt lỗi này.
- Swap dùng `int256` (giữ dấu). Đừng dùng two's-complement thủ công (`_to_word`) nữa — `eth_abi` lo.
- KHÔNG đổi `build_block_header`, `iter_block_groups`, `load_events`, speed control, server loop.
- `_addr_topic` / `_to_word` cũ: `_to_word` có thể bỏ nếu không còn dùng (kiểm tra reference trước khi xoá).

### Project Conventions & Testing

- Python 3.11+; pytest, `asyncio_mode=auto`. Chạy: `python3 -m pytest tests/unit/test_mock_wss.py tests/unit/test_mock_router_roundtrip.py`.
- Console output bị hook lọc → redirect file + Read nếu cần traceback.
- `ruff check` trên CI (không cài local).

### References

- [Source: `tools/mock_wss/replay.py`] — `build_raw_log`/`_EVENT_TOPIC0`/`iter_block_groups` hiện tại.
- [Source: `ingestion/decoders/uniswap_v3.py`, `aave_v3.py`] — layout decoder phải khớp.
- [Source: `ingestion/router.py`, `ingestion/whitelist.yaml`] — dispatch + pool metadata.
- [Source: `fixtures/backtest/README.md`] — Aave V2 pool `0x7d2768..` (luna/ftx), Uniswap `0x88e6..`, amount semantics.
- [Source: project-memory directive 2026-07-09] — Aave V3-only decoder; V2 fixtures đi CSV (nhưng story này cho phép mock replay V2 rows như log Aave để realtime path decode được, coi V2 pool như aave_v3 alias trong whitelist).

---

### Review Findings

- [x] [Review][Patch] **HIGH:** `build_raw_log` giờ bọc `_encode_event`/`abi_encode` trong try/except → re-raise `ValueError` (khớp docstring) → server `_replay_loop` per-row guard skip được thay vì giết task. [tools/mock_wss/replay.py]
- [x] [Review][Defer] `build_raw_log` `int(amount)` từ chối amount thập phân "1.5" mà schema cho phép — fixtures là integer-wei nên không trigger; defer. [tools/mock_wss/replay.py]

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- RED: `test_mock_router_roundtrip.py` 8 failed (mock log không decode được).
- Bug tìm ra khi round-trip: mock emit `blockNumber`/`logIndex` dạng **hex string** (`"0x1"`, đúng JSON-RPC) nhưng decoder 1B dùng `int(log[...])` (giả định web3 đã parse sang int) → `ValueError: invalid literal '0x1'`. **Fix:** thêm `_to_int` helper trong `uniswap_v3.py` (xử lý cả int lẫn hex-string), dùng cho `block_number`/`log_index` ở cả 2 decoder. Decoder giờ robust cho raw JSON-RPC (mock) lẫn web3-parsed (realtime).
- GREEN: round-trip 8 passed; decoder 1B 20 passed (không hồi quy). Full suite 238 passed, 1 skipped.

### Completion Notes List

- `build_raw_log` viết lại: `_encode_event(event_type, a0, a1, t0, t1)` trả `(topics_tail, data)` dùng `eth_abi.encode` đúng layout ABI thật mỗi event; topic0 thật (khớp 1B, borrow `0xb3d084`). `_addr_topic` pad address→32-byte topic. Bỏ `_to_word`/`_UINT256_MASK` (mồ côi).
- Swap dùng `int256` (giữ dấu âm) — round-trip `-1000000000` OK. Liquidation data order `[debtToCover=a1, liquidatedCollateral=a0]` → decoder `amount0=data[1]=a0`, `amount1=data[0]=a1` khớp fixture.
- Whitelist thêm Aave V2 pool LUNA/FTX `0x7d2768..` (aave_v3 alias) — nếu không, log Aave từ fixture bị router drop.
- **Decoder hardening (`_to_int`)** — thay đổi nhỏ trong Track 1B files nhưng cần thiết & đúng: decoder giờ chạy được với cả log raw (mock/JSON-RPC hex) lẫn web3-parsed (int). 1B tests vẫn xanh.
- Round-trip verify cả 7 event type + 2 row thật từ luna fixture (uniswap + aave).

### File List

- `tools/mock_wss/replay.py` (UPDATE — build_raw_log + _encode_event + _EVENT_TOPIC0; remove _to_word/_UINT256_MASK)
- `ingestion/whitelist.yaml` (UPDATE — add Aave V2 pool)
- `ingestion/decoders/uniswap_v3.py` (UPDATE — add `_to_int`; use for block_number/log_index)
- `ingestion/decoders/aave_v3.py` (UPDATE — use `_to_int`)
- `tests/unit/test_mock_wss.py` (UPDATE — build_raw_log shape assertions)
- `tests/unit/test_mock_router_roundtrip.py` (NEW)

## Change Log

- 2026-07-09 — Story 0.6: mock WSS emits real ABI logs (round-trip decodable by Track 1B); hardened decoders to accept hex-string numeric fields; whitelisted Aave V2 pool; 8 round-trip tests; status → review. Unblocks 1E.1 realtime.
