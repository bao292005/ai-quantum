---
baseline_commit: a56e3f6
type: build
---

# Story 2A.3: Graph Builder (events → GraphSnapshot)

Status: review

## Story

As a **Kỹ sư AI**,
I want **function `build_graph(events) -> GraphSnapshot` dựng đồ hình DeFi state (nodes + typed edges + weights) từ list tick-data events bằng NetworkX**,
so that **raw events (Track 1B/1D) được convert thành `GraphSnapshot` khớp contract 0.2 để Track 2B (tensor) tiêu thụ**.

## Acceptance Criteria

1. **AC1 — API + package:** `engine/graph/builder.py` export `build_graph(events: list[dict], *, snapshot_id: str | None = None) -> dict` trả về một GraphSnapshot dict khớp `graph_snapshot.schema.json`. Input `events` là list dict tick-data (schema 0.1) — không phụ thuộc TickDataEvent class (1B trả dict). `networkx>=3` được thêm explicit vào `dependencies` trong `pyproject.toml`.

2. **AC2 — Node construction (2R.2 + 2A.1):** Từ events tạo node đúng 3 type (`protocol`, `pool`, `token`) theo whitelist/topology 2R.2. Mỗi node có đủ 5 feature (2A.1 `NodeFeatures`): `connectivity` = `degree(node)/(N-1)` (tính từ graph, khớp định nghĩa 2R.1/2R.2); `volume_24h_usd` tính từ swap events trong cửa sổ; các feature cần nguồn phụ (`tvl_usd`, `price_usd`, `volatility`) điền theo policy 2R.1 (proxy/0 + không vi phạm ràng buộc `≥0`). Node `id` theo convention `protocol:<name>` / `pool:<protocol>:<addr>` / `token:<addr>` (khớp example 0.2).

3. **AC3 — Edge construction (2R.2 + 2A.2 + 2A.4):** Tạo cạnh đúng 3 `edge_type` theo edge rules 2R.2; `weight ∈ [0,1]` tính bằng công thức Story 2A.4 (`research/edge_weight_formula.md`). Dùng `engine.graph.edge_types.Edge` để validate từng cạnh. `src`/`dst` phải trỏ tới node id tồn tại (không dangling, không self-loop — khớp runtime invariant của `validate_graph_snapshot`).

4. **AC4 — Round-trip schema:** Output của `build_graph(...)` PASS `core.schemas.validate_graph_snapshot(...)` (schema 0.2 + runtime invariants). Metadata edge dùng `model_dump(exclude_none=True)` để tránh `metadata: null`.

5. **AC5 — Benchmark:** `build_graph` xử lý **1000 events < 20ms** trên 1 CPU core (đo bằng test, cho phép ngưỡng nới trên CI chậm nhưng ghi rõ số đo thực).

6. **AC6 — Unit tests:** `tests/unit/test_graph_builder.py`: (a) build từ ≥100 mock events (fixture 0.4 hoặc synthetic) → PASS `validate_graph_snapshot`; (b) 3 node type + 3 edge type đều xuất hiện; (c) connectivity ∈ [0,1] và đúng degree; (d) 5 case biên weight khớp worked examples của 2A.4; (e) empty events → hành vi rõ ràng (raise hoặc snapshot rỗng hợp lệ — schema yêu cầu `nodes minItems:1`, nên empty → raise `ValueError` rõ nghĩa); (f) benchmark test (AC5).

## Tasks / Subtasks

- [x] **Task 1 — pyproject + skeleton** (AC1)
  - [x] Thêm `networkx>=3` vào `dependencies`
  - [x] `engine/graph/builder.py` với signature `build_graph(events, *, snapshot_id=None) -> dict`
- [x] **Task 2 — Node builder** (AC2)
  - [x] Gom events → tập node (protocol/pool/token) theo topology 2R.2
  - [x] Tính `volume_24h_usd` (từ swap), `connectivity` (degree/(N-1)); feature nguồn-phụ theo policy 2R.1
  - [x] Validate mỗi node bằng `engine.graph.node_types.Node`
