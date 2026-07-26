---
baseline_commit: ae1732c
type: build
---

# Story 2A.2: Edge Type Schema

Status: ready-for-dev

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

- [ ] **Task 1 — Define `Edge` model** (AC2, AC3)
  - [ ] `edge_type: Literal[...]` (3 giá trị snake_case y hệt schema)
  - [ ] `weight: float = Field(ge=0, le=1)`
  - [ ] `src/dst: str = Field(min_length=1, max_length=128)`
  - [ ] `metadata: dict | None = None`; validator giới hạn ≤ 32 keys
  - [ ] `model_config = ConfigDict(extra="forbid")`
- [ ] **Task 2 — Round-trip validation** (AC4)
  - [ ] `model_dump(exclude_none=True)` → validate trong GraphSnapshot tối thiểu (1 node + 1 edge) qua jsonschema
- [ ] **Task 3 — Unit tests** (AC5)
  - [ ] `tests/unit/test_edge_types.py`: 3 positive + ≥4 negative + 1 round-trip

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

### Debug Log References

### Completion Notes List

### File List

- `engine/graph/edge_types.py` (NEW)
- `tests/unit/test_edge_types.py` (NEW)
