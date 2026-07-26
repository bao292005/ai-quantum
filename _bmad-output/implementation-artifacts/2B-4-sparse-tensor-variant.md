---
baseline_commit: a56e3f6
type: build
---

# Story 2B.4: Sparse Tensor Variant

Status: review

# ℹ️ NOTE: Story 2R.2 chốt sparse KHÔNG bắt buộc cho v1 (N≈10-15). Story này build sẵn variant cho v2/graph lớn (≥ vài trăm node) theo yêu cầu. Dense (2B.1) vẫn là mặc định v1.

## Story

As a **Kỹ sư AI**,
I want **biến thể sparse (CSR) của adjacency tensor cho graph có tỉ lệ zero cao (≥90%)**,
so that **graph lớn (v2, ~500+ node) tiết kiệm RAM đáng kể mà vẫn cho cùng kết quả contraction với dense**.

## Acceptance Criteria

1. **AC1 — API:** `sparse_adjacency_tensor(graph) -> torch.Tensor` trong `engine/tensor/sparse.py`, trả về **sparse CSR** tensor `(N, N)` float32, layout `torch.sparse_csr`. Không materialize dense trung gian (build COO trực tiếp từ edges rồi → CSR).

2. **AC2 — Tương đương dense (2B.1):** `sparse_adjacency_tensor(g).to_dense()` **bằng** `adjacency_tensor(g)` (2B.1) — cùng đối xứng, cùng aggregate, cùng diagonal. `torch.allclose` (atol 1e-6).

3. **AC3 — Tiết kiệm RAM:** Với graph 500 node, sparsity ~95%, storage của sparse tensor **≤ 20%** của dense (tiết kiệm ≥ 80% RAM). Đo bằng tổng `element_size()*nelement()` của các thành phần (values + crow_indices + col_indices) so với dense `N²·4 bytes`.

4. **AC4 — Contraction khớp:** `sparse @ x` ≈ `dense @ x` cho vector `x` (N,) float32, sai số `< 1e-6` (`torch.allclose(atol=1e-6)`).

5. **AC5 — Robustness:** src/dst lạ → `ValueError` (như 2B.1). 0 edge → sparse tensor rỗng hợp lệ, `.to_dense()` = zero `(N,N)`. Helper `tensor_storage_bytes(t)` tính bytes cho dense/coo/csr.

6. **AC6 — Unit tests:** `tests/unit/test_sparse_tensor.py`: equivalence với dense (nhỏ + build_graph output), CSR layout + float32, 500-node 95% sparse tiết kiệm ≥80% RAM, contraction khớp <1e-6, unknown id → ValueError, 0-edge → zero dense.

## Tasks / Subtasks

- [x] **Task 1 — `sparse_adjacency_tensor`** (AC1, AC2, AC5)
  - [x] Build COO entries đối xứng trực tiếp (giống 2B.1 rule); `torch.sparse_coo_tensor(...).coalesce().to_sparse_csr()`
  - [x] ValueError khi src/dst không có trong node map; 0 edge → empty sparse
- [x] **Task 2 — `tensor_storage_bytes` helper** (AC3)
  - [x] Tính bytes cho dense / sparse_coo / sparse_csr
- [x] **Task 3 — Tests** (AC3, AC4, AC6)
  - [x] Equivalence, RAM saving (500-node 95%), contraction, robustness

## Dev Notes

**Loại story:** `[BUILD]` — variant tối ưu cho v2. **KHÔNG thay dense làm mặc định v1** (2R.2 chốt N≈10-15 → dense đủ). Build sẵn để sẵn sàng khi scope mở rộng.

**Phụ thuộc:**
- **2B.1 (adjacency, DONE):** cùng edge rule (đối xứng, aggregate `+=`, diagonal 0 trừ self-loop). `sparse.to_dense()` PHẢI khớp `adjacency_tensor`. `torch` đã là dep.
- **2R.2:** ngưỡng sparse = N≥512 hoặc sparsity≥90% (xem `research/graph_topology.md`).

