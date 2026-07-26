---
baseline_commit: ae1732c
type: build
---

# Story 2A.2: Edge Type Schema

Status: in-progress

## Story

As a **Kỹ sư AI**,
I want **định nghĩa edge type (`liquidity_flow`, `borrow_position`, `shared_collateral`) bằng Pydantic model trong `engine/graph/edge_types.py`**,
so that **entanglement giữa các node được biểu diễn đúng, validated, và khớp contract `graph_snapshot.schema.json` cho Story 2A.3 (Graph Builder) + 2B.1 (Adjacency Tensor)**.

## Acceptance Criteria

1. **AC1 — File tồn tại:** `engine/graph/edge_types.py` được tạo (package `engine/graph/` đã có từ Story 2A.1).

2. **AC2 — Edge model:** export Pydantic v2 model `Edge` với fields khớp schema 0.2 `#/$defs/edge`:
   - `src: str` (minLength 1, maxLength 128)
   - `dst: str` (minLength 1, maxLength 128)
   - `weight: float` (`0 <= weight <= 1`)
   - `edge_type: Literal["liquidity_flow", "borrow_position", "shared_collateral"]`
   - `metadata: dict | None` (optional; nếu có, ≤ 32 keys)

3. **AC3 — Invariant `weight >= 0` (và `<= 1`):** `Edge(weight=-0.1)` và `Edge(weight=1.1)` raise `ValidationError`. `metadata` > 32 keys raise `ValidationError`.

4. **AC4 — Round-trip khớp schema:** `Edge(...).model_dump(exclude_none=True)` tạo dict validate PASS qua `graph_snapshot.schema.json` (edge nằm trong GraphSnapshot.edges[]).

5. **AC5 — Unit tests:** `tests/unit/test_edge_types.py`: tạo 1 edge mỗi type (3 loại) validate OK; negative case (edge_type sai, weight=-0.1, weight=1.1, metadata 33 keys) raise `ValidationError`; 1 round-trip test khớp schema 0.2.

## Tasks / Subtasks

- [x] **Task 1 — Define `Edge` model** (AC2, AC3)
  - [x] `edge_type: Literal[...]` (3 giá trị snake_case y hệt schema)
  - [x] `weight: float = Field(ge=0, le=1)`
  - [x] `src/dst: str = Field(min_length=1, max_length=128)`
  - [x] `metadata: dict | None = None`; validator giới hạn ≤ 32 keys
  - [x] `model_config = ConfigDict(extra="forbid")`
- [x] **Task 2 — Round-trip validation** (AC4)
  - [x] `model_dump(exclude_none=True)` → validate trong GraphSnapshot tối thiểu (1 node + 1 edge) qua jsonschema
- [x] **Task 3 — Unit tests** (AC5)
  - [x] `tests/unit/test_edge_types.py`: 3 positive + ≥4 negative + 1 round-trip

### Review Findings (code review 2026-07-26)

- [ ] [Review][Decision] `metadata=None` → plain `model_dump()` emits `{"metadata": null}` which fails schema (`metadata` is `type: object`, no null). Round-trip only safe via `model_dump(exclude_none=True)`. Decide: enforce with a serializer vs document the exclude_none consumer convention. [engine/graph/edge_types.py]
- [ ] [Review][Decision] Lax type coercion on `weight` (`True→1.0`, `"0.5"→0.5`) — same tradeoff as 2A.1. [engine/graph/edge_types.py]
- [ ] [Review][Patch] Add `allow_inf_nan=False` to `weight` for consistency with 2A.1 (bounded `le=1` already blocks `+inf`, so low risk). [engine/graph/edge_types.py]
- [x] [Review][Defer] `metadata` value depth/size unbounded (`dict[str, Any]`) — consistent with locked schema `additionalProperties: true`; downstream MAY drop (contract-level). [engine/graph/edge_types.py]
- [x] [Review][Defer] Whitespace-only `src`/`dst` accepted (contract-level, no schema pattern). [engine/graph/edge_types.py]

## Dev Notes

**Loại story:** `[BUILD]` — **KHÔNG bị research chặn**. Edge type đã khoá cứng trong contract 0.2 → độc lập hoàn toàn, chạy song song với 2A.1/2B.1 được.

**⚠️ Tên enum:** dùng ĐÚNG snake_case của schema — `liquidity_flow`, `borrow_position`, `shared_collateral` (KHÔNG phải CamelCase `LiquidityFlow` như tên mô tả trong epics.md). Contract là nguồn chân lý.

