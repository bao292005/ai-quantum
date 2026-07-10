---
baseline_commit: 0e04db60825409ad60bf9c50f73db6977cb733f6
type: build
---

# Story 1D.1: CSV Schema Mapping

Status: done

## Story

As a **Data Analyst**,
I want **a mapper that reads a backtest fixture CSV (`.csv` or `.csv.gz`) and converts each row into a normalized tick-data `dict` conforming to `contracts/tick_data.schema.json`**,
so that **historical replay (Track 1D) feeds the ring buffer and MPS engine through the exact same contract as the realtime WebSocket path (Track 1A/1B) — one schema, two sources**.

## Acceptance Criteria

1. **AC1 — Module tồn tại:** `ingestion/csv_loader.py` export hàm map một row và hàm iterate cả file (tên đề xuất: `map_csv_row`, `iter_csv_events`).

2. **AC2 — Row → schema-conformant dict:** `map_csv_row(raw)` nhận một `dict[str, str]` (từ `csv.DictReader`) và trả về `dict` với đúng 11 field của `tick_data.schema.json`, thứ tự/tên field khớp schema.

3. **AC3 — Type coercion đúng:** `block_number` và `log_index` được ép về `int`. **Tất cả field còn lại giữ nguyên `str`** — đặc biệt `amount0`/`amount1` **PHẢI giữ dạng chuỗi thập phân** (schema yêu cầu `string` để bảo toàn độ chính xác wei/int256; KHÔNG được cast sang `int`/`float`).

4. **AC4 — Schema validation:** Mỗi dict được validate bằng `jsonschema` với `contracts/tick_data.schema.json` (Draft 2020-12). Row hợp lệ → yield; row vi phạm schema (sai enum, sai pattern address/tx_hash, thiếu field...) → coi là lỗi (xem AC5).

5. **AC5 — Row lỗi không crash pipeline:** Row lỗi format (thiếu cột, `block_number` không phải số, validation fail...) được ghi vào `csv_errors.log` dưới dạng **1 dòng JSON** (chứa lý do + số dòng + nội dung row) rồi **skip**, iterate tiếp các row còn lại. Không raise ra ngoài, không dừng file.

6. **AC6 — Đọc gzip trong suốt:** `iter_csv_events(path)` mở được cả `.csv` và `.csv.gz` (dùng `gzip.open` khi đuôi là `.gz`) — khớp storage strategy của `fixtures/backtest/README.md`.

7. **AC7 — Fixture thật map sạch:** Chạy trên một mẫu đầu file `luna_2022_05_09.csv.gz` (≥ 50 row đầu, cả `uniswap_v3` và `aave_v2`), 100% row hợp lệ map thành công (0 dòng ghi vào `csv_errors.log`).

8. **AC8 — Unit tests:** `tests/unit/test_csv_loader.py` cover:
   - `map_csv_row` happy path cho 1 row Uniswap V3 swap và 1 row Aave (`aave_v2`) → dict khớp schema
   - Type coercion: `block_number`/`log_index` là `int`; `amount0`/`amount1` vẫn là `str` (kể cả giá trị âm như `-13739080501`)
   - Schema validation reject: enum sai, address sai pattern
   - Row lỗi (`block_number="abc"`, hoặc thiếu cột) → ghi `csv_errors.log`, không raise, iterate tiếp
   - `iter_csv_events` đọc được `.csv.gz` (dùng một file tạm gzip nhỏ trong test)
   - Round-trip: một mẫu row thật từ fixture → validate pass

## Tasks / Subtasks

- [x] **Task 1 — Implement row mapper** (AC1–AC4)
  - [x] Tạo `ingestion/csv_loader.py`
  - [x] `map_csv_row(raw: dict[str, str]) -> dict` — ép `block_number`/`log_index` sang `int`, giữ 9 field còn lại là `str`
  - [x] Load schema một lần (module-level lazy) từ `contracts/tick_data.schema.json`
  - [x] Validate dict bằng `jsonschema.validate`

