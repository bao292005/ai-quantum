---
baseline_commit: a56e3f6
type: build
---

# Story 2B.2: Node Feature Tensor

Status: review

## Story

As a **Kỹ sư AI**,
I want **hàm `feature_tensor(graph) -> torch.Tensor` trả về ma trận đặc trưng node `(N, F)` float32 từ một `GraphSnapshot`**,
so that **MPS engine (Epic 3) có node embedding input song song với adjacency tensor (2B.1)**.

## Acceptance Criteria

1. **AC1 — Signature & shape:** `feature_tensor(graph) -> torch.Tensor` trong `engine/tensor/features.py`. Với `GraphSnapshot` có `N` node → trả về tensor shape `(N, F)`, dtype `torch.float32`. **F = 5** (bộ feature canonical chốt ở Story 2R.1).

2. **AC2 — Thứ tự feature CỐ ĐỊNH (2R.1):** Cột theo đúng thứ tự: `[tvl_usd, volume_24h_usd, price_usd, volatility, connectivity]`. Hằng số `FEATURE_ORDER` export được để consumer (2C.*/Epic 3) tham chiếu.

3. **AC3 — Node ordering nhất quán 2B.1:** Chỉ số hàng = thứ tự xuất hiện trong `graph["nodes"]` (0..N-1) — GIỐNG HỆT `adjacency_tensor` (2B.1) để adjacency và feature khớp hàng.

4. **AC4 — NaN → 0 + warning:** Nếu bất kỳ giá trị feature nào là `NaN` (hoặc `inf`), thay bằng `0.0` và phát **warning** (logging.warning hoặc warnings.warn) nêu rõ node + feature. Không để NaN/inf lọt vào tensor (làm hỏng MPS).

5. **AC5 — Robustness:** Node thiếu key feature bắt buộc → raise `ValueError` rõ ràng (feature nào, node nào). `N=1` vẫn trả `(1, 5)`. `graph["nodes"]` rỗng không xảy ra (schema `minItems:1`), nhưng nếu list rỗng → raise `ValueError`.

6. **AC6 — Unit tests:** `tests/unit/test_feature_tensor.py`: shape `(N,5)` + dtype float32; thứ tự cột đúng (đặt giá trị test đọc lại đúng vị trí); node ordering khớp `adjacency_tensor`; NaN→0 + warning được raise; inf→0; thiếu feature → ValueError; round-trip với `build_graph` (2A.3) output.

## Tasks / Subtasks

- [x] **Task 1 — `engine/tensor/features.py`** (AC1, AC2)
  - [x] `FEATURE_ORDER = ("tvl_usd","volume_24h_usd","price_usd","volatility","connectivity")`
  - [x] `feature_tensor(graph) -> torch.Tensor` shape `(N,5)` float32
- [x] **Task 2 — Extract + sanitize** (AC2, AC3, AC4, AC5)
  - [x] Loop `graph["nodes"]` theo thứ tự; đọc `features[k]` cho k in FEATURE_ORDER
  - [x] `math.isnan`/`math.isinf` → 0.0 + warning; thiếu key → ValueError
- [x] **Task 3 — Tests** (AC6)
  - [x] `tests/unit/test_feature_tensor.py`: các invariant + round-trip build_graph

## Dev Notes

**Loại story:** `[BUILD]` — cặp đôi với 2B.1 (adjacency). Cùng node ordering để MPS engine dùng `(A, X)` khớp hàng.

**Phụ thuộc:**
- **2R.1 (feature catalog, DONE):** bộ 5 feature canonical + thứ tự = `[tvl_usd, volume_24h_usd, price_usd, volatility, connectivity]`. Xem `research/feature_catalog.md`. AC "NaN→0" chính là missing-data policy 2R.1.
- **2B.1 (adjacency, DONE):** node ordering = thứ tự `graph["nodes"]`. PHẢI giống hệt để `adjacency_tensor(g)` và `feature_tensor(g)` cùng đánh index node.
- **2A.1 (Node model):** node dict có `features` với đúng 5 key (đã validate). `build_graph` (2A.3) emit đúng dạng này.

