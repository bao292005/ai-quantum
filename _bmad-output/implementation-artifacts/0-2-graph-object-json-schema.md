---
baseline_commit: 186d98f8f25e4da0e1cd16100f350b9dd6f08ddc
---

# Story 0.2: Graph Object JSON Schema

Status: done

## Story

As a **Kỹ sư AI (AI Lead)**,
I want **định nghĩa JSON Schema (Draft 2020-12) cho `GraphSnapshot` tại `contracts/graph_snapshot.schema.json`**,
so that **Track 3A/3B/3C/3D (MPS Algorithm) mock được input mà chưa cần Track 2A/2B xong, mở khoá 5 track Epic 3 chạy song song với Epic 2**.

## Acceptance Criteria

1. **AC1 — Schema file:** `contracts/graph_snapshot.schema.json` tuân Draft 2020-12, có `$schema`, `$id: "https://quantumradar.io/schemas/graph_snapshot.schema.json"`, `title`, `description`.

2. **AC2 — Cấu trúc top-level:** Top-level object có 5 trường required:
   - `snapshot_id` (string, UUID v4 pattern)
   - `block_range` (object: `{start: int, end: int}`, `end >= start`)
   - `created_at` (string, ISO 8601 UTC pattern như Story 0.1)
   - `nodes` (array, `minItems: 1`)
   - `edges` (array, `minItems: 0`)
   `additionalProperties: false`.

3. **AC3 — Schema Node:** Mỗi node là object có required `{id, type, features}`:
   - `id` (string, non-empty, unique trong array)
   - `type` (enum: `"protocol" | "pool" | "token"`)
   - `features` (object): required 5 field float:
     - `tvl_usd` (number ≥ 0)
     - `volume_24h_usd` (number ≥ 0)
     - `price_usd` (number ≥ 0)
     - `volatility` (number ≥ 0)
     - `connectivity` (number ∈ [0, 1])
   `additionalProperties: false` cho features.

4. **AC4 — Schema Edge:** Mỗi edge có required `{src, dst, weight, edge_type}`:
   - `src`, `dst` (string, phải reference node.id — validate ở runtime, không enforce trong pure schema)
   - `weight` (number ∈ [0, 1])
   - `edge_type` (enum: `"liquidity_flow" | "borrow_position" | "shared_collateral"`)
   - Optional `metadata` (object, `additionalProperties: true` cho phép mở rộng)
   Constraint: `src != dst` (no self-loop) qua `not` clause hoặc validate runtime.

5. **AC5 — Example file:** `contracts/examples/graph_snapshot_example.json` có ≥ 5 node (đủ 3 type) + ≥ 8 edge (đủ 3 edge_type), pass validate.

6. **AC6 — Unit test:** `tests/unit/test_graph_schema.py`:
   - 1 positive load example → pass
   - 4 negative: (a) thiếu `snapshot_id`, (b) `weight = 1.5`, (c) `edge_type = "unknown"`, (d) `node.features.connectivity = 2.0` — tất cả raise.

7. **AC7 — Loader:** `core/schemas/__init__.py` thêm `load_graph_schema()` + `validate_graph_snapshot(snap: dict) -> None`. Bổ sung reference runtime check `src`/`dst` ∈ node.id set và `src != dst` (raise `ValueError` với message rõ).

8. **AC8 — CI:** Test file được include trong pytest job đã setup ở Story 0.1.

## Tasks / Subtasks

- [x]**Task 1 — Viết schema** (AC 1-4)
  - [x]Header + $id
  - [x]Top-level 5 field + `additionalProperties: false`
  - [x]Sub-schema `$defs.node` với 5 feature
  - [x]Sub-schema `$defs.edge` với enum edge_type
  - [x]Ràng buộc weight [0,1], connectivity [0,1]

- [x]**Task 2 — Example file** (AC 5)
  - [x]2 protocol node (uniswap_v3, aave_v3)
  - [x]2 pool node (USDC/ETH, AAVE Pool)
  - [x]2 token node (USDC, WETH)
  - [x]Edge: pool→token (liquidity_flow), pool→pool (shared_collateral), user_position ghi qua borrow_position

- [x]**Task 3 — Loader mở rộng** (AC 7)
  - [x]Cache schema
  - [x]Runtime check node.id unique
  - [x]Runtime check edge.src/dst tồn tại trong node.id set
  - [x]Runtime check src != dst

- [x]**Task 4 — Test** (AC 6)
  - [x]1 positive + 4 negative
  - [x]1 test riêng cho runtime check (dangling edge → raise)

- [x]**Task 5 — Update sprint-status.yaml**

## Dev Notes

### Bối cảnh

Đây là **gate cho Track 3A/3B/3C/3D** — mọi story trong Epic 3 dùng mock GraphSnapshot làm input cho MPS forward. Nếu schema sai, phải rework toàn bộ Epic 3.

### Ràng buộc kiến trúc