- [x] **Task 2 — File iterator + error logging** (AC5, AC6, AC7)
  - [x] `iter_csv_events(path, *, error_log="csv_errors.log", validate=True) -> Iterator[dict]`
  - [x] Mở `.csv`/`.csv.gz` trong suốt (`gzip.open` cho `.gz`, text mode utf-8)
  - [x] Dùng `csv.DictReader` (file CÓ header row khớp 11 field)
  - [x] Bắt lỗi per-row → ghi 1 dòng JSON vào `error_log` (line number 1-based tính từ header) → `continue`

- [x] **Task 3 — Unit tests** (AC8)
  - [x] Tạo `tests/unit/test_csv_loader.py`
  - [x] Reuse `_event`-style helpers; tạo file `.csv.gz` tạm bằng `tmp_path` fixture của pytest

## Dev Notes

**Loại story:** `[BUILD]` — Track 1D (Historical CSV Ingestion), story đầu track.
**blockedBy:** Epic 0 Story 0.1 (`tick_data.schema.json` — DONE) + Story 0.4 (fixtures — DONE). **KHÔNG phụ thuộc Track 1B.**

---

### ⚠️ Quyết định thiết kế QUAN TRỌNG — output là `dict`, KHÔNG phải `TickDataEvent`

Epics mô tả "mỗi row → `TickDataEvent`". Tuy nhiên `TickDataEvent` là một dataclass **do Track 1B định nghĩa** (`ingestion/decoders/uniswap_v3.py`, story 1B.1) và **Track 1B hiện CHƯA implement** (`1B-*` đang `ready-for-dev`). Theo Parallelization Guide trong `epics.md`, **Track 1D độc lập với Track 1B** (chỉ phụ thuộc 0.1 + 0.4).

→ **1D.1 sản xuất `dict` khớp `tick_data.schema.json`** (đúng contract mà `core/ring_buffer.py` đã consume — ring buffer nhận `dict`, xem `RingBufferProtocol.write(event: dict)`). Điều này:
- Giữ Track 1D chạy song song, không bị chặn bởi 1B.
- Khớp chính xác contract downstream: ring buffer (1C) và Epic 2 GraphBuilder đều làm việc trên `dict` schema-conformant.
- Khi 1B hoàn thành, `TickDataEvent.to_dict()` cho ra **cùng một dict** này → hoàn toàn tương thích; nếu sau này cần object, thêm một adapter mỏng `TickDataEvent(**dict)` mà không phải sửa 1D.

**Không** import bất cứ thứ gì từ `ingestion/decoders/` hay `ingestion/router.py` (chưa tồn tại).

---

### CSV format thực tế (đã xác minh trên fixture)

- File **CÓ header row** ở dòng 1, khớp đúng 11 field schema:
  `block_number,block_timestamp,protocol,event_type,pool_address,token0,token1,amount0,amount1,tx_hash,log_index`
  → dùng `csv.DictReader` (không cần định nghĩa cột thủ công).
- Fixtures gzip: `luna_2022_05_09.csv.gz` (26,540 row), `ftx_2022_11_08.csv.gz` (35,109), `normal_2023_03_15.csv.gz` (6,899). [Source: `fixtures/backtest/README.md`]
- Mẫu row thật (Uniswap V3 swap, LUNA):
  `14724001,2022-05-06T14:15:06Z,uniswap_v3,swap,0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640,0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48,0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2,-13739080501,5130000000000000000,0xa343dacfff741a8773aa3b85b865c3ff98ed0b2b69d52e3aecd77a9877182d45,154`

### Field mapping table (CSV column → schema field)

