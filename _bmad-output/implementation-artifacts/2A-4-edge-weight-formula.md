---
baseline_commit: a56e3f6
type: research
---

# Story 2A.4: Edge Weight Formula

Status: review

## Story

As a **Quant**,
I want **một công thức chốt cho edge weight = f(volume_usd, time_decay, protocol_correlation) chuẩn hoá về `[0, 1]`**,
so that **Story 2A.3 (Graph Builder) có công thức rõ ràng để gán `weight` cho mỗi cạnh thay vì đoán, và weight phản ánh đúng cường độ liquidity flow / lan truyền rủi ro giữa các node**.

## Acceptance Criteria

1. **AC1 — Công thức chốt:** `research/edge_weight_formula.md` định nghĩa công thức tính `weight` cho từng `edge_type` (`liquidity_flow`, `borrow_position`, `shared_collateral`), dựa trên các thành phần: (a) khối lượng USD (`volume_usd`), (b) suy giảm theo thời gian (`time_decay`), (c) tương quan/độ liên kết (`protocol_correlation` hoặc shared-token exposure). Nêu rõ input mỗi thành phần lấy từ đâu (event schema 0.1 + topology 2R.2).

2. **AC2 — Chuẩn hoá `[0, 1]`:** Công thức đảm bảo `weight ∈ [0, 1]` (khớp ràng buộc contract 0.2 `#/$defs/edge`). Nêu rõ cách normalize (min-max theo snapshot, hoặc squashing như `tanh`/logistic, hoặc chia cho tổng). Ghi rõ hành vi khi chỉ có 1 cạnh / tổng = 0 (tránh chia 0).

3. **AC3 — Time-decay đúng hướng:** Với 2+ cạnh cùng `volume_usd` nhưng khác thời điểm, cạnh **mới nhất** có `weight` LỚN HƠN (half-life / hằng số suy giảm λ nêu rõ, đơn vị giây). Cho ví dụ số minh hoạ.

4. **AC4 — 5 case biên (worked examples):** Doc trình bày 5 trường hợp biên với input → output `weight` tính tay: (1) cạnh đơn (tổng=0 guard), (2) hai cạnh cùng volume khác thời gian, (3) volume=0, (4) volume rất lớn (bão hoà về ≤1), (5) shared_collateral / borrow_position vs liquidity_flow (khác edge_type). Đây là bảng tham chiếu để Story 2A.3 viết unit test khớp.

## Tasks / Subtasks

- [x] **Task 1 — Định nghĩa 3 thành phần** (AC1)
  - [x] `volume_usd`: nguồn (sum |amount| swap × price anchor; xem 2R.1 về giới hạn price)
  - [x] `time_decay`: hàm suy giảm (VD `exp(-λ·Δt)`), chọn λ/half-life + đơn vị
  - [x] `protocol_correlation` / shared exposure: định nghĩa cho từng edge_type
- [x] **Task 2 — Công thức tổng hợp + normalize** (AC1, AC2)
  - [x] Kết hợp 3 thành phần → raw score; normalize về `[0,1]`; guard chia-0
- [x] **Task 3 — Time-decay validation** (AC3)
  - [x] Ví dụ số: 2 cạnh cùng volume, Δt khác → cạnh mới weight lớn hơn
- [x] **Task 4 — Viết `research/edge_weight_formula.md` + 5 case biên** (AC1-AC4)
  - [x] Bảng 5 worked examples (input → weight) làm reference cho unit test 2A.3

## Dev Notes

**Loại story:** `[RESEARCH]` — output là document công thức, KHÔNG code. **Chặn Story 2A.3** (Graph Builder áp dụng công thức này). Không test tự động ở story này (test thực nằm ở 2A.3 khi implement công thức); worked examples trong doc là "ground truth" cho các test đó.

**Contract PHẢI bám:** `weight` ∈ `[0, 1]` (schema 0.2 `#/$defs/edge`, `minimum:0 maximum:1`). Công thức KHÔNG được tạo weight ngoài khoảng này.

**Liên hệ chéo:**
- **2R.2 (graph topology):** edge rules đã chốt — `liquidity_flow` (protocol→pool, pool→token), `borrow_position` (Aave pool→reserve), `shared_collateral` (pool↔pool qua token chung). Công thức weight phải áp được cho cả 3 loại. Xem `research/graph_topology.md`.
- **2R.1 (feature catalog):** `volume_24h_usd` và giới hạn price-anchor (USD cần stablecoin/WETH leg hoặc oracle). Công thức volume_usd kế thừa giới hạn này — nếu chưa có price, dùng token-volume proxy và ghi rõ. Xem `research/feature_catalog.md`.
- **2A.3 (Graph Builder):** tiêu thụ công thức này để gán `Edge.weight`. 5 worked examples → 5 unit test.

**Gợi ý công thức (điểm khởi đầu, research xác nhận/điều chỉnh):**
```
raw(e)   = volume_usd(e) · exp(-λ · Δt(e)) · corr(e)
weight(e)= normalize(raw(e))            # min-max theo snapshot HOẶC tanh(raw/scale)
```
- `Δt` = (block_timestamp mới nhất trong snapshot − block_timestamp của cạnh), giây.
- Guard: nếu chỉ 1 cạnh hoặc tổng raw = 0 → weight = 0 (hoặc quy ước rõ, tránh chia 0 / NaN).
- Bão hoà: đảm bảo volume rất lớn không đẩy weight > 1 (nếu dùng min-max thì tự bounded; nếu tanh thì bounded sẵn).

**Không cần:** code, test, pyproject changes. Chỉ tạo `research/edge_weight_formula.md`.

### Project Structure Notes

```
research/
  edge_weight_formula.md   ← output DUY NHẤT của story này (NEW)
```

### References

- Contract: `contracts/graph_snapshot.schema.json#/$defs/edge`
- Topology (edge rules): `research/graph_topology.md` (Story 2R.2)
- Feature/price limits: `research/feature_catalog.md` (Story 2R.1)
- Epic 2 Track 2A: `_bmad-output/epics.md#Story 2A.4`
- Consumer: `_bmad-output/epics.md#Story 2A.3`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story)

### Debug Log References

Research-only — no code/test. Formula grounded in 2R.2 edge rules + 2R.1 price limits.

### Completion Notes List

- **AC1:** 3 components — `volume_usd(e)` (per edge_type source table; token-native
  proxy when no USD anchor per 2R.1), `time_decay(e) = exp(-λΔt)` (Δt seconds,
  half-life 1h → λ=ln2/3600), `corr(e)` per edge_type (liquidity_flow 1.0,
  borrow_position 0.7, shared_collateral 0.5). `raw = volume·decay·corr`.
- **AC2:** Normalize snapshot-relative: `weight = raw/max_raw`, `0` when `max_raw=0`
  (div-0 guard). Bounded [0,1], auto-saturating. Documented tanh alternative (not chosen).
- **AC3:** Time-decay worked table — equal volume, Δt 0 vs 3600 → weights 1.0 vs 0.5
  (newest larger).
- **AC4:** 5 boundary worked examples (single/div-0, time-decay, zero-volume,
  saturation, edge_type corr) — ground truth for 2A.3 unit tests.

### Change Log

| Date | Change |
|---|---|
| 2026-07-26 | Created `research/edge_weight_formula.md`: raw=volume·exp(-λΔt)·corr, snapshot min-max normalize to [0,1] with div-0 guard, half-life 1h, per-edge_type corr, 5 worked boundary examples. Status → review. |

### File List

- `research/edge_weight_formula.md` (NEW)