- **AD-2:** Ring buffer 10 blocks in-memory — snapshot chứa `block_range` để buffer có thể lưu trữ và evict theo FIFO.
- **AD-5:** Node type + edge_type phản ánh Uniswap/Aave surface — không thêm type chưa có FR.

### Quyết định thiết kế

1. **Features là 5 float cố định**, KHÔNG dùng object tự do — vì Epic 2/3 build tensor với shape `(N, 5)` fixed. Thêm feature mới = breaking change.

2. **Edge reference bằng string node.id, không phải index** — dễ debug, JSON self-describing. Tensor builder tự map id→index deterministic (sort id).

3. **Runtime dangling-edge check TÁCH RỜI schema:** JSON Schema pure không tham chiếu chéo giữa array item, nên loader phải làm.

4. **`snapshot_id` UUID v4:** Deterministic hash của block_range không dùng vì snapshot có thể re-generate với cùng block khác trọng số.

### LLM-mistake prevention

- **KHÔNG dùng `type: number` cho tvl mà thiếu `minimum: 0`** — âm sẽ phá bình phương frobenius norm downstream.
- **KHÔNG cho phép `connectivity > 1`** — nhiều dev để [0,∞) vì "connectivity là count"; ở đây phải normalize.
- **KHÔNG quên `additionalProperties: false` cho features** — Epic 2 sẽ thêm field debug, nhưng phải qua PR sửa schema chứ không silent.
- **KHÔNG dùng JSON pointer `$ref` cross-file** cho node/edge — inline trong `$defs` để 1 file self-contained.

### Files tạo mới

- `contracts/graph_snapshot.schema.json`
- `contracts/examples/graph_snapshot_example.json`
- `tests/unit/test_graph_schema.py`

### Files update

- `core/schemas/__init__.py` — thêm `load_graph_schema`, `validate_graph_snapshot`
- `_bmad-output/sprint-status.yaml`

### References

- [Source: _bmad-output/architecture/architecture-mps-defi-risk/ARCHITECTURE-SPINE.md#AD-2] — Ring buffer state
- [Source: _bmad-output/epics.md#Story-0.2] — AC gốc
- [Source: _bmad-output/implementation-artifacts/0-1-tick-data-json-schema.md] — Convention loader + test setup (dùng lại)
- JSON Schema $defs: https://json-schema.org/understanding-json-schema/structuring#defs

## Dev Agent Record

### Agent Model Used
Claude (bmad-dev-story workflow, 2026-07-05).

### Debug Log References
- `pytest tests/ -v` → 29/29 passed (13 tick + 16 graph) in 0.08s.

### Completion Notes List
- Schema `contracts/graph_snapshot.schema.json` Draft 2020-12: top-level 5 required fields, node with 5-feature dict (`tvl_usd`, `volume_24h_usd`, `price_usd`, `volatility`, `connectivity∈[0,1]`), edge with 3 edge_types + optional `metadata` (open dict). `additionalProperties: false` at object + features level (AC1-AC4).
- Example `contracts/examples/graph_snapshot_example.json`: 6 nodes (2 protocol + 2 pool + 2 token) và 8 edges (đủ 3 edge_type). Verified positive validation. (AC5)
- Loader `core/schemas/__init__.py` mở rộng: `load_graph_schema()` lru_cache + `validate_graph_snapshot()` chạy schema validate rồi runtime invariants: `end >= start`, unique node ids, dangling edge check, self-loop rejection (AC7).
- Test suite 16 test cho graph: 4 positive (validate + covers all types) + 4 required negative (AC6: missing snapshot_id, weight=1.5, edge_type=unknown, connectivity=2.0) + 5 runtime invariant + 3 guardrail (empty nodes, additional feature, bad UUID pattern).
- `_find_contracts_root(sentinel)` từ Story 0.1 được tổng quát hoá để nhận sentinel path — reuse cho cả tick + graph schema.

### File List

**Tạo mới:**
- `contracts/graph_snapshot.schema.json`
- `contracts/examples/graph_snapshot_example.json`
- `tests/unit/test_graph_schema.py`

**Update:**
- `core/schemas/__init__.py` — thêm `load_graph_schema()`, `validate_graph_snapshot()`, generalize `_find_contracts_root(sentinel)`
- `_bmad-output/sprint-status.yaml` — 0-2 → review

## Change Log

| Date | Change | Author |
| --- | --- | --- |
| 2026-07-05 | Story 0.2 implemented: graph schema + example (6N/8E) + loader with runtime dangling/self-loop check + 16 tests. Status → review. | dev-story (Claude) |
| 2026-07-05 | Code-review fixes: (1) added `maxProperties: 32` to edge.metadata (DOS guard); (2) reversed runtime check order — membership before self-loop, so dangling refs surface with clearer message; (3) removed placeholder `allOf` block; (4) added 2 tests (top-level additionalProperties reject + metadata maxProperties). 18/18 graph + 13/13 tick = 31/31 pass. Status → done. | code-review (Claude) |