**Vì sao CSR (không phải COO):** COO int64 indices `2×nnz×8` bytes → ở 95% sparsity chỉ tiết kiệm ~75% RAM (không đạt AC3 80%). **CSR** dùng `crow_indices` (N+1) + `col_indices` (nnz) + `values` (nnz) → ở 95% sparsity tiết kiệm ~85% → đạt AC3. CSR cũng là format chuẩn cho spMV (`sparse @ x`).

**Build không qua dense:** thu thập `(row, col, val)` từ edges (đối xứng) → `torch.sparse_coo_tensor(indices, values, (N,N)).coalesce()` (coalesce cộng dồn trùng) → `.to_sparse_csr()`. Không tạo ma trận dense `(N,N)` nào.

**Memory measurement:** `element_size()*nelement()` cho từng thành phần. Dense = `N*N*4`. CSR = `values` + `col_indices` + `crow_indices`.

**Testing:** pytest sync. `from engine.tensor.sparse import sparse_adjacency_tensor, tensor_storage_bytes`.

### Project Structure Notes

```
engine/tensor/
  sparse.py               ← NEW (sparse_adjacency_tensor, tensor_storage_bytes)
tests/unit/
  test_sparse_tensor.py   ← NEW
```

### References

- Dense equivalent: `engine/tensor/adjacency.py` (2B.1)
- Sparse threshold: `research/graph_topology.md` (2R.2)
- Epic 2 Track 2B: `_bmad-output/epics.md#Story 2B.4`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story)

### Debug Log References

`tests/unit/test_sparse_tensor.py` 7 passed. Measured: **N=500, sparsity=0.952,
dense=1,000,000B, sparse=148,008B, saving=85.2%** (AC3 ≥80% met). Full suite
**338 passed, 1 skipped**, 0 regressions. (2 benign torch beta warnings: sparse
invariant checks disabled + CSR beta.)

### Completion Notes List

- **AC1:** `engine/tensor/sparse.py` → `sparse_adjacency_tensor(graph) -> torch.Tensor`
  (`torch.sparse_csr`, float32, `(N,N)`). Built from COO entries directly →
  `.coalesce().to_sparse_csr()` — no dense `(N,N)` materialized.
- **AC2:** `.to_dense()` equals dense `adjacency_tensor` (2B.1) — same symmetry,
  accumulation (via COO coalesce), diagonal — verified `allclose(atol=1e-6)` on a
  small graph and on `build_graph` output.
- **AC3:** `tensor_storage_bytes` (dense/COO/CSR). At 500 nodes / 95.2% sparsity,
  CSR = 148 KB vs dense 1 MB → **85.2% saving** (≤20% of dense). CSR chosen over COO
  (COO int64 `2×nnz` indices only reach ~75%).
- **AC4:** `sparse @ x` matches `dense @ x` within `atol=1e-6` (200-node graph).
- **AC5:** unknown `src`/`dst` → `ValueError`; 0 edges → valid empty sparse whose
  `.to_dense()` is the zero matrix.
- **AC6:** 7 tests — CSR layout/dtype, dense equivalence (small + build_graph),
  unknown-id ValueError, zero-edge, 500-node RAM saving, contraction match.

**Scope:** v2/large-graph optimization. Dense (2B.1) remains the v1 default per 2R.2
(N≈10-15). Switch threshold: N≥512 or sparsity≥90% (2R.2).

### Change Log

| Date | Change |
|---|---|
| 2026-07-26 | Added `engine/tensor/sparse.py` `sparse_adjacency_tensor()` (CSR, no dense intermediate) + `tensor_storage_bytes()`; dense-equivalent, 85% RAM saving at 500-node/95% sparsity, contraction match <1e-6; 7 tests. Story file created + status → review. |

### File List

- `engine/tensor/sparse.py` (NEW)
- `tests/unit/test_sparse_tensor.py` (NEW)
- `_bmad-output/implementation-artifacts/2B-4-sparse-tensor-variant.md` (NEW story spec)
