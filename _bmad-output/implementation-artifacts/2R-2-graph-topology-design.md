---
baseline_commit: ae1732c
type: research
---

# Story 2R.2: Graph Topology Design

Status: review

## Story

As a **Kỹ sư AI**,
I want **chốt cách dựng đồ hình DeFi state graph: loại node, quy tắc nối cạnh, kích thước N kỳ vọng lúc runtime, và độ thưa (sparsity)**,
so that **quyết định được tensor shape cho Track 2B (2B.1 adjacency `N×N`, 2B.2 feature `N×F`) và xác định có cần sparse variant (2B.4) cho v1 hay không**.

## Acceptance Criteria

1. **AC1 — Sơ đồ mẫu:** `research/graph_topology.md` chứa 1 sơ đồ đồ hình đại diện (mermaid hoặc mô tả node/edge) dựng từ scope whitelist thật (Story 1B.3 / E.2): Uniswap V3 pool `0x88e6…5640`, Aave V3 Pool `0x87870B…4E2`, (+ Aave V2 `0x7d2768…c7A9` cho backtest).

2. **AC2 — Node & edge rule chốt:** Nêu rõ dùng đúng enum của contract `graph_snapshot.schema.json`:
   - Node types: `protocol`, `pool`, `token`.
   - Edge types: `liquidity_flow`, `borrow_position`, `shared_collateral`.
   - Quy tắc nối cạnh: khi nào tạo cạnh loại nào giữa 2 node (VD pool↔token = liquidity_flow; token dùng chung giữa 2 pool = shared_collateral; Aave borrow = borrow_position).

3. **AC3 — Ước lượng N + sparsity:** Ước lượng số node `N` lúc runtime cho scope v1 (3-5 pool + token + protocol) và ma trận sparsity ước lượng (% ô 0 trong adjacency `N×N`).

4. **AC4 — Khuyến nghị dense/sparse:** Kết bằng mục `## Decision`: (a) v1 dùng dense hay sparse, (b) ngưỡng N (hoặc % sparsity) mà tại đó nên chuyển sang sparse (2B.4), kèm lý do.

## Tasks / Subtasks

- [x] **Task 1 — Liệt kê node từ whitelist thật** (AC1, AC3)
  - [x] Từ whitelist (1B.3): các protocol, pool, token xuất hiện → đếm N ước lượng
- [x] **Task 2 — Định nghĩa quy tắc nối cạnh** (AC2)
  - [x] Map 3 edge_type của schema 0.2 vào quan hệ cụ thể (pool-token, token-token, borrow)
  - [x] Vẽ sơ đồ mẫu (mermaid) cho scope v1
- [x] **Task 3 — Ước lượng sparsity** (AC3)
  - [x] Tính % ô khác 0 trong adjacency `N×N` cho đồ hình mẫu
- [x] **Task 4 — Viết `research/graph_topology.md` + Decision** (AC1-AC4)
  - [x] Sơ đồ + N + sparsity + `## Decision` (dense/sparse + ngưỡng)

## Dev Notes

**Loại story:** `[RESEARCH]` P0 — output là document quyết định, KHÔNG code. **Chặn tensor shape 2B.*** và **quyết định 2B.4 (sparse) có cần v1 không**. Không test, không đụng pyproject.

**Contract đã khoá (PHẢI bám):** `contracts/graph_snapshot.schema.json`
- Node: `id`, `type ∈ {protocol, pool, token}`, `features{...}` (bộ feature do 2R.1 chốt).
- Edge: `src`, `dst`, `weight ∈ [0,1]`, `edge_type ∈ {liquidity_flow, borrow_position, shared_collateral}`, `metadata?`.
- → KHÔNG phát minh node/edge type mới; nếu cần thêm phải bump `$id` (breaking) — ghi khuyến nghị, không tự sửa.

**Scope thật (whitelist 1B.3 / E.2):**
- Uniswap V3 USDC/WETH pool `0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640`
- Aave V3 Pool `0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2`
- Aave V2 Pool `0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9` (chỉ backtest LUNA/FTX)

