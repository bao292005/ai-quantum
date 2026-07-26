---
baseline_commit: ae1732c
type: build
---

# Story 2B.1: Adjacency Tensor Constructor

Status: ready-for-dev

# ⚠️ NEW DEPENDENCY: story này giới thiệu **PyTorch** lần đầu vào codebase (chưa cài). Xem Dev Notes trước khi code.

## Story

As a **Kỹ sư AI**,
I want **hàm `adjacency_tensor(graph) -> torch.Tensor` trả về ma trận kề `(N, N)` float32 từ một `GraphSnapshot`**,
so that **MPS engine (Epic 3) có input tensor chuẩn để phân rã và tính Fragility**.

## Acceptance Criteria

1. **AC1 — Signature & shape:** `adjacency_tensor(graph) -> torch.Tensor` trong `engine/tensor/adjacency.py`. Với `GraphSnapshot` có `N` node → trả về tensor shape `(N, N)`, dtype `torch.float32`.

2. **AC2 — Node ordering xác định:** Chỉ số hàng/cột = thứ tự xuất hiện của node trong `graph["nodes"]` (index 0..N-1). Xây map `node_id -> index` từ thứ tự đó. Edge dùng `src`/`dst` (node id) → tra map để đặt giá trị.

3. **AC3 — Đối xứng (undirected v1):** Ma trận đối xứng: `A[i, j] == A[j, i]`. Với mỗi edge `(src, dst, weight)`: đặt `A[i, j] += weight` và `A[j, i] += weight` (i≠j). Nhiều edge giữa cùng cặp node → cộng dồn weight (document assumption).

4. **AC4 — Đường chéo = 0:** Không self-loop → `A[i, i] = 0` (trừ khi tồn tại edge `src == dst`, khi đó cộng vào đường chéo 1 lần).

5. **AC5 — Robustness:** Edge tham chiếu `src`/`dst` không có trong `nodes` → raise `ValueError` rõ ràng (không im lặng bỏ). Graph 0 edge → trả về ma trận zero `(N, N)`.

6. **AC6 — Perf:** Benchmark cho `N = 50` (fixture) < 5ms/call trên 1 CPU core (đo bằng test, warm run).

7. **AC7 — Unit tests:** `tests/unit/test_adjacency_tensor.py`: shape đúng, đối xứng, ordering đúng (giá trị đặt đúng ô), diagonal 0, 0-edge → zero, edge id lạ → ValueError, dtype float32.

## Tasks / Subtasks

- [ ] **Task 0 — Thêm PyTorch** (blocker)
  - [ ] Thêm `torch>=2.1` vào `dependencies` trong `pyproject.toml`
  - [ ] Cài **CPU-only**: `pip install torch` (NFR5 — local-first CPU, KHÔNG GPU). Xác nhận `python -c "import torch; print(torch.__version__)"`
  - [ ] Đảm bảo `engine*` đã có trong `packages.find include` (từ 2A.1; nếu chưa thì thêm)
- [ ] **Task 1 — Package `engine/tensor/`** (AC1)
  - [ ] `engine/tensor/__init__.py`, `engine/tensor/adjacency.py`
- [ ] **Task 2 — Implement `adjacency_tensor`** (AC1-AC5)
  - [ ] Build `node_id -> index` từ thứ tự `graph["nodes"]`
  - [ ] `A = torch.zeros((N, N), dtype=torch.float32)`; loop edges cộng dồn đối xứng
  - [ ] ValueError khi src/dst không có trong map
- [ ] **Task 3 — Benchmark + tests** (AC6, AC7)
  - [ ] Fixture 50-node GraphSnapshot; test `< 5ms` warm; các test invariant

## Dev Notes

**Loại story:** `[BUILD]` — **thực tế độc lập research**: shape `(N,N)` suy từ graph runtime nên code dense chạy bất kể 2R.2. 2R.2 chỉ quyết **có cần sparse variant (2B.4) không** và N kỳ vọng — KHÔNG chặn 2B.1 dense.

