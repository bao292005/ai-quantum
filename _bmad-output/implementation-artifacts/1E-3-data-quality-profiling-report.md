---
baseline_commit: 0e04db60825409ad60bf9c50f73db6977cb733f6
type: build
---

# Story 1E.3: Data Quality Profiling Report

Status: review

## Story

As a **Data Analyst**,
I want **a profiling tool that turns a window of ring-buffer events into a self-contained HTML report — event counts per protocol/type, block drop rate, per-protocol breakdown, and a timestamp-gap histogram flagging any gap > 30s**,
so that **the team can objectively assess ingestion data quality after a run**.

## Acceptance Criteria

1. **AC1 — Tool tồn tại:** `python -m tools.profile_quality` chạy được (module `tools/profile_quality.py`).

2. **AC2 — Core thuần `profile(events) -> QualityProfile`** tính (không I/O, testable):
   - `total_events`, `per_protocol` (dict count), `per_event_type` (dict count)
   - `n_blocks` (số block phân biệt có event), `block_range` (min, max)
   - `block_drop_rate` (xem AC5)
   - `timestamp_gaps`: list `(block_a, block_b, gap_seconds)` giữa các block phân biệt liên tiếp
   - `gaps_over_30s`: tập con `timestamp_gaps` có `gap_seconds > 30`

3. **AC3 — HTML report 4 "chart":** `render_html(profile) -> str` xuất HTML self-contained với 4 phần trực quan: (1) event count per protocol, (2) event count per event_type, (3) block coverage / drop rate, (4) timestamp-gap histogram. Dùng matplotlib nhúng PNG base64 (self-contained, không cần file phụ). Nếu matplotlib không import được → fallback bảng HTML (không crash).

4. **AC4 — Flag gap > 30s:** Report nêu rõ (highlighted) mọi gap timestamp > 30s (block_a→block_b, số giây). Nếu không có gap nào > 30s → ghi "no gaps > 30s".

5. **AC5 — Block drop rate:** Nếu truyền `blocks_seen` (dãy block_number từ newHeads) → `drop_rate = 1 - |distinct(blocks_seen)| / (max-min+1)`. Nếu không → suy từ coverage event: `1 - n_blocks_with_events / (max-min+1)` (ghi chú caveat: block không có event whitelisted ≠ dropped).

6. **AC6 — CLI:** argparse `--source {mock,csv}`, `--duration`/`--file`, `--wss-url`, `--whitelist`, `--out` (mặc định `data_quality_report.html`). `mock` nạp buffer qua `run_realtime` (1E.1) bounded; `csv` đọc fixture qua `iter_csv_events` (1D). Ghi HTML ra `--out`.

7. **AC7 — Unit tests:** `tests/unit/test_profile_quality.py` (không mạng, không cần matplotlib cho phần assert chính):
   - counts per protocol/type đúng
   - timestamp gaps + `gaps_over_30s` phát hiện gap 45s, bỏ qua gap 12s
   - block_drop_rate với `blocks_seen` (có block thiếu) và không có
   - `render_html(profile, charts=False)` trả HTML chứa các section + flag gap
   - `render_html(profile)` (charts=True) chạy không crash, chứa `data:image/png;base64`

## Tasks / Subtasks

- [x] **Task 1 — Core `profile()`** (AC2, AC4, AC5)
  - [x] `tools/profile_quality.py`: `@dataclass QualityProfile`; `profile(events, *, blocks_seen=None)`.
  - [x] Counts (Counter); distinct blocks + timestamp per block; gaps giữa block liên tiếp; gaps_over_30s.

- [x] **Task 2 — `render_html`** (AC3, AC4)
  - [x] Summary + 4 matplotlib charts base64 PNG (guarded try/except → fallback table). Flag gaps>30s highlighted.

- [x] **Task 3 — CLI** (AC1, AC6)
  - [x] argparse; `--source mock` → `run_realtime` bounded; `--source csv` → `iter_csv_events`/`resolve_scenario_file`; ghi `--out`.

- [x] **Task 4 — Unit tests** (AC7)
  - [x] `tests/unit/test_profile_quality.py` (8 test).

## Dev Notes

**Loại story:** `[BUILD]` — Track 1E, story cuối. blockedBy: 1E.1 (buffer/run_realtime), 1D (iter_csv_events), 1C (buffer).

### ⚠️ Quyết định thiết kế — module testable thay cho notebook