- [x] **Task 3 — Edge builder + weight** (AC3)
  - [x] Sinh cạnh 3 loại theo edge rules 2R.2
  - [x] Gán `weight` theo công thức 2A.4; guard chia-0; đảm bảo ∈ [0,1]
  - [x] Validate mỗi cạnh bằng `engine.graph.edge_types.Edge`; loại self-loop / dangling
- [x] **Task 4 — Assemble + round-trip** (AC4)
  - [x] Ghép snapshot (snapshot_id uuid4, block_range từ min/max block, created_at ISO Z)
  - [x] `validate_graph_snapshot(snap)` phải PASS
- [x] **Task 5 — Tests + benchmark** (AC5, AC6)
  - [x] `tests/unit/test_graph_builder.py` theo AC6; benchmark 1000 events < 20ms

## Dev Notes

**Loại story:** `[BUILD]` — story tích hợp lớn nhất Track 2A: nối 2A.1 (Node), 2A.2 (Edge), 2R.1 (features), 2R.2 (topology), 2A.4 (weight) thành builder hoàn chỉnh. **Chặn 2B.*** (tensor cần GraphSnapshot thật để test).

**⚠️ Phụ thuộc — làm SAU 2A.4:** cần công thức weight từ `research/edge_weight_formula.md`. Nếu 2A.4 chưa done → HALT hoặc dùng công thức tạm và ghi rõ TODO.

**⚠️ Dependency mới:** `networkx>=3` (đã cài sẵn trong env, nhưng phải khai explicit vào `pyproject.toml dependencies`). NetworkX dùng để: dựng graph, tính `degree` cho `connectivity`, và (tuỳ) hỗ trợ topology. Output cuối là **dict GraphSnapshot** (không phải nx.Graph) — nx chỉ là công cụ trung gian.

**Feature-population scope (chốt theo 2R.1):**
- `connectivity`: tính THẬT từ graph = `degree(node)/(N-1)`, clamp [0,1]; N=1 → 0.
- `volume_24h_usd`: sum |amount| swap của node trong cửa sổ (token-volume proxy nếu chưa có price USD — ghi rõ, 2R.1 đã flag).
- `tvl_usd`, `price_usd`, `volatility`: cần nguồn phụ (reserve state / price series) — v1 điền **proxy hoặc 0.0** + warning, KHÔNG vi phạm `≥0`. Đầy đủ chính xác là việc của 2B.2 / story sau. Ghi rõ đây là giới hạn v1.

**Contract PHẢI bám:** `graph_snapshot.schema.json` — nodes `minItems:1`, edges `minItems:0`, node features 5 field, edge weight [0,1], `additionalProperties:false`. Runtime invariants (`validate_graph_snapshot`): unique node id, no dangling edge, no self-loop, block_range.end≥start.

**Tái dùng:**
- `engine.graph.node_types.Node/NodeFeatures`, `engine.graph.edge_types.Edge` (2A.1/2A.2) — validate từng phần tử; `model_dump(exclude_none=True)` khi ghép edge (tránh `metadata: null` — xem review note 2A.2 D2).
- `core.schemas.validate_graph_snapshot` cho round-trip.
- Whitelist: `ingestion/whitelist.yaml` (map pool→protocol, token0/1).
- Fixtures mock events: `fixtures/backtest/*.csv.gz` (qua `ingestion/csv_loader`) hoặc synthetic events dict.

**Performance (AC5):** 1000 events < 20ms → tránh vòng lặp O(N²) không cần; dùng dict/set gom node, networkx degree O(E). Đo bằng `time.perf_counter` trong test, ghi số thực.

**Testing:** pytest sync. `from engine.graph.builder import build_graph`.

### Project Structure Notes

