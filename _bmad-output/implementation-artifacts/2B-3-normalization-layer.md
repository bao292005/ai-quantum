---
baseline_commit: a56e3f6
type: build
---

# Story 2B.3: Normalization Layer

Status: review

## Story

As a **Kỹ sư AI**,
I want **hàm `normalize(tensor, method="minmax"|"zscore")` chuẩn hoá node feature tensor per-cột, kèm `NormalizationState` để lưu tham số dùng lại lúc inference**,
so that **thử nghiệm được scheme nào giúp MPS ổn định hơn, và train/inference dùng CÙNG tham số (tránh train-serve skew)**.

## Acceptance Criteria

1. **AC1 — API:** `normalize(tensor, method="minmax") -> tuple[torch.Tensor, NormalizationState]` trong `engine/tensor/normalize.py`. `method ∈ {"minmax", "zscore"}`; method khác → `ValueError`. Chuẩn hoá **per-cột** (dim=0) trên tensor `(N, F)` float32.

2. **AC2 — minmax → [0,1]:** Với `method="minmax"`, mỗi cột output ∈ `[0, 1]` (min→0, max→1). Kể cả khi có outlier. Guard cột hằng (max==min) → output `0.0` (không NaN/chia-0).

3. **AC3 — zscore → mean≈0, std≈1:** Với `method="zscore"`, mỗi cột output có `mean≈0`, `std≈1` (dùng population std, `unbiased=False`). Guard cột std==0 → output `0.0`.

4. **AC4 — Persist + reuse (`NormalizationState`):** `normalize()` trả về `NormalizationState` chứa `method` + tham số per-cột (min/max hoặc mean/std). `NormalizationState.apply(tensor) -> torch.Tensor` áp LẠI đúng tham số đó lên tensor mới (inference). `apply` trên chính tensor đã fit → khớp output của `normalize`.

5. **AC5 — Robustness:** Output luôn `float32`, shape giữ nguyên `(N, F)`. Không NaN/inf trong output (guard chia-0). `N=1` → minmax cột hằng → 0; zscore std=0 → 0.

6. **AC6 — Unit tests:** `tests/unit/test_normalize.py`: minmax range [0,1] với outlier; zscore mean≈0/std≈1; constant-column guard (no NaN) cả 2 method; invalid method → ValueError; state reuse (`apply` khớp `normalize`); round-trip với `feature_tensor` (2B.2) output.

## Tasks / Subtasks

- [x] **Task 1 — `NormalizationState`** (AC4)
  - [x] dataclass: `method: str`, tham số per-cột (tensors); `apply(tensor) -> Tensor`
- [x] **Task 2 — `normalize()`** (AC1-AC3, AC5)
  - [x] minmax: `(x-min)/(max-min)`, guard range==0 → 0
  - [x] zscore: `(x-mean)/std` (`unbiased=False`), guard std==0 → 0
  - [x] invalid method → ValueError; giữ float32 + shape
- [x] **Task 3 — Tests** (AC6)
  - [x] `tests/unit/test_normalize.py` theo AC6

## Dev Notes

**Loại story:** `[RESEARCH→BUILD]` — phần "research" (scheme nào) đã được Story 2R.1 định hướng (normalization hints per-feature). Story này BUILD cái toggle minmax/zscore generic; tinh chỉnh per-feature (log1p cho monetary, per-token zscore cho price, bỏ connectivity) là **v2/optional** — ghi rõ, KHÔNG làm ở đây để tránh over-engineering.

**Phụ thuộc:**
- **2B.2 (feature_tensor, DONE):** input là tensor `(N, 5)` float32 từ `feature_tensor`. `torch` đã là dep.
- **2R.1 (feature catalog):** range kỳ vọng + hint normalization mỗi feature. `connectivity` đã ∈[0,1] (minmax gần như no-op); monetary heavy-tailed (lý tưởng log trước — defer v2). Xem `research/feature_catalog.md` §3.

**Train-serve skew (AC4 — giá trị cốt lõi):** phải fit tham số trên tập train rồi tái dùng ở inference. `NormalizationState` giữ min/max (minmax) hoặc mean/std (zscore) per-cột. KHÔNG re-fit ở inference.

**Guard chia-0 (bắt buộc):**
- minmax: nếu `max==min` (cột hằng) → `(x-min)/0` = NaN → thay bằng 0.
- zscore: nếu `std==0` → NaN → thay bằng 0.
Dùng `torch.where(denom==0, 0, ...)` hoặc set denom=1 khi 0 rồi zero-out.

**zscore std:** dùng `tensor.std(dim=0, unbiased=False)` (population) để output std=1 chính xác; `unbiased=True` (Bessel) với N nhỏ làm std output ≠1. Test assert với `unbiased=False`.

**Testing:** pytest sync. `from engine.tensor.normalize import normalize, NormalizationState`.

### Project Structure Notes

```
engine/tensor/
  normalize.py            ← NEW (normalize, NormalizationState)
tests/unit/
  test_normalize.py       ← NEW
```

### References

- Input tensor: `engine/tensor/features.py` (2B.2)
- Normalization hints: `research/feature_catalog.md` §3 (2R.1)
- Epic 2 Track 2B: `_bmad-output/epics.md#Story 2B.3`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story)

### Debug Log References

`tests/unit/test_normalize.py` 10 passed. Full suite **331 passed, 1 skipped** (mock WSS), 0 regressions.

### Completion Notes List

- **AC1:** `engine/tensor/normalize.py` → `normalize(tensor, method="minmax") -> (Tensor, NormalizationState)`;
  invalid method → `ValueError`. Per-column (dim=0), float32.
- **AC2:** minmax → `(x-min)/(max-min)`; each column min→0, max→1 (verified with an outlier column).
- **AC3:** zscore → `(x-mean)/std` with `unbiased=False` (population) → column mean≈0, std≈1 (atol 1e-6).
- **AC4:** `NormalizationState` (frozen dataclass) holds `method`, per-column `offset`/`scale`/`zero_mask`;
  `apply(tensor)` re-applies fitted params (train→inference). `apply` on the fitted tensor matches
  `normalize` output; applying train-state to an inference tensor maps train min/max → 0/1.
- **AC5:** div-0 guard via `zero_mask` (constant column / std=0 → 0.0); output always float32, shape preserved,
  all-finite (no NaN/inf); N=1 handled.
- **AC6:** 10 tests — invalid method, shape/dtype/state, minmax range w/ outlier, zscore mean/std,
  constant-column no-NaN (both methods), single-row, apply==normalize, state reuse on new tensor,
  round-trip with `feature_tensor` (2B.2).

**Scope note:** generic minmax/zscore toggle only. Per-feature refinements from 2R.1 (log1p for monetary,
per-token zscore for price, skip connectivity) deferred to v2 to avoid over-engineering.

### Change Log

| Date | Change |
|---|---|
| 2026-07-26 | Added `engine/tensor/normalize.py` `normalize()` + `NormalizationState`: per-column minmax/zscore with div-0 guards and reusable fitted params (train-serve parity); 10 tests. Story file created + status → review. |

### File List

- `engine/tensor/normalize.py` (NEW)
- `tests/unit/test_normalize.py` (NEW)
- `_bmad-output/implementation-artifacts/2B-3-normalization-layer.md` (NEW story spec)
