---
baseline_commit: a56e3f6
type: build
---

# Story 2C.1: Tensor Invariant Unit Tests

Status: review

## Story

As a **Quant**,
I want **một test suite verify các invariant toán học của tensor pipeline (symmetry, non-negative, mass conservation) trên nhiều sample graph, cả dense (2B.1) lẫn sparse (2B.4)**,
so that **bug math bị bắt sớm trước khi vào MPS engine (Epic 3)**.

## Acceptance Criteria

1. **AC1 — 20 sample graph:** `tests/unit/test_tensor_invariants.py` sinh ≥ **20 sample GraphSnapshot** đa dạng (nhiều size/sparsity), gồm cả graph từ `build_graph` (2A.3) và một số graph thủ công (single-node/0-edge, self-loop, parallel edges).

2. **AC2 — Symmetry:** Với mỗi graph, `adjacency_tensor(g)` (dense) đối xứng (`A == A.T`), và `sparse_adjacency_tensor(g).to_dense()` cũng đối xứng và **bằng** dense (`allclose 1e-6`).

3. **AC3 — Non-negative:** Mọi entry của adjacency (dense + sparse) `>= 0`. Feature tensor (2B.2) hữu hạn (no NaN/inf).

4. **AC4 — Mass conservation:** Tổng khối lượng adjacency bảo toàn: `A.sum() == Σ_edges (2·w nếu src≠dst else w)` (off-diagonal cộng 2 lần do đối xứng, self-loop 1 lần). Dense và sparse cho cùng tổng (`allclose 1e-6`).

5. **AC5 — Dense + sparse coverage:** Mỗi invariant test chạy trên CẢ dense (2B.1) VÀ sparse (2B.4) variant.

6. **AC6 — All pass:** `pytest tests/unit/test_tensor_invariants.py` toàn bộ pass; không regression.

## Tasks / Subtasks

- [x] **Task 1 — Sample graph generator** (AC1)
  - [x] Helper sinh ≥20 graph: build_graph với seed/size khác nhau + manual edge cases (self-loop, parallel, 0-edge)
- [x] **Task 2 — Invariant tests** (AC2-AC5)
  - [x] Parametrize 20 graph × invariant; symmetry, non-negative, mass conservation cho dense + sparse
  - [x] Feature tensor finite
- [x] **Task 3 — Run + verify** (AC6)
  - [x] Toàn bộ pass; full suite không regression

## Dev Notes

**Loại story:** `[BUILD]` (test-only) — KHÔNG thêm source code, chỉ test invariant trên Track 2B. Không đụng pyproject.

**Phụ thuộc (đều DONE):**
- 2B.1 `adjacency_tensor` (dense), 2B.4 `sparse_adjacency_tensor` (CSR), 2B.2 `feature_tensor`, 2A.3 `build_graph`.

**Invariant định nghĩa rõ:**
- **Symmetry:** builder cộng cả `A[i,j]` và `A[j,i]` → đối xứng theo thiết kế 2B.1/2B.4.
- **Non-negative:** edge weight ∈ [0,1], cộng dồn non-negative → mọi entry ≥ 0.
- **Mass conservation:** `A.sum()` = Σ mỗi edge đóng góp `2w` (off-diag, do đối xứng) hoặc `w` (self-loop, cộng 1 lần). Tính expected TỪ `graph["edges"]` để so.

**Path:** epic ghi `tests/test_tensor_invariants.py`; đặt tại `tests/unit/` cho khớp cấu trúc dự án (pytest `testpaths=["tests"]` vẫn pick up). `pytest tests/unit/test_tensor_invariants.py`.

**Manual edge cases (đưa vào 20 graph):** build_graph KHÔNG sinh self-loop → thêm graph dict thủ công có self-loop (`src==dst`) + parallel edges để test mass rule đầy đủ.

**Testing:** pytest sync. `from engine.tensor.adjacency import adjacency_tensor`; `from engine.tensor.sparse import sparse_adjacency_tensor`; `from engine.tensor.features import feature_tensor`.

### Project Structure Notes

```
tests/unit/
  test_tensor_invariants.py   ← NEW (test-only)
```

### References

- Dense: `engine/tensor/adjacency.py` (2B.1)
- Sparse: `engine/tensor/sparse.py` (2B.4)
- Feature: `engine/tensor/features.py` (2B.2)
- Graph builder: `engine/graph/builder.py` (2A.3)
- Epic 2 Track 2C: `_bmad-output/epics.md#Story 2C.1`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story)

### Debug Log References

`tests/unit/test_tensor_invariants.py` **106 passed** (21 sample graphs ×
5 parametrized invariants + count check). Full suite **444 passed, 1 skipped**
(mock WSS), 0 regressions. (2 benign torch CSR beta warnings.)

### Completion Notes List

- **AC1:** 21 sample graphs — 17 from `build_graph` (seed-varied size/sparsity/protocol)
  + 4 manual edge cases (single-node/0-edge, self-loop, parallel edges, mixed
  self-loop+parallel). `test_have_at_least_20_samples` guards the count.
- **AC2:** symmetry — `adjacency_tensor(g) == .T` and
  `sparse_adjacency_tensor(g).to_dense()` symmetric + equal to dense (`allclose 1e-6`).
- **AC3:** non-negativity — all dense entries ≥ 0, all sparse values ≥ 0; feature
  tensor shape `(N,5)` + all-finite.
- **AC4:** mass conservation — `A.sum() == Σ_edges (2w if src≠dst else w)`, computed
  from `graph["edges"]`; dense and sparse both match (`abs=1e-4`). Self-loop/parallel
  manual graphs exercise the full rule.
- **AC5:** every invariant runs on BOTH dense (2B.1) and sparse (2B.4).
- **AC6:** all pass; no regression.

Test-only story — no source/pyproject changes.

### Change Log

| Date | Change |
|---|---|
| 2026-07-26 | Added `tests/unit/test_tensor_invariants.py`: 21 sample graphs × symmetry/non-negative/mass-conservation invariants across dense + sparse variants + feature finiteness (106 tests). Story file created + status → review. |

### File List

- `tests/unit/test_tensor_invariants.py` (NEW)
- `_bmad-output/implementation-artifacts/2C-1-tensor-invariant-tests.md` (NEW story spec)