**Input `graph`:** dict GraphSnapshot (schema 0.2), giống 2B.1. Không bắt buộc Pydantic.

**NaN/inf handling (AC4):** dùng `math.isnan(v) or math.isinf(v)` → 0.0. Phát `warnings.warn(...)` HOẶC `logging.warning(...)` một lần mỗi giá trị xấu, nêu `node_id` + feature. (Liên hệ review note 2A: model Pydantic chặn NaN nhưng KHÔNG chặn inf ở field unbounded — nên feature_tensor phải tự guard cả inf.)

**dtype/perf:** `torch.tensor(rows, dtype=torch.float32)` với `rows` là list[list[float]] N×5. N nhỏ (~10-50) → không cần vectorize phức tạp.

**⚠️ Coordination 2C.1 (invariant tests):** 2C.1 có thể test `feature_tensor` cùng `adjacency_tensor`. Chốt signature `feature_tensor(graph) -> torch.Tensor` shape `(N,5)` float32, `FEATURE_ORDER` cố định.

**Testing:** pytest sync. `from engine.tensor.features import feature_tensor, FEATURE_ORDER`.

### Project Structure Notes

```
engine/tensor/
  features.py             ← NEW (feature_tensor, FEATURE_ORDER)
tests/unit/
  test_feature_tensor.py  ← NEW
```
`torch` đã là dep từ 2B.1 — không cần thêm.

### References

- Feature set + policy: `research/feature_catalog.md` (2R.1)
- Node ordering (khớp): `engine/tensor/adjacency.py` (2B.1)
- Node model: `engine/graph/node_types.py` (2A.1)
- Graph source: `engine/graph/builder.py` (2A.3)
- Contract: `contracts/graph_snapshot.schema.json#/$defs/node/features`
- Epic 2 Track 2B: `_bmad-output/epics.md#Story 2B.2`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story)

### Debug Log References

`tests/unit/test_feature_tensor.py` 10 passed. Full suite **321 passed, 1 skipped**
(mock WSS), 0 regressions.

### Completion Notes List

- **AC1/AC2:** `engine/tensor/features.py` → `feature_tensor(graph) -> torch.Tensor`,
  shape `(N, 5)`, `float32`. `FEATURE_ORDER = (tvl_usd, volume_24h_usd, price_usd,
  volatility, connectivity)` exported (locked by 2R.1).
- **AC3:** rows follow `graph["nodes"]` order — identical to `adjacency_tensor` (2B.1);
  test asserts both index the same nodes so `(A, X)` align row-wise.
- **AC4:** `NaN`/`inf` → `0.0` with a `warnings.warn` naming node+feature (2R.1
  missing-data policy). Guards `inf` explicitly (Pydantic blocks NaN but not inf on
  unbounded feature fields — cf. 2A review note P1).
- **AC5:** missing feature key → `ValueError` (names node+feature); empty nodes →
  `ValueError`; `N=1` → `(1,5)`.
- **AC6:** 10 tests — shape/dtype, single node, FEATURE_ORDER constant, column-order
  values, row-ordering matches adjacency, NaN→0+warn, inf→0+warn, missing→ValueError,
  empty→ValueError, round-trip with `build_graph` (2A.3) incl. connectivity∈[0,1] +
  all-finite.
- Pairs with 2B.1: `adjacency_tensor(g)` `(N,N)` + `feature_tensor(g)` `(N,5)` share
  node ordering → ready as `(A, X)` for MPS engine (Epic 3). `torch` already a dep.

### Change Log

| Date | Change |
|---|---|
| 2026-07-26 | Added `engine/tensor/features.py` `feature_tensor()`: (N,5) float32 node feature matrix, FEATURE_ORDER per 2R.1, node ordering matches 2B.1, NaN/inf→0 with warning, missing→ValueError; 10 tests. Story file created + status → review. |

### File List

- `engine/tensor/features.py` (NEW)
- `tests/unit/test_feature_tensor.py` (NEW)
- `_bmad-output/implementation-artifacts/2B-2-node-feature-tensor.md` (NEW story spec)