```
engine/graph/
  builder.py              ← NEW (build_graph)
tests/unit/
  test_graph_builder.py   ← NEW
pyproject.toml            ← UPDATE (dependencies += networkx>=3)
```

### References

- Contract: `contracts/graph_snapshot.schema.json`
- Models: `engine/graph/node_types.py` (2A.1), `engine/graph/edge_types.py` (2A.2)
- Topology + edge rules: `research/graph_topology.md` (2R.2)
- Feature policy: `research/feature_catalog.md` (2R.1)
- Weight formula: `research/edge_weight_formula.md` (2A.4)
- Validator: `core/schemas/__init__.py` (`validate_graph_snapshot`)
- Epic 2 Track 2A: `_bmad-output/epics.md#Story 2A.3`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story)

### Debug Log References

`tests/unit/test_graph_builder.py` 12 passed. **Benchmark: build_graph(1000 events) = 2.32 ms**
(AC5 target <20ms — met with large margin). Full suite **301 passed, 1 skipped** (mock WSS), 0 regressions.

### Completion Notes List

- **AC1:** `engine/graph/builder.py` → `build_graph(events, *, snapshot_id=None) -> dict`.
  `networkx>=3` added to pyproject `dependencies` (was already installed transitively).
  Input is list of plain event dicts (schema 0.1); no TickDataEvent dependency.
- **AC2 (nodes, 2R.2 + 2A.1 + 2R.1):** protocol/pool/token nodes; ids `protocol:<p>` /
  `pool:<p>:<addr>` / `token:<addr>`. `connectivity = degree(node)/(N-1)` via NetworkX
  (N=1→0, clamped [0,1]); `volume_24h_usd` = token-native volume proxy. Per 2R.1 v1 policy,
  `tvl_usd`/`price_usd`/`volatility` emitted as `0.0` (need reserve/price aux data — flagged).
  Zero-address tokens skipped. Each node validated via `Node`.
- **AC3 (edges, 2R.2 + 2A.2 + 2A.4):** `liquidity_flow` (protocol→pool, DEX pool→token),
  `borrow_position` (Aave pool→reserve), `shared_collateral` (pool↔pool via shared token,
  exposure=min). Weight = `raw/max_raw`, `raw = volume·exp(-λΔt)·corr` (λ=ln2/3600, corr per
  2A.4); div-0 guard → 0. Each edge validated via `Edge(...).model_dump(exclude_none=True)`
  (avoids `metadata: null` per 2A.2 review note).
- **AC4:** `validate_graph_snapshot(snapshot)` called inside `build_graph` (schema + runtime
  invariants: unique ids, no dangling/self-loop, block_range). snapshot_id uuid4, block_range
  from min/max block, created_at ISO-Z.
- **AC5:** 1000-event benchmark measured at **2.32 ms** (well under 20ms).
- **AC6:** 12 tests — round-trip, all 3 node + 3 edge types, connectivity range + exact
  degree (`token:W` = 2/8), weights ∈[0,1], max weight=1.0, time-decay ordering, zero-volume→0,
  edge_type corr ordering (liquidity_flow > borrow_position), empty→ValueError, benchmark.

**v1 limitation (documented):** `tvl_usd`/`price_usd`/`volatility` are `0.0` placeholders
pending Story 2B.2 / reserve-state + price sourcing (per 2R.1). `volume_24h_usd` is
token-native (no USD anchor yet).

### Change Log

| Date | Change |
|---|---|
| 2026-07-26 | Added `engine/graph/builder.py` `build_graph()`: events→GraphSnapshot via NetworkX, nodes+3 edge types per 2R.2, weights per 2A.4 formula, connectivity=degree/(N-1); 12 tests incl. 1000-event benchmark (2.32ms). pyproject `networkx>=3`. Status → review. |

### File List

- `engine/graph/builder.py` (NEW)
- `tests/unit/test_graph_builder.py` (NEW)
- `pyproject.toml` (UPDATE)