**Ước lượng N (v1, gợi ý):** ~2 protocol + 3-5 pool + ~5-8 token (WETH/USDC dùng chung) ≈ **15-25 node**. N nhỏ → adjacency `N×N` ≤ ~625 ô → **dense gần như chắc chắn đủ cho v1**; sparse (2B.4) chỉ cần khi mở rộng scope (v2, N ≥ vài trăm). Research xác nhận/điều chỉnh con số này.

**Liên hệ chéo:**
- **2R.1 (feature catalog):** feature `connectivity` = hàm của degree/số cạnh của node → định nghĩa NHẤT QUÁN với quy tắc cạnh ở story này.
- **2B.1/2B.2:** tensor shape `(N,N)` và `(N,F)` phụ thuộc N chốt ở đây.
- **2B.4 sparse:** quyết định "có làm v1 không" nằm ở AC4.
- **2A.2 (edge type schema) / 2A.3 (graph builder):** tiêu thụ quy tắc cạnh này khi build graph thật.

**Context có sẵn:** Event thật (Track 1B decoder) cho biết mỗi swap/borrow tạo quan hệ gì (pool↔token qua amount0/1; Aave borrow token↔pool). Dùng để suy ra cạnh.

### Project Structure Notes

```
research/
  graph_topology.md   ← output DUY NHẤT của story này (NEW)
```
Không tạo/sửa file code. Bump schema (nếu cần) chỉ ghi khuyến nghị.

### References

- Contract (node/edge enums): `contracts/graph_snapshot.schema.json`
- Whitelist scope: `_bmad-output/implementation-artifacts/E-2-contract-address-registry.md`, `ingestion/whitelist.yaml`
- Epic 2 Track 2R + Story 2B.1/2B.2/2B.4: `_bmad-output/epics.md#Story 2R.2`
- Story liên quan 2R.1: `_bmad-output/implementation-artifacts/2R-1-node-feature-catalog.md`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story)

### Debug Log References

Research-only story — no code/test. Grounded in `ingestion/whitelist.yaml`
(real scope) and `contracts/graph_snapshot.schema.json` (locked node/edge enums).

### Completion Notes List

- **AC1 (diagram):** Mermaid sample graph for realtime v1 (N=10) built from the
  real whitelist (2 Uniswap pools, Aave V3 pool, +Aave V2 backtest) mapping to
  the 3 locked node types.
- **AC2 (rules):** Locked edge rules using schema-0.2 enums —
  `liquidity_flow` (protocol→pool, pool→token), `borrow_position` (Aave pool→reserve),
  `shared_collateral` (pool↔pool via shared token = contagion channel). No new
  node/edge types; no `$id` bump.
- **AC3 (N + sparsity):** **N ≈ 10–15** for v1 (realtime ~10, +backtest ~13) —
  refined the story's 15–25 guess **downward** (WETH/USDC shared). Sample graph
  E=14 edges → adjacency density ~15–30% (sparsity ~70–85%). Dense matrix <1 KB
  at N≤15.
- **AC4 (Decision):** **v1 = DENSE** `(N,N)` + `(N,F=5)`. **Story 2B.4 (sparse)
  NOT needed for v1 → defer/optional.** Sparse trigger: N ≥ 512 (mandate) or
  N ≥ 128 evaluate, AND sparsity ≥ 90%.
- **Cross-story:** `connectivity` (2R.1) = `degree(node)/(N−1)` using undirected
  incident edges under these rules — keep identical in 2B.2. Tensor shapes are
  dynamic per snapshot (don't hard-code N).

### Change Log

| Date | Change |
|---|---|
| 2026-07-26 | Created `research/graph_topology.md`: node/edge rules (schema-0.2 enums), sample mermaid graph, N≈10–15, sparsity ~70–85%, Decision = dense for v1 (2B.4 deferred; sparse threshold N≥512 & sparsity≥90%). Status → review. |

### File List

- `research/graph_topology.md` (NEW)