**⚠️ PyTorch (dependency mới, chưa cài):**
- Stack pinned (epics Additional Requirements) = **PyTorch 2.1+** → đây là expected, không phải dep tuỳ tiện.
- Cài **CPU wheel** (`pip install torch`) — NFR5 yêu cầu local-first CPU, không GPU. Không cần CUDA.
- Đây là story ĐẦU TIÊN dùng torch → sau story này torch thành dep chuẩn cho Epic 2/3.

**Input `graph` — dạng gì?** Nhận **dict** khớp `graph_snapshot.schema.json` (`graph["nodes"]`, `graph["edges"]`), KHÔNG bắt buộc Pydantic. Lý do: Story 2A.3 (Graph Builder) sẽ emit GraphSnapshot; trong lúc chờ, test dùng dict mock trực tiếp theo schema 0.2. Nếu muốn nhận cả Pydantic Node/Edge (2A.1/2A.2) thì accept `.model_dump()` — nhưng tối thiểu phải nhận dict.

**Contract 0.2 (input):** `contracts/graph_snapshot.schema.json`
- `nodes[]`: mỗi node có `id` (string), `type`, `features`.
- `edges[]`: `src`, `dst` (= node `id`), `weight` (0..1), `edge_type`, `metadata?`.
- `nodes` minItems 1 → N ≥ 1. `edges` minItems 0 → có thể rỗng.

**⚠️ Directionality (đối xứng) — quyết định v1:** MPS adjacency dùng ma trận đối xứng (undirected). v1 symmetrize TẤT CẢ edge type (kể cả `borrow_position` vốn có hướng). Đây là giả định modeling — ghi rõ trong docstring + đánh dấu để Story 2R.2 / 3R.1 xác nhận hoặc override (nếu cần directed, dùng ma trận không đối xứng ở v2).

**⚠️ Coordination với 2C.1 (Tensor Invariant Tests):** 2C.1 test invariant (symmetry, non-negative, mass conservation) trên output hàm NÀY. Chốt signature `adjacency_tensor(graph) -> torch.Tensor`, shape `(N,N)`, float32, đối xứng — để 2C.1 viết test khớp. Nếu đổi signature phải báo 2C.1.

**Aggregate rule (nhiều edge cùng cặp):** cộng dồn weight (`+=`). Giá trị ô có thể > 1 nếu nhiều edge — chấp nhận ở adjacency (weight [0,1] là per-edge, không phải per-cell). Document trong docstring.

**Perf:** dùng vectorization nếu được (build index arrays rồi `index_put_` / scatter) hoặc loop đơn giản cho N nhỏ (~50). Test warm-run < 5ms.

**Testing:** pytest sync. `from engine.tensor.adjacency import adjacency_tensor`. Seed không cần (deterministic).

### Project Structure Notes

```
engine/tensor/
  __init__.py             ← NEW
  adjacency.py            ← NEW (adjacency_tensor)
tests/unit/
  test_adjacency_tensor.py ← NEW
pyproject.toml            ← UPDATE (dependencies += torch>=2.1; engine* include nếu chưa)
```

### References

- Contract: `contracts/graph_snapshot.schema.json` (nodes/edges)
- Node/Edge model (nếu dùng): `engine/graph/node_types.py` (2A.1), `engine/graph/edge_types.py` (2A.2)
- Topology decision (N, sparse): `research/graph_topology.md` (2R.2)
- Epic 2 Track 2B: `_bmad-output/epics.md#Story 2B.1`
- 2C.1 invariant tests (coordinate signature): `_bmad-output/epics.md#Story 2C.1`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

- `engine/tensor/__init__.py` (NEW)
- `engine/tensor/adjacency.py` (NEW)
- `tests/unit/test_adjacency_tensor.py` (NEW)
- `pyproject.toml` (UPDATE)
