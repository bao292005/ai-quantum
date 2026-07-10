---
baseline_commit: 0e04db60825409ad60bf9c50f73db6977cb733f6
type: build
---

# Story 1E.2: Etherscan Reconciliation Tool

Status: review

## Story

As a **Data Analyst**,
I want **a `python -m tools.reconcile_etherscan` tool that samples a few blocks from a live ring buffer, re-fetches those blocks' events from Etherscan, compares them field-by-field, and writes a `reconcile_report.md` with the match rate (failing if < 99.5%)**,
so that **I have objective, on-chain evidence that the ingestion pipeline (Track 1A/1B/1C) captured events faithfully — no dropped/garbled logs**.

## Acceptance Criteria

1. **AC1 — Tool tồn tại:** `python -m tools.reconcile_etherscan` chạy được (module `tools/reconcile_etherscan.py`).

2. **AC2 — Lấy buffer từ realtime:** Tool nạp ring buffer bằng cách chạy ingestion realtime một khoảng (`--duration` giây, mặc định gợi ý 300s = 5 phút) qua `run_realtime` (1E.1) trên `--wss-url`, hoặc nhận nguồn buffer đã có. Sau đó `buffer.read_all()` cho danh sách event dict.

3. **AC3 — Sample N block:** Chọn ngẫu nhiên `--samples` block (mặc định 3) từ các `block_number` phân biệt có trong buffer (dùng seed `--seed` để tái lập). Nếu buffer có < N block phân biệt → dùng tất cả + cảnh báo.

4. **AC4 — Fetch on-chain:** Với mỗi block sample, gọi Etherscan V2 `getLogs` cho các contract trong whitelist (reuse `tools.extract_fixtures.etherscan_get_logs` + decoders `decode_univ3_swap`/`decode_aave_*`), `fromBlock=toBlock=block`, ra danh sách event dict chuẩn hoá **cùng schema** với buffer.

5. **AC5 — So khớp field-by-field:** Ghép event buffer ↔ on-chain theo khóa `(tx_hash, log_index)`; coi là "match" nếu trùng `event_type`, `pool_address`, `token0`, `token1`, `amount0`, `amount1`. Match rate = (số event buffer khớp) / (tổng event buffer trong các block sample).

6. **AC6 — Report:** Ghi `reconcile_report.md` (repo root hoặc `--out`): liệt kê 3 block sample, số event mỗi block (buffer vs on-chain), danh sách mismatch (nếu có), và match rate tổng.

7. **AC7 — Fail gate:** Exit code ≠ 0 nếu match rate < 99.5% (in rõ lý do). Exit 0 nếu ≥ 99.5%.

8. **AC8 — Core thuần + injectable:** Logic so khớp tách thành hàm thuần `reconcile(events, sample_blocks, fetch_block_events) -> ReconcileResult` với `fetch_block_events` **inject được** (mock trong test, Etherscan thật trong CLI). KHÔNG gọi mạng trong unit test.

9. **AC9 — Unit tests:** `tests/unit/test_reconcile_etherscan.py` cover (dùng fake fetcher):
   - match 100% (buffer == on-chain) → ok, exit 0
   - mismatch amount → match rate giảm, report liệt kê mismatch
   - on-chain thiếu 1 event (dropped) → rate < 100%
   - rate < 99.5% → `ok=False`
   - report markdown chứa 3 block + rate

## Tasks / Subtasks

- [x] **Task 1 — Core reconcile (thuần, injectable)** (AC5, AC7, AC8)
  - [x] `tools/reconcile_etherscan.py`: `reconcile(events, sample, fetch_block_events) -> ReconcileResult`.
  - [x] Ghép theo `(tx_hash, log_index)`; so 6 field; `ok = rate >= 0.995`.

- [x] **Task 2 — Sampling + report** (AC3, AC6)
  - [x] `sample_blocks(events, n, seed)`; `render_report(...) -> str` (blocks + per-block counts + mismatches + rate + PASS/FAIL).

- [x] **Task 3 — Etherscan fetch adapter** (AC4)
  - [x] `make_etherscan_fetcher(whitelist, router, api_key)`: reuse `extract_fixtures.etherscan_get_logs` + **EventRouter 1B** để normalize (per-pool token đúng). Topics từ decoder constants.