| CSV column | schema field | Coercion | Ghi chú |
| --- | --- | --- | --- |
| `block_number` | `block_number` | `int(x)` | integer ≥ 0 |
| `block_timestamp` | `block_timestamp` | giữ `str` | ISO 8601 UTC, đã có hậu tố `Z` |
| `protocol` | `protocol` | giữ `str` | enum: `uniswap_v3` \| `aave_v3` \| **`aave_v2`** |
| `event_type` | `event_type` | giữ `str` | enum: swap/mint/burn/borrow/supply/withdraw/**liquidation** |
| `pool_address` | `pool_address` | giữ `str` | `^0x[0-9a-fA-F]{40}$` (CSV để lowercase) |
| `token0` | `token0` | giữ `str` | address |
| `token1` | `token1` | giữ `str` | Aave: zero-address `0x000...0` |
| `amount0` | `amount0` | **giữ `str`** | chuỗi thập phân, cho phép ÂM (signed int256 delta) |
| `amount1` | `amount1` | **giữ `str`** | chuỗi thập phân |
| `tx_hash` | `tx_hash` | giữ `str` | `^0x[0-9a-fA-F]{64}$` |
| `log_index` | `log_index` | `int(x)` | integer ≥ 0 |

**Guardrail #1 (dễ sai nhất):** KHÔNG cast `amount0`/`amount1` sang số. Schema `tick_data.schema.json` định nghĩa chúng là `string` với `maxLength: 80` để bảo toàn uint256/int256 (78 chữ số) — cast sang `int`/`float` sẽ mất chính xác hoặc phá schema validation.

**Guardrail #2:** Chỉ `block_number` và `log_index` là integer. Đừng ép các field khác.

**Guardrail #3:** `protocol` enum bao gồm `aave_v2` (fixtures LUNA/FTX dùng Aave V2 vì Aave V3 chưa deploy tới 2023-01-27). Đừng "sửa" thành `aave_v3`. [Source: `contracts/tick_data.schema.json` + `fixtures/backtest/README.md`]

---

### Implementation Pattern

```python
# ingestion/csv_loader.py
from __future__ import annotations

import csv
import gzip
import json
import logging
from collections.abc import Iterator
from pathlib import Path

import jsonschema

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "contracts" / "tick_data.schema.json"
_INT_FIELDS = ("block_number", "log_index")
_STR_FIELDS = (
    "block_timestamp", "protocol", "event_type", "pool_address",
    "token0", "token1", "amount0", "amount1", "tx_hash",
)
_schema: dict | None = None


class CsvRowError(ValueError):
    """Raised when a CSV row cannot be mapped to a valid tick-data dict."""


def _load_schema() -> dict:
    global _schema
    if _schema is None:
        with open(_SCHEMA_PATH) as f:
            _schema = json.load(f)
    return _schema


def map_csv_row(raw: dict[str, str], *, validate: bool = True) -> dict:
    """Map one CSV DictReader row to a tick_data.schema.json-conformant dict.

    Raises CsvRowError if a required column is missing, an int field is
    non-numeric, or (when validate=True) the row violates the schema.
    """
    try:
        event = {f: int(raw[f]) for f in _INT_FIELDS}
        for f in _STR_FIELDS:
            event[f] = raw[f]  # KeyError if column missing
    except KeyError as e:
        raise CsvRowError(f"missing column {e}") from e
    except (ValueError, TypeError) as e:
        raise CsvRowError(f"bad integer field: {e}") from e

    if validate:
        try:
            jsonschema.validate(event, _load_schema())
        except jsonschema.ValidationError as e:
            raise CsvRowError(f"schema violation: {e.message}") from e
    return event


def _open_text(path: str | Path):
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, mode="rt", encoding="utf-8", newline="")
    return open(path, mode="rt", encoding="utf-8", newline="")


def iter_csv_events(
    path: str | Path,
    *,
    error_log: str | Path = "csv_errors.log",
    validate: bool = True,
) -> Iterator[dict]:
    """Yield schema-conformant tick-data dicts from a fixture CSV(.gz).

    Malformed rows are written as one JSON line to `error_log` and skipped —
    the iterator never raises on a bad row.
    """
    with _open_text(path) as fh:
        reader = csv.DictReader(fh)
        err_fh = None
        try:
            for lineno, raw in enumerate(reader, start=2):  # line 1 = header
                try:
                    yield map_csv_row(raw, validate=validate)
                except CsvRowError as e:
                    if err_fh is None:
                        err_fh = open(error_log, "a", encoding="utf-8")
                    err_fh.write(json.dumps(
                        {"event": "csv_row_error", "line": lineno,
                         "reason": str(e), "row": raw}
                    ) + "\n")
                    logger.warning("csv_row_error line=%d: %s", lineno, e)
                    continue
        finally:
            if err_fh is not None:
                err_fh.close()
```

---

### Test Pattern

```python
# tests/unit/test_csv_loader.py
import gzip
import json

import pytest

from ingestion.csv_loader import CsvRowError, iter_csv_events, map_csv_row

_UNI_ROW = {
    "block_number": "14724001",
    "block_timestamp": "2022-05-06T14:15:06Z",
    "protocol": "uniswap_v3",
    "event_type": "swap",
    "pool_address": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
    "token0": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "token1": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    "amount0": "-13739080501",
    "amount1": "5130000000000000000",
    "tx_hash": "0xa343dacfff741a8773aa3b85b865c3ff98ed0b2b69d52e3aecd77a9877182d45",
    "log_index": "154",
}


def test_map_uniswap_row():
    e = map_csv_row(_UNI_ROW)
    assert e["block_number"] == 14724001 and isinstance(e["block_number"], int)
    assert e["log_index"] == 154 and isinstance(e["log_index"], int)
    # amounts MUST stay strings (precision + schema)
    assert e["amount0"] == "-13739080501" and isinstance(e["amount0"], str)
    assert e["amount1"] == "5130000000000000000" and isinstance(e["amount1"], str)
    assert set(e) == set(_UNI_ROW)  # exactly 11 fields


def test_map_aave_v2_row():
    row = {**_UNI_ROW, "protocol": "aave_v2", "event_type": "liquidation",
           "token1": "0x0000000000000000000000000000000000000000"}
    e = map_csv_row(row)
    assert e["protocol"] == "aave_v2"


def test_reject_bad_enum():
    with pytest.raises(CsvRowError):
        map_csv_row({**_UNI_ROW, "protocol": "sushiswap"})


def test_reject_bad_address():
    with pytest.raises(CsvRowError):
        map_csv_row({**_UNI_ROW, "pool_address": "0xNOTHEX"})


def test_reject_non_integer_block():
    with pytest.raises(CsvRowError):
        map_csv_row({**_UNI_ROW, "block_number": "abc"})


def test_bad_row_logged_not_raised(tmp_path):
    csv_path = tmp_path / "mini.csv"
    header = ",".join(_UNI_ROW.keys())
    good = ",".join(_UNI_ROW.values())
    bad = good.replace("14724001", "not_a_number", 1)
    csv_path.write_text(f"{header}\n{good}\n{bad}\n{good}\n")
    err_log = tmp_path / "csv_errors.log"

    events = list(iter_csv_events(csv_path, error_log=err_log))
    assert len(events) == 2  # 2 good rows, bad one skipped
    lines = err_log.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["line"] == 3


def test_gzip_transparent(tmp_path):
    gz = tmp_path / "mini.csv.gz"
    header = ",".join(_UNI_ROW.keys())
    good = ",".join(_UNI_ROW.values())
    with gzip.open(gz, "wt", encoding="utf-8") as f:
        f.write(f"{header}\n{good}\n")
    events = list(iter_csv_events(gz, error_log=tmp_path / "e.log"))
    assert len(events) == 1 and events[0]["block_number"] == 14724001
```

---

### File Structure After 1D.1

```
ingestion/
  __init__.py
  config.py
  client.py
  reconnect.py
  streams.py
  metrics.py
  csv_loader.py       ← NEW (1D.1) — map_csv_row + iter_csv_events
                         (1D.2 sẽ thêm async stream_csv; 1D.3 thêm ReplayDriver)
contracts/
  tick_data.schema.json  ← EXISTING (Epic 0)
tests/unit/
  test_csv_loader.py  ← NEW (1D.1)
```

### Track 1D roadmap (để tránh làm lấn sang story sau)

- **1D.1 (story này):** row → schema dict + validate + đọc file (sync) + error logging. **Chưa** cần async, **chưa** cần ordering theo timestamp, **chưa** cần pacing.
- **1D.2 CSV Streamer:** `async def stream_csv(path)` yield theo thứ tự timestamp, memory < 50MB — build TRÊN `iter_csv_events`.
- **1D.3 Backtest Replay Driver:** `ReplayDriver(rate="1x"|"100x"|"asap")` bơm vào ring buffer đúng nhịp thời gian.

Giữ scope 1D.1 gọn: KHÔNG implement async/ordering/pacing ở đây.

---

### Project Conventions & Testing

- Python 3.11+ (local anaconda 3.12); pytest, `asyncio_mode=auto` (nhưng 1D.1 là sync — không cần async test).
- Chạy test: `python3 -m pytest tests/unit/test_csv_loader.py`. Console output bị hook lọc → redirect ra file và Read nếu cần full traceback.
- Lint `ruff check` chạy trên CI (ruff KHÔNG cài local); tránh import thừa.
- Logging JSON qua stdout/stderr theo convention (AD Consistency). `csv_errors.log` ghi mỗi lỗi 1 dòng JSON.
- `jsonschema>=4.20.0` đã có trong `pyproject.toml` (không cần thêm dependency).
- Naming: snake_case cho file/function, PascalCase cho class. [Source: ARCHITECTURE-SPINE.md#Consistency-Conventions]

### References

- [Source: `_bmad-output/epics.md`#Story-1D.1-CSV-Schema-Mapping] — user story + AC gốc.
- [Source: `contracts/tick_data.schema.json`] — 11 field, enum, pattern, `amount*` là string maxLength 80, `protocol` gồm `aave_v2`.
- [Source: `fixtures/backtest/README.md`] — CSV có header 11 field, gzip storage, block/timestamp ranges, ghi chú Aave V2.
- [Source: `core/ring_buffer.py`] — `RingBufferProtocol.write(event: dict)`: downstream consume `dict`, khẳng định lựa chọn output dict.
- [Source: `_bmad-output/implementation-artifacts/1B-4-event-router-normalizer.md`] — `TickDataEvent`/`route_validated()` pattern (Track 1B, chưa build) → forward-compatibility note.
- [Source: ARCHITECTURE-SPINE.md#AD-4] — "Dữ liệu lịch sử (backtest) dùng CSV/BigQuery."

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- RED: `pytest tests/unit/test_csv_loader.py` → ImportError (module chưa tồn tại).
- GREEN: 8 passed sau khi implement.
- AC7: map full `luna_2022_05_09.csv.gz` → 26,540 row, `csv_errors.log` = 0 byte (0 lỗi).
- Regression: full suite 185 passed, 1 skipped (test_client_connect — mock WSS không chạy, không liên quan).

### Completion Notes List

- Tạo `ingestion/csv_loader.py`: `map_csv_row` (ép `block_number`/`log_index`→int, 9 field còn lại giữ str, `amount*` KHÔNG cast), lazy-load schema, `jsonschema.validate`.
- `iter_csv_events`: mở `.csv`/`.csv.gz` trong suốt, `csv.DictReader` (file có header), row lỗi → 1 dòng JSON vào `csv_errors.log` (line 1-based) rồi skip, không raise.
- `CsvRowError(ValueError)` cho lỗi map/validate một row.
- Output là `dict` khớp schema (không phải `TickDataEvent` — Track 1B chưa build), forward-compatible với `TickDataEvent.to_dict()`.
- ruff không cài local (CI chạy lint); không import thừa.

### File List

- `ingestion/csv_loader.py` (NEW)
- `tests/unit/test_csv_loader.py` (NEW)

## Change Log

- 2026-07-09 — Implemented Story 1D.1 CSV schema mapping; 8 unit tests; AC7 verified on real luna fixture; status → review.
