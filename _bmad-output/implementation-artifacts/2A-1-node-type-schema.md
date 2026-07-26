---
baseline_commit: ae1732c
type: build
---

# Story 2A.1: Node Type Schema

Status: in-progress

## Story

As a **Kỹ sư AI**,
I want **định nghĩa node type (`protocol`, `pool`, `token`) bằng Pydantic model trong `engine/graph/node_types.py`**,
so that **graph có typology rõ ràng, validated, và khớp đúng contract `graph_snapshot.schema.json` để Story 2A.3 (Graph Builder) + 2B.* (Tensor) tiêu thụ**.

## Acceptance Criteria

1. **AC1 — Package `engine/graph/` tồn tại:** `engine/__init__.py`, `engine/graph/__init__.py`, `engine/graph/node_types.py` được tạo. `engine*` được thêm vào `[tool.setuptools.packages.find] include` trong `pyproject.toml`.

2. **AC2 — Node model:** `engine/graph/node_types.py` export Pydantic v2 model `Node` với fields:
   - `id: str` (minLength 1, maxLength 128 — khớp schema 0.2)
   - `type: Literal["protocol", "pool", "token"]` (khớp enum schema 0.2)
   - `features: NodeFeatures` (model con, xem AC3)

3. **AC3 — Features model khớp contract:** `NodeFeatures` (Pydantic model) có ĐÚNG các field mà `contracts/graph_snapshot.schema.json` `#/$defs/node/features` quy định — hiện tại: `tvl_usd`, `volume_24h_usd`, `price_usd`, `volatility` (`>= 0`), `connectivity` (`0..1`). Nếu Story 2R.1 đã chốt bộ feature khác → dùng bộ đã chốt (đọc `research/feature_catalog.md`).

4. **AC4 — Validation & round-trip:** `Node.model_validate(d)` reject input sai (type ngoài enum, feature thiếu, connectivity > 1); `Node(...).model_dump()` tạo dict validate PASS qua `graph_snapshot.schema.json` (dùng validator draft 2020-12 như các story 0.x).

5. **AC5 — Unit tests:** `tests/unit/test_node_types.py`: tạo 3 node mỗi type (protocol/pool/token) validate OK; ít nhất 3 negative case (type sai, feature thiếu, connectivity=1.5) raise `ValidationError`; 1 test round-trip `model_dump()` khớp schema 0.2.

## Tasks / Subtasks

- [x] **Task 1 — Dựng package `engine/`** (AC1)
  - [x] Tạo `engine/__init__.py`, `engine/graph/__init__.py` (rỗng)
  - [x] Thêm `"engine*"` vào `include` của `[tool.setuptools.packages.find]` trong `pyproject.toml`
  - [x] Thêm `pydantic>=2` vào `dependencies` trong `pyproject.toml` (hiện chỉ có transitively qua web3 — khai explicit)
- [x] **Task 2 — Define models** (AC2, AC3)
  - [x] `NodeFeatures(BaseModel)` với 5 field + constraints (dùng `Field(ge=0)`, `Field(ge=0, le=1)`)
  - [x] `Node(BaseModel)` với `id`, `type: Literal[...]`, `features: NodeFeatures`
  - [x] `model_config = ConfigDict(extra="forbid")` để khớp `additionalProperties: false` của schema
- [x] **Task 3 — Round-trip validation** (AC4)
  - [x] `model_dump()` → dict khớp schema 0.2 (test bằng jsonschema validator)
- [x] **Task 4 — Unit tests** (AC5)
  - [x] `tests/unit/test_node_types.py`: 3 node/type positive, 3 negative, 1 round-trip

### Review Findings (code review 2026-07-26)

- [ ] [Review][Decision] Lax type coercion on NodeFeatures floats — pydantic v2 default (lax) accepts `True→1.0` and `"0.5"→0.5`. `strict=True` would also reject legit `int→float` (e.g. `tvl_usd=100`). [engine/graph/node_types.py]
- [ ] [Review][Patch] `inf` accepted on unbounded feature floats — `tvl_usd`/`volume_24h_usd`/`price_usd`/`volatility` accept `float('inf')` (verified); survives `model_dump()` + Python jsonschema; `json.dumps` emits non-standard `Infinity`. Fix: `Field(..., allow_inf_nan=False)`. [engine/graph/node_types.py:32-36]
- [x] [Review][Defer] Whitespace-only `id` accepted — `min_length=1` allows `" "`; locked schema has no `pattern` either (contract-level, not this change). [engine/graph/node_types.py]

## Dev Notes

**Loại story:** `[BUILD]` — story ĐẦU TIÊN dựng package `engine/`. Các story 2A/2B sau build tiếp trên skeleton này.

**⚠️ Coordination (scaffolding):** `engine/` CHƯA tồn tại. Story này tạo skeleton `engine/__init__.py` + `engine/graph/__init__.py`. Nếu chạy song song với 2A.2/2B.1 → story này nên land TRƯỚC để tránh conflict `__init__.py` (đã bàn trong phân tích parallel).