- [x] **Task 4 — CLI** (AC1, AC2, AC7)
  - [x] argparse `--wss-url --duration --samples --seed --whitelist --out`; `_fill_buffer` qua `run_realtime` bounded bằng stop+sleep; ghi report; `SystemExit(0/1)`.

- [x] **Task 5 — Unit tests** (AC9)
  - [x] `tests/unit/test_reconcile_etherscan.py` (8 test, fake fetcher, không mạng).

## Dev Notes

**Loại story:** `[BUILD]` — Track 1E. blockedBy: **1E.1** (run_realtime + buffer), **1B** (router/decoders/whitelist), **1C** (buffer). Reuse `tools/extract_fixtures.py` (Etherscan client).

---

### 🔗 Reuse — KHÔNG viết lại (chống reinvention)

- **`tools/extract_fixtures.py`** đã có: `etherscan_get_logs(from_block,to_block,address,topic0,api_key)` (V2 API, rate-limit `_throttle` 0.5s, retry 5×, pagination split, xử lý "No records"/"rate limit"); decoders `decode_univ3_swap`, `decode_aave_borrow/supply/liquidation(version=)`; `_load_env_file`/`_get_api_key`; topic0 constants; `UNIV3_USDC_WETH`/`AAVE_V2_POOL`/`AAVE_V3_POOL`. **Import và dùng lại** — đừng viết client Etherscan mới.
- **`ingestion/pipeline.py::run_realtime(buffer, router, wss_url, stop)`** (1E.1) — nạp buffer. Bound thời gian bằng `stop` set sau `--duration` (dùng `asyncio.create_task` + `asyncio.sleep(duration)` rồi `stop.set()`, giống integration test 1E.1).
- **`ingestion/whitelist.py::ContractWhitelist.from_yaml` + `.addresses()`** — danh sách contract để fetch.
- **`core/ring_buffer.py::DequeRingBuffer`** — buffer; `read_all()` cho list dict.
- **Config:** `IngestionConfig.etherscan_api_key` có sẵn (`ingestion/config.py`) — hoặc dùng `extract_fixtures._get_api_key()`.

### ⚠️ Quyết định thiết kế

1. **Buffer ở process khác không truy cập được (NFR4: no disk write realtime).** → Tool **tự chạy ingestion** một khoảng `--duration` (reuse `run_realtime`) để có buffer riêng, rồi reconcile. Đây là cách khả thi cho một CLI độc lập. (Không dump buffer ra đĩa.)
2. **`fetch_block_events` PHẢI injectable** (AC8) — unit test truyền fake fetcher, KHÔNG gọi Etherscan thật (không mạng, không cần API key, tất định). CLI truyền adapter thật.
3. **So khớp theo `(tx_hash, log_index)`** — khóa duy nhất một log on-chain. Chỉ so 6 field nội dung (event_type, pool_address, token0, token1, amount0, amount1); KHÔNG so block_timestamp (buffer stamp từ newHeads, Etherscan từ `timeStamp` — có thể lệch cách format nhưng cùng giá trị; để tránh false-mismatch, bỏ qua timestamp trong so khớp, hoặc so bằng giá trị epoch).
4. **Topic0 V2 vs V3:** `extract_fixtures` fetch Aave bằng topic0 **đúng theo version block** (V2 cho block LUNA/FTX, V3 cho block hiện tại). Realtime buffer trên mainnet hiện tại = uniswap_v3 + aave_v3 → adapter fetch dùng V3 topics + uniswap swap topic. (Reconcile realtime = mainnet hiện tại, không phải LUNA/FTX.)
5. **Match rate denominator = event buffer trong block sample** (không phải on-chain), vì mục tiêu là "buffer có bỏ sót/sai so với chain không". On-chain thừa event mà buffer thiếu → tính là buffer miss (giảm rate). AC7 gate 99.5%.

### Implementation Pattern