Epics ghi `notebooks/profile.ipynb`. Nhưng: **jupyter KHÔNG cài**, notebook không unit-test được, và convention project là module `.py` testable. → Làm **`tools/profile_quality.py`** (core thuần `profile()` + `render_html()` xuất HTML self-contained với 4 chart matplotlib nhúng base64). Đáp ứng đúng ý AC (report trực quan + 4 chart + flag gap>30s) mà vẫn testable. Notebook wrapper (nếu cần sau) chỉ việc `from tools.profile_quality import profile, render_html`.
`ponytail:` charts = matplotlib PNG base64 (không cần jupyter/plotly). Upgrade lên notebook/interactive khi cần.

### 🔗 Reuse
- `ingestion/pipeline.py::run_realtime` (nạp buffer realtime bounded, capacity lớn).
- `ingestion/csv_loader.py::iter_csv_events` + `tools.mock_wss.replay.resolve_scenario_file` (nguồn csv).
- `core/ring_buffer.py::DequeRingBuffer.read_all()`.
- matplotlib 3.8.2, numpy 1.26.3 (đã cài).

### Implementation Pattern

```python
# tools/profile_quality.py
from __future__ import annotations
import base64, io
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class QualityProfile:
    total_events: int
    per_protocol: dict[str, int]
    per_event_type: dict[str, int]
    n_blocks: int
    block_range: tuple[int, int]
    block_drop_rate: float
    timestamp_gaps: list[tuple[int, int, float]] = field(default_factory=list)
    gaps_over_30s: list[tuple[int, int, float]] = field(default_factory=list)

def profile(events: list[dict], *, blocks_seen: list[int] | None = None) -> QualityProfile:
    if not events:
        return QualityProfile(0, {}, {}, 0, (0, 0), 0.0)
    per_proto = Counter(e["protocol"] for e in events)
    per_type = Counter(e["event_type"] for e in events)
    # first timestamp per distinct block, in block order
    ts_by_block: dict[int, str] = {}
    for e in events:
        ts_by_block.setdefault(e["block_number"], e["block_timestamp"])
    blocks = sorted(ts_by_block)
    lo, hi = blocks[0], blocks[-1]
    span = hi - lo + 1
    if blocks_seen:
        drop = 1 - len(set(blocks_seen)) / span
    else:
        drop = 1 - len(blocks) / span
    gaps = []
    for a, b in zip(blocks, blocks[1:]):
        ga = (datetime.fromisoformat(ts_by_block[b]) - datetime.fromisoformat(ts_by_block[a])).total_seconds()
        gaps.append((a, b, ga))
    over = [g for g in gaps if g[2] > 30]
    return QualityProfile(len(events), dict(per_proto), dict(per_type), len(blocks),
                          (lo, hi), max(0.0, drop), gaps, over)

def _bar_png(labels, values, title) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.bar(labels, values); ax.set_title(title); fig.tight_layout()
    buf = io.BytesIO(); fig.savefig(buf, format="png"); plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def render_html(p: QualityProfile, *, charts: bool = True) -> str:
    # summary tables + (optional) 4 charts base64 + gaps>30s flag.
    # guard matplotlib: try _bar_png(...) except Exception -> skip charts.
    ...
```

### CLI sketch

```python
# --source mock: reuse _fill_buffer pattern (run_realtime bounded)
# --source csv:  events = list(iter_csv_events(resolve_scenario_file(scenario) or --file))
# report = render_html(profile(events)); Path(out).write_text(report)
```

### Test Pattern