**⚠️ pyproject — 2 thay đổi bắt buộc:**
- `[tool.setuptools.packages.find]` hiện `include = ["core*", "tools*", "ingestion*"]` → **PHẢI thêm `"engine*"`** nếu không package không được đóng gói (`pip install -e .` bỏ sót engine).
- `pydantic>=2` khai explicit vào `dependencies` (đã có sẵn 2.12.5 transitively qua web3 7.16, nhưng không nên phụ thuộc transitive).

**Contract PHẢI bám (đã khoá):** `contracts/graph_snapshot.schema.json` `#/$defs/node`
- `required: ["id", "type", "features"]`, `additionalProperties: false`.
- `type` enum: `protocol | pool | token` (lowercase).
- `features` required 5 field: `tvl_usd`, `volume_24h_usd`, `price_usd` (number ≥ 0), `volatility` (≥ 0), `connectivity` (0..1). `additionalProperties: false`.
- `id`: string 1..128 ký tự.

**Phụ thuộc 2R.1:** Bộ feature ở AC3 phải khớp quyết định của Story 2R.1 (`research/feature_catalog.md`). Nếu 2R.1 CHƯA done → dùng bộ 5 feature schema 0.2 (mặc định an toàn vì contract đã locked). Nếu 2R.1 đổi bộ feature → cần cập nhật schema 0.2 song song (breaking, bump `$id`) — coordination với 2R.1.

**Pydantic v2 patterns:**
```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class NodeFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tvl_usd: float = Field(ge=0)
    volume_24h_usd: float = Field(ge=0)
    price_usd: float = Field(ge=0)
    volatility: float = Field(ge=0)
    connectivity: float = Field(ge=0, le=1)

class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=128)
    type: Literal["protocol", "pool", "token"]
    features: NodeFeatures
```

**Validator round-trip (tái dùng pattern story 0.x):** load `contracts/graph_snapshot.schema.json`, validate `Node(...).model_dump()` — nhưng schema là cho toàn GraphSnapshot; test node đơn bằng cách validate against `#/$defs/node` (dùng `jsonschema` với `$ref` resolver hoặc trích subschema). Đơn giản nhất: dựng 1 GraphSnapshot tối thiểu (1 node, 0 edge) và validate cả object.

**Testing:** pytest sync (không async). `from engine.graph.node_types import Node, NodeFeatures`.

### Project Structure Notes

```
engine/                       ← NEW package (story đầu tiên tạo)
  __init__.py                 ← NEW (rỗng)
  graph/
    __init__.py               ← NEW (rỗng)
    node_types.py             ← NEW (Node, NodeFeatures)
tests/unit/
  test_node_types.py          ← NEW
pyproject.toml                ← UPDATE (packages.find += engine*; dependencies += pydantic>=2)
```

### References

- Contract: `contracts/graph_snapshot.schema.json#/$defs/node`
- Feature decision (nếu có): `research/feature_catalog.md` (Story 2R.1)
- Epic 2 Track 2A: `_bmad-output/epics.md#Story 2A.1`
- Story format/pattern (schema+test): `_bmad-output/implementation-artifacts/1C-1-ring-buffer-interface.md`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story)

### Debug Log References

Full suite green: **276 passed, 1 skipped** (mock WSS :8546 not running — pre-existing),
0 regressions. New tests: `tests/unit/test_node_types.py` 11 passed.

### Completion Notes List

- **AC1:** Created `engine/` + `engine/graph/` packages (empty `__init__.py`).
  `pyproject.toml`: added `"engine*"` to `packages.find.include` and `pydantic>=2`
  to `dependencies` (was only transitive via web3).
- **AC2/AC3:** `engine/graph/node_types.py` — `Node` (`id` 1..128, `type: Literal[protocol|pool|token]`,
  `features: NodeFeatures`) + `NodeFeatures` with the **canonical 5-feature set
  from Story 2R.1** (schema-0.2): `tvl_usd`, `volume_24h_usd`, `price_usd`,
  `volatility` (`ge=0`), `connectivity` (`ge=0, le=1`). Both use
  `ConfigDict(extra="forbid")` to mirror `additionalProperties:false`.
  Exported `NodeType` alias too.
- **AC4:** Round-trip test embeds `Node(...).model_dump()` into a minimal
  GraphSnapshot (1 node, 0 edges) and validates via
  `core.schemas.validate_graph_snapshot` (reuses existing draft-2020-12 validator).
- **AC5:** 11 tests — 3 positive (one per node type) + boundary connectivity 0/1,
  6 negative (bad type, missing feature, connectivity>1, negative tvl, extra
  feature field, empty id), 1 round-trip.

### Change Log

| Date | Change |
|---|---|
| 2026-07-26 | Scaffolded `engine/graph/` package; added `Node`/`NodeFeatures` Pydantic v2 models matching locked `graph_snapshot.schema.json#/$defs/node` (5-feature canonical set per 2R.1); pyproject `engine*` + `pydantic>=2`; 11 unit tests. Status → review. |

### File List

- `engine/__init__.py` (NEW)
- `engine/graph/__init__.py` (NEW)
- `engine/graph/node_types.py` (NEW)
- `tests/unit/test_node_types.py` (NEW)
- `pyproject.toml` (UPDATE)