```python
# tools/reconcile_etherscan.py
from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

_COMPARE_FIELDS = ("event_type", "pool_address", "token0", "token1", "amount0", "amount1")


@dataclass
class ReconcileResult:
    match_rate: float
    ok: bool
    total: int
    matched: int
    mismatches: list[dict] = field(default_factory=list)
    report_md: str = ""


def _key(e: dict) -> tuple:
    return (str(e["tx_hash"]).lower(), int(e["log_index"]))


def _norm(e: dict) -> tuple:
    return tuple(str(e[f]).lower() for f in _COMPARE_FIELDS)


def sample_blocks(events: list[dict], n: int, seed: int | None = None) -> list[int]:
    blocks = sorted({e["block_number"] for e in events})
    rng = random.Random(seed)
    return sorted(rng.sample(blocks, min(n, len(blocks))))


def reconcile(
    events: list[dict],
    sample: list[int],
    fetch_block_events: Callable[[int], list[dict]],
) -> ReconcileResult:
    sample_set = set(sample)
    buf = [e for e in events if e["block_number"] in sample_set]
    onchain: dict[tuple, dict] = {}
    for b in sample:
        for oe in fetch_block_events(b):
            onchain[_key(oe)] = oe

    matched, mismatches = 0, []
    for e in buf:
        oe = onchain.get(_key(e))
        if oe is not None and _norm(oe) == _norm(e):
            matched += 1
        else:
            mismatches.append({"key": _key(e), "buffer": _norm(e),
                               "onchain": _norm(oe) if oe else None})
    total = len(buf)
    rate = 1.0 if total == 0 else matched / total
    return ReconcileResult(
        match_rate=rate, ok=(rate >= 0.995), total=total, matched=matched,
        mismatches=mismatches,
        report_md=render_report(sample, buf, onchain, matched, total, rate, mismatches),
    )
```

```python
# CLI sketch
async def _fill_buffer(wss_url, whitelist_path, duration) -> DequeRingBuffer:
    from ingestion.pipeline import run_realtime
    from ingestion.router import EventRouter
    buf = DequeRingBuffer(capacity=100_000)  # large: keep the whole window
    router = EventRouter.from_yaml(whitelist_path)
    stop = asyncio.Event()
    task = asyncio.create_task(run_realtime(buf, router, wss_url, stop))
    await asyncio.sleep(duration)
    stop.set()
    await asyncio.wait_for(task, timeout=5)
    return buf
```

> Capacity: mặc định 1000 của DequeRingBuffer sẽ evict — với reconcile cần giữ cả cửa sổ, dùng capacity lớn (vd 100k) để không mất event của block sample. Ghi chú rõ.

### Test Pattern

```python
# tests/unit/test_reconcile_etherscan.py
from tools.reconcile_etherscan import reconcile, sample_blocks

def _ev(block, li, amount0="100", et="swap", tx=None):
    return {"block_number": block, "log_index": li, "tx_hash": tx or f"0x{li:064x}",
            "event_type": et, "pool_address": "0x" + "aa"*20,
            "token0": "0x"+"bb"*20, "token1": "0x"+"cc"*20,
            "amount0": amount0, "amount1": "0", "block_timestamp": "2023-10-24T12:00:00Z",
            "protocol": "uniswap_v3"}

def test_match_100():
    evs = [_ev(10, i) for i in range(5)]
    r = reconcile(evs, [10], fetch_block_events=lambda b: list(evs))
    assert r.match_rate == 1.0 and r.ok and r.total == 5

def test_amount_mismatch():
    evs = [_ev(10, i) for i in range(4)]
    onchain = [_ev(10, i, amount0=("999" if i == 0 else "100")) for i in range(4)]
    r = reconcile(evs, [10], fetch_block_events=lambda b: onchain)
    assert r.matched == 3 and r.match_rate == 0.75 and not r.ok and r.mismatches

def test_dropped_event():
    evs = [_ev(10, i) for i in range(4)]
    onchain = evs[:3]  # buffer has an extra event not on-chain
    r = reconcile(evs, [10], fetch_block_events=lambda b: onchain)
    assert r.matched == 3 and not r.ok

def test_gate_995():
    evs = [_ev(10, i) for i in range(1000)]
    onchain = [_ev(10, i, amount0=("999" if i < 6 else "100")) for i in range(1000)]
    r = reconcile(evs, [10], fetch_block_events=lambda b: onchain)
    assert r.match_rate < 0.995 and not r.ok  # 994/1000

def test_report_lists_blocks():
    evs = [_ev(b, 0) for b in (10, 20, 30)]
    r = reconcile(evs, [10, 20, 30], fetch_block_events=lambda b: [_ev(b, 0)])
    for b in (10, 20, 30):
        assert str(b) in r.report_md
```