```python
# tests/unit/test_profile_quality.py
from tools.profile_quality import profile, render_html

def _ev(block, ts, proto="uniswap_v3", et="swap"):
    return {"block_number": block, "block_timestamp": ts, "protocol": proto,
            "event_type": et, "amount0": "1", "amount1": "0"}

def test_counts():
    evs = [_ev(1,"2022-05-06T14:00:00Z"), _ev(1,"2022-05-06T14:00:00Z", et="mint"),
           _ev(2,"2022-05-06T14:00:12Z", proto="aave_v3", et="borrow")]
    p = profile(evs)
    assert p.total_events == 3
    assert p.per_protocol == {"uniswap_v3": 2, "aave_v3": 1}
    assert p.per_event_type["swap"] == 1 and p.per_event_type["borrow"] == 1

def test_gap_over_30():
    evs = [_ev(1,"2022-05-06T14:00:00Z"), _ev(2,"2022-05-06T14:00:12Z"),
           _ev(3,"2022-05-06T14:00:57Z")]  # 12s then 45s
    p = profile(evs)
    assert len(p.gaps_over_30s) == 1
    assert p.gaps_over_30s[0][:2] == (2, 3)
    assert p.gaps_over_30s[0][2] == 45.0

def test_drop_rate_with_blocks_seen():
    evs = [_ev(10,"2022-05-06T14:00:00Z"), _ev(12,"2022-05-06T14:00:24Z")]
    p = profile(evs, blocks_seen=[10, 11, 12])   # all seen -> span 3
    assert p.block_drop_rate == 0.0
    p2 = profile(evs, blocks_seen=[10, 12])       # 11 missing -> 1/3
    assert round(p2.block_drop_rate, 3) == round(1/3, 3)

def test_render_html_tables():
    p = profile([_ev(1,"2022-05-06T14:00:00Z")])
    html = render_html(p, charts=False)
    assert "<html" in html.lower() and "uniswap_v3" in html
    assert "gap" in html.lower()

def test_render_html_charts():
    evs = [_ev(1,"2022-05-06T14:00:00Z"), _ev(2,"2022-05-06T14:00:57Z")]
    html = render_html(profile(evs))  # charts=True
    assert "data:image/png;base64" in html
```

### File Structure After 1E.3

```
tools/profile_quality.py          ← NEW (profile + render_html + CLI)
tests/unit/test_profile_quality.py ← NEW
```

### Project Conventions & Testing

- Python 3.11+; pytest. Unit test KHÔNG chạm mạng. `matplotlib.use("Agg")` (headless). Chạy: `python3 -m pytest tests/unit/test_profile_quality.py`.
- Console output bị hook lọc → redirect file + Read.
- matplotlib đã cài; nếu thêm khai báo pyproject thì `"matplotlib>=3.8"` (optional-dependency `dev` hoặc main — matplotlib chỉ dùng cho report, có thể để optional). Kiểm tra trước.
- ruff trên CI.

### References
- [Source: `_bmad-output/epics.md`#Story-1E.3] — 4 chart, drop rate, timestamp gap histogram, flag gap>30s.
- [Source: `ingestion/pipeline.py` run_realtime, `csv_loader.py` iter_csv_events] — nguồn buffer.
- [Source: `core/ring_buffer.py`] — read_all.

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story workflow)

### Debug Log References

- RED: `pytest tests/unit/test_profile_quality.py` → ImportError.
- GREEN (sau 1 fix test): test flag-gap ban đầu assert "45" nhưng gap 14:00:00→14:00:57 = **57s** → sửa assert "57s". 8 passed.
- Full suite 260 passed, 1 skipped.

### Completion Notes List

- **Quyết định:** thay notebook (jupyter không cài, không testable) bằng module testable `tools/profile_quality.py` — core thuần `profile()` + `render_html()`. Notebook wrapper có thể import lại nếu cần.
- `profile(events, *, blocks_seen=None)`: counts per protocol/type (Counter), distinct blocks + timestamp/block, timestamp gaps giữa block liên tiếp, `gaps_over_30s`. `block_drop_rate`: từ `blocks_seen` nếu có, else từ coverage event (có ghi caveat).
- `render_html(p, charts=True)`: summary + 4 chart matplotlib base64 PNG (`Agg` headless) trong try/except → fallback bảng nếu matplotlib lỗi; flag gaps>30s highlighted (đỏ), "no gaps > 30s ✓" nếu sạch. HTML-escape input.
- CLI `--source csv|mock`: csv → `iter_csv_events` (1D); mock → `run_realtime` (1E.1) bounded. Ghi `--out` (mặc định `data_quality_report.html`).
- Thêm `matplotlib>=3.8` vào `[dev]` optional-deps (render degrade được nếu thiếu).
- Unit test không chạm mạng; chart test dùng matplotlib (đã cài 3.8.2).
- ruff không cài local (CI lint).

### File List

- `tools/profile_quality.py` (NEW)
- `tests/unit/test_profile_quality.py` (NEW)
- `pyproject.toml` (UPDATE — matplotlib>=3.8 in [dev])

## Change Log

- 2026-07-09 — Story 1E.3 data-quality profiler (pure profile() + HTML report w/ 4 charts + gap>30s flag); 8 tests; notebook→testable module deviation; status → review. Closes Track 1E.
