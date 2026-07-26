---
baseline_commit: ae1732c
type: research
---

# Story 2R.1: Node Feature Catalog & Sourcing

Status: review

## Story

As a **Kỹ sư AI**,
I want **một catalog chính xác cho từng node feature (công thức tính, nguồn dữ liệu, đơn vị, range kỳ vọng, chính sách khi thiếu)**,
so that **Story 2B.2 (Node Feature Tensor) có spec rõ ràng để implement thay vì đoán, và bộ feature khớp đúng với contract `graph_snapshot.schema.json` đã khoá**.

## Acceptance Criteria

1. **AC1 — Reconcile bộ feature (QUAN TRỌNG NHẤT):** Xác định bộ feature CANONICAL. Hiện có **mâu thuẫn** phải giải quyết:
   - `contracts/graph_snapshot.schema.json` (Story 0.2, contract ĐÃ KHOÁ) định nghĩa 5 feature: `tvl_usd`, `volume_24h_usd`, `price_usd`, `volatility`, `connectivity`.
   - `epics.md` (2R.1/2B.2) đề xuất 5 feature khác: `tvl`, `utilization`, `price_delta`, `volatility`, `borrow_rate`.
   - `research/feature_catalog.md` PHẢI nêu rõ chốt dùng bộ nào, ánh xạ tên cũ↔mới, và nếu chọn bộ khác schema 0.2 thì ghi rõ đây là **breaking change** cần bump `$id` schema (feed lại 0.2).

2. **AC2 — Catalog đầy đủ mỗi feature:** `research/feature_catalog.md` có 1 bảng, mỗi feature 1 dòng với các cột: `Feature`, `Công thức / định nghĩa`, `Input event/field (từ schema 0.1)`, `Đơn vị`, `Range kỳ vọng`, `Missing-data policy`.

3. **AC3 — Nguồn dữ liệu:** Chỉ rõ feature nào tính được **trực tiếp từ schema 0.1** (`tick_data.schema.json`: block_number, block_timestamp, protocol, event_type, pool_address, token0/1, amount0/1, tx_hash, log_index), feature nào **cần nguồn phụ** (VD price_usd cần oracle/off-chain, tvl cần state snapshot).

4. **AC4 — Missing-data & normalization hint:** Mỗi feature có chính sách khi thiếu (VD → 0, → last-known, → NaN-rồi-2B.2-thay-0). Nêu range kỳ vọng để Story 2B.3 (normalization) dùng chọn minmax/zscore.

## Tasks / Subtasks

- [x] **Task 1 — Đối chiếu 2 bộ feature** (AC1)
  - [x] Liệt kê 5 feature schema 0.2 vs 5 feature epics
  - [x] Quyết định bộ canonical; nếu lệch schema → ghi khuyến nghị bump `$id` + feed lại Story 0.2
- [x] **Task 2 — Định nghĩa công thức từng feature** (AC2, AC3)
  - [x] Với mỗi feature: công thức, input field từ schema 0.1, đơn vị, range
  - [x] Đánh dấu "derivable từ 0.1" hay "cần nguồn phụ"
- [x] **Task 3 — Missing-data policy + range** (AC4)
  - [x] Chính sách thiếu cho từng feature + range kỳ vọng (hint cho 2B.3)
- [x] **Task 4 — Viết `research/feature_catalog.md`** (AC1-AC4)
  - [x] Bảng catalog + mục `## Decision` (bộ feature canonical + có bump schema hay không)

## Dev Notes

**Loại story:** `[RESEARCH]` P0 — output là document quyết định, KHÔNG code. **Chặn Story 2B.2** (Node Feature Tensor). Không có test, không đụng pyproject.

**⚠️ Mâu thuẫn cần chốt (giá trị cốt lõi của story):**
| Schema 0.2 (đã khoá) | Epics 2R.1/2B.2 (đề xuất) |
| --- | --- |
| `tvl_usd` | `tvl` |
| `volume_24h_usd` | `utilization` |
| `price_usd` | `price_delta` |
| `volatility` | `volatility` |
| `connectivity` | `borrow_rate` |

- `graph_snapshot.schema.json` mô tả: *"Contract locked; adding node/edge attributes is a breaking change (bump $id path)"* → nếu research chọn bộ epics, PHẢI đề xuất bump `$id` và cập nhật `$defs/node/features`.
- **Khuyến nghị mặc định:** ưu tiên bộ schema 0.2 (đã locked + đã có validation/tests). Chỉ đổi nếu có lý do toán học rõ (VD `utilization`/`borrow_rate` cần cho fragility Aave). Ghi rõ trade-off.