**Contract PHẢI bám (đã khoá):** `contracts/graph_snapshot.schema.json` `#/$defs/edge`
- `required: ["src", "dst", "weight", "edge_type"]`, `additionalProperties: false`.
- `weight`: number, `minimum: 0`, `maximum: 1`.
- `edge_type` enum: 3 giá trị snake_case ở trên.
- `metadata`: object optional, `additionalProperties: true`, `maxProperties: 32`, downstream MAY drop.

**Phụ thuộc 2A.1:** package `engine/graph/` + pattern Pydantic (ConfigDict extra="forbid", Field constraints) đã thiết lập ở Story 2A.1 — TÁI DÙNG, không dựng lại skeleton. Nếu 2A.1 chưa land → tạo `engine/__init__.py`+`engine/graph/__init__.py` (và cập nhật pyproject `include += engine*`, `pydantic>=2`) như 2A.1 mô tả.

**metadata 32-key guard (Pydantic v2):**
```python
from pydantic import field_validator
@field_validator("metadata")
@classmethod
def _max_32(cls, v):
    if v is not None and len(v) > 32:
        raise ValueError("metadata exceeds 32 keys")
    return v
```

**Không bị ảnh hưởng bởi 2A.4 (edge WEIGHT formula):** Story này chỉ định nghĩa STRUCTURE + range [0,1] của edge. Công thức TÍNH weight (2A.4 `[RESEARCH]`) được áp ở Story 2A.3 (Graph Builder), KHÔNG ở đây.

**Testing:** pytest sync. `from engine.graph.edge_types import Edge`.

### Project Structure Notes

```
engine/graph/
  edge_types.py           ← NEW (Edge model)
tests/unit/
  test_edge_types.py      ← NEW
```
Nếu 2A.1 chưa chạy: cũng cần `engine/__init__.py`, `engine/graph/__init__.py`, pyproject update (xem 2A.1).

### References

- Contract: `contracts/graph_snapshot.schema.json#/$defs/edge`
- Story 2A.1 (Pydantic pattern + engine skeleton): `_bmad-output/implementation-artifacts/2A-1-node-type-schema.md`
- Epic 2 Track 2A: `_bmad-output/epics.md#Story 2A.2`
- Edge WEIGHT formula (áp ở 2A.3, không phải story này): `_bmad-output/epics.md#Story 2A.4`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story)

### Debug Log References

Full suite green: **289 passed, 1 skipped** (mock WSS :8546 — pre-existing),
0 regressions. New: `tests/unit/test_edge_types.py` 13 passed.

### Completion Notes List

- **AC1/AC2:** `engine/graph/edge_types.py` — `Edge` (`src`/`dst` 1..128,
  `weight: float ge=0 le=1`, `edge_type: Literal[liquidity_flow|borrow_position|shared_collateral]`
  snake_case per contract, `metadata: dict|None`). `ConfigDict(extra="forbid")`.
  Exported `EdgeType` alias. Reused the `engine/graph/` skeleton from 2A.1 (no
  re-scaffold needed).
- **AC3:** `weight` bounds via `Field(ge=0, le=1)`; `metadata` >32 keys rejected
  via `@field_validator` (`_MAX_METADATA_KEYS=32`).
- **AC4:** Round-trip embeds `edge.model_dump(exclude_none=True)` into a minimal
  2-node + 1-edge GraphSnapshot and validates via
  `core.schemas.validate_graph_snapshot` (edge src/dst reference real node ids to
  pass the runtime dangling-edge invariant). Second round-trip test confirms
  `exclude_none` drops `metadata` cleanly (schema does not require it).
- **AC5:** 13 tests — 3 positive (one per edge type) + boundary weight 0/1 +
  metadata-at-limit(32), 6 negative (bad edge_type incl. CamelCase, weight -0.1,
  weight 1.1, metadata 33 keys, empty src, extra field), 2 round-trip.

### Change Log

| Date | Change |
|---|---|
| 2026-07-26 | Added `Edge` Pydantic v2 model matching locked `graph_snapshot.schema.json#/$defs/edge` (snake_case edge types, weight [0,1], metadata ≤32-key guard); 13 unit tests incl. round-trip. Reused 2A.1 engine skeleton. Status → review. |

### File List

- `engine/graph/edge_types.py` (NEW)
- `tests/unit/test_edge_types.py` (NEW)