### File Structure After 1E.2

```
tools/
  reconcile_etherscan.py   ← NEW (core reconcile + fetch adapter + CLI __main__)
  extract_fixtures.py      ← EXISTING (reuse Etherscan client + decoders)
tests/unit/
  test_reconcile_etherscan.py  ← NEW
```

### Project Conventions & Testing

- Python 3.11+; pytest. Unit test KHÔNG chạm mạng (fake fetcher). Chạy: `python3 -m pytest tests/unit/test_reconcile_etherscan.py`.
- Console output bị hook lọc → redirect file + Read nếu cần traceback.
- `requests` đã dùng trong `extract_fixtures.py` — nếu chưa khai báo trong pyproject dependencies thì thêm `"requests>=2.31"`. (Kiểm tra: `grep requests pyproject.toml`.)
- Logging JSON qua stdout theo convention; report là markdown.
- ruff trên CI.

### References

- [Source: `_bmad-output/epics.md`#Story-1E.2] — sample 3 block + Etherscan + reconcile_report.md, fail < 99.5%.
- [Source: `tools/extract_fixtures.py`] — `etherscan_get_logs` + decoders + `_get_api_key` (reuse).
- [Source: `ingestion/pipeline.py` run_realtime] — nạp buffer realtime bounded.
- [Source: `ingestion/whitelist.py`] — contract addresses.
- [Source: `core/ring_buffer.py`] — buffer read_all; capacity note.
- [Source: `fixtures/backtest/README.md`] — pool addresses, Aave V2/V3 topic note.
- [Source: `ingestion/config.py`] — `IngestionConfig.etherscan_api_key`.

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- RED: `pytest tests/unit/test_reconcile_etherscan.py` → ImportError.
- GREEN: 8 passed. Full suite 252 passed, 1 skipped.
- CLI import + `--help` verified (fetcher imports lazy → không chạm mạng khi import/test).

### Completion Notes List

- Core thuần `reconcile(events, sample, fetch_block_events)` + `sample_blocks` (seeded) + `render_report` (markdown: blocks, per-block buffer/on-chain counts, mismatches, rate, PASS/FAIL). Gate `_GATE=0.995`.
- Match theo `(tx_hash, log_index)`; so 6 field nội dung (event_type/pool_address/token0/token1/amount0/amount1); **bỏ qua block_timestamp** (tránh false-mismatch).
- `make_etherscan_fetcher`: **reuse** `extract_fixtures.etherscan_get_logs` (HTTP client) + **EventRouter 1B** để normalize raw log (per-pool token đúng qua whitelist) — không viết lại decoder. Topics từ decoder constants (uniswap swap/mint/burn + aave supply/borrow/withdraw/liquidation).
- CLI `_fill_buffer`: `run_realtime` (1E.1) trong `--duration` giây, capacity 100k (giữ cả cửa sổ, không evict block sample), rồi reconcile; exit 1 nếu rate < 99.5%.
- Thêm `requests>=2.31` vào pyproject (đã cài 2.32.2, trước đó thiếu khai báo).
- **Không unit-test phần mạng** (AC8): fetcher inject được → 8 test dùng fake fetcher, tất định, không API key.
- ruff không cài local (CI lint).

### File List

- `tools/reconcile_etherscan.py` (NEW)
- `tests/unit/test_reconcile_etherscan.py` (NEW)
- `pyproject.toml` (UPDATE — add requests>=2.31)

## Change Log

- 2026-07-09 — Story 1E.2 Etherscan reconciliation tool (pure core + injectable fetcher + CLI reusing extract_fixtures client & 1B router); 8 tests; status → review.