**Feature nào derivable từ schema 0.1:**
- Derivable trực tiếp: `volume_24h_usd` (sum |amount| swap trong cửa sổ 24h — nhưng cần giá quy USD), `connectivity` (đếm cạnh/degree trong graph — thuộc topology 2R.2), event counts.
- Cần nguồn phụ / tính toán thêm: `price_usd` (từ swap ratio Uniswap HOẶC oracle), `tvl_usd` (cần reserve/state snapshot, KHÔNG có trực tiếp trong event), `volatility` (rolling std của price → cần chuỗi thời gian), `borrow_rate`/`utilization` (Aave: cần reserve data).
- → Nêu rõ feature "cần nguồn phụ" là rủi ro: có thể phải defer hoặc dùng proxy trong v1.

**Liên hệ 2R.2:** `connectivity` phụ thuộc topology (số cạnh của node) → phối hợp với Story 2R.2 (Graph Topology) để định nghĩa nhất quán.

**Context có sẵn:**
- Schema 0.1 (input events): `contracts/tick_data.schema.json` — 11 field, `amount0/1` là decimal string có thể âm.
- Schema 0.2 (output graph, feature nằm ở đây): `contracts/graph_snapshot.schema.json`.
- Decoder đã build (Track 1B) cho biết chính xác field nào có sẵn từ event thật.

### Project Structure Notes

```
research/
  feature_catalog.md   ← output DUY NHẤT của story này (NEW)
```
Không tạo/sửa file code. Nếu chốt bump schema → chỉ GHI KHUYẾN NGHỊ trong doc, việc sửa `graph_snapshot.schema.json` là story build riêng (patch 0.2), không làm ở đây.

### References

- Contract features (đã khoá): `contracts/graph_snapshot.schema.json#/$defs/node/features`
- Input schema: `contracts/tick_data.schema.json`
- Epic 2 Track 2R + Story 2B.2: `_bmad-output/epics.md#Story 2R.1`, `#Story 2B.2`
- Story research mẫu (format): `_bmad-output/implementation-artifacts/1R-1-data-source-assessment.md`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story)

### Debug Log References

Research-only story — no code, no tests, no runtime. Grounded in:
- `contracts/graph_snapshot.schema.json` (locked feature contract, 5 features)
- `contracts/tick_data.schema.json` (schema 0.1 input event fields)
- `research/schema_abi_gap.md` (confirms `borrowRate` is a deferred ABI field; Aave reserve state not in event stream)

### Completion Notes List

- **AC1 (Decision):** Adopted **Schema 0.2** feature set as CANONICAL —
  `[tvl_usd, volume_24h_usd, price_usd, volatility, connectivity]`. **NO `$id` bump.**
  Rationale: schema 0.2 is locked + tested; all 5 are computable from the existing
  pipeline; epics-only `utilization`/`borrow_rate` need Aave reserve state absent
  from tick_data → deferred to a future v2 breaking change (route via Story 0.2 if
  Epic 3/4 fragility math requires).
- **AC1 mapping:** `tvl→tvl_usd` (rename), `volatility` identical, `price_delta→price_usd`
  (re-scope: store level; delta becomes intermediate for volatility),
  `utilization`/`borrow_rate` dropped from v1.
- **AC2/AC3:** Full catalog table (formula, input field, source class, unit, range) in §2.
  Source classes: 0.1-direct, 0.1+price-anchor, state-snapshot, topology(2R.2).
  Flagged sourcing risk: `tvl_usd` needs reserve-state read (or documented cumulative-flow
  proxy); `connectivity` depends on 2R.2 topology.
- **AC4:** Per-feature missing-data policy + expected range + normalization hint for
  Story 2B.3 (log1p→minmax for monetary, per-token zscore for price, none for connectivity).
- Coordination note surfaced for Story 2B.2: emit exactly the 5 canonical keys (schema
  `additionalProperties:false`); replace NaN→0 with warning per 2B.2 AC.

### Change Log

| Date | Change |
|---|---|
| 2026-07-26 | Created `research/feature_catalog.md`: reconciled schema-0.2 vs epics feature sets, locked canonical 5-feature set (no schema bump), catalogued formula/source/range + missing-data & normalization policy. Status → review. |

### File List

- `research/feature_catalog.md` (NEW)
