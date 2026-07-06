---
baseline_commit: 186d98f8f25e4da0e1cd16100f350b9dd6f08ddc
---

# Story 0.3: Fragility Payload Schema

Status: done

## Story

As a **Backend Lead (Đội Emitter)**,
I want **định nghĩa JSON Schema chính thức cho Webhook payload tại `contracts/fragility_alert.schema.json`**,
so that **Track Epic 5 (Formatter + Emitter) và các consumer test song song mà không cần chờ Epic 4 calibration xong, đồng thời enforce contract AD-3 cho khách hàng bên ngoài**.

## Acceptance Criteria

1. **AC1 — Schema file:** `contracts/fragility_alert.schema.json` Draft 2020-12, `$id: "https://quantumradar.io/schemas/fragility_alert.schema.json"`.

2. **AC2 — Đúng 4 trường required (theo AD-3):**
   - `timestamp` (string, ISO 8601 UTC kết `Z`, pattern như Story 0.1)
   - `fragility_score` (number, `minimum: 0`, `maximum: 100`, `multipleOf: 0.01` → 2 chữ số thập phân)
   - `alert_level` (enum: `"YELLOW" | "RED"` — KHÔNG có "GREEN" vì chỉ emit khi vượt ngưỡng)
   - `trigger_protocols` (array, `minItems: 1`, items enum `"uniswap_v3" | "aave_v3"`, `uniqueItems: true`)
   `additionalProperties: false`.

3. **AC3 — Cross-field constraint:** Enforce qua `if/then`:
   - `alert_level == "YELLOW"` → `fragility_score >= 70 AND < 90`
   - `alert_level == "RED"` → `fragility_score >= 90`

4. **AC4 — 2 example hợp lệ:**
   - `contracts/examples/payload_yellow.json` (score = 75.42, level = YELLOW, protocols = [uniswap_v3])
   - `contracts/examples/payload_red.json` (score = 94.10, level = RED, protocols = [uniswap_v3, aave_v3])
   Cả 2 pass validate.

5. **AC5 — Unit test (`tests/unit/test_payload_schema.py`):**
   - 2 positive (load 2 example)
   - 6 negative:
     - Thiếu bất kỳ 1 trong 4 field → raise (4 test)
     - `alert_level = "YELLOW"` nhưng `score = 95` → raise (cross-field)
     - `trigger_protocols = []` → raise (minItems)

6. **AC6 — Loader:** `core/schemas/__init__.py` thêm `validate_alert_payload(payload: dict) -> None`.

7. **AC7 — Downstream reference:** Trong file schema có `description` note rõ: "Consumer contract theo AD-3 SPEC — bất kỳ thay đổi nào là breaking change, yêu cầu bump `$id` version".

## Tasks / Subtasks

- [x]**Task 1 — Schema** (AC 1-3)
  - [x]4 field với constraint đúng
  - [x]`allOf` khối `if/then` cho cross-field
  - [x]`additionalProperties: false`

- [x]**Task 2 — Example** (AC 4)
  - [x]`payload_yellow.json` + `payload_red.json`
  - [x]Timestamp thực tế (dùng UTC now hoặc mốc LUNA)

- [x]**Task 3 — Test** (AC 5)
  - [x]Setup pytest fixture dùng chung schema loader
  - [x]2 positive + 6 negative

- [x]**Task 4 — Loader** (AC 6)

- [x]**Task 5 — Update sprint-status**

## Dev Notes

### Bối cảnh

Đây là **contract public** — payload gửi ra webhook của khách hàng. Nếu sau này đổi, khách hàng phải update code. VÌ VẬY cần:
- Version qua `$id` URL (nếu breaking, đổi thành `v2.schema.json`)
- Cực kỳ ổn định, tối giản field

### Ràng buộc AD-3

Bám sát 4 field trong AD-3: `timestamp, fragility_score, alert_level, trigger_protocols`. KHÔNG thêm field khác (không thêm `pool_addresses` hay `explanation` — để v2).

### Quyết định thiết kế

1. **`multipleOf: 0.01`** để enforce 2 chữ số thập phân — tránh float scientific notation (`7.5e1`) làm khách hàng parse sai.

2. **`alert_level` UPPERCASE** — theo AD-3 examples. Không cho lowercase để tránh case-mismatch bug.

3. **KHÔNG có "GREEN":** khi score < 70 → không emit payload → schema không cần biết trạng thái green.

4. **`uniqueItems: true` cho protocols:** tránh `[uniswap_v3, uniswap_v3]`.

### LLM-mistake prevention

- **KHÔNG dùng `type: string` cho fragility_score** — dù thấy JSON API khác dùng string cho decimal, ở đây score bounded 0-100 nên float đủ precision.
- **KHÔNG cho `minItems: 0`** — payload không có protocol trigger là vô nghĩa.
- **KHÔNG quên `if/then`:** dev có thể để formatter tự do gán YELLOW/RED sai với score → schema là hàng rào cuối.
- **KHÔNG dùng `pattern` cho fragility_score** vì đây là number, pattern chỉ áp cho string.

### Files tạo mới

- `contracts/fragility_alert.schema.json`
- `contracts/examples/payload_yellow.json`
- `contracts/examples/payload_red.json`
- `tests/unit/test_payload_schema.py`

### Files update

- `core/schemas/__init__.py`
- `_bmad-output/sprint-status.yaml`

### References

- [Source: _bmad-output/architecture/architecture-mps-defi-risk/ARCHITECTURE-SPINE.md#AD-3] — 4 field contract
- [Source: _bmad-output/specs/spec-mps-defi-risk/SPEC.md#CAP-3] — FR4, FR5 canonical
- [Source: _bmad-output/epics.md#Story-0.3] — AC gốc
- [Source: _bmad-output/implementation-artifacts/0-1-tick-data-json-schema.md] — Loader convention

## Dev Agent Record

### Agent Model Used
Claude (bmad-dev-story workflow, 2026-07-05).

### Debug Log References
- `pytest tests/ -v` → 49/49 passed (13 tick + 18 graph + 18 alert) in 0.08s.

### Completion Notes List
- Schema `contracts/fragility_alert.schema.json` Draft 2020-12 with 4 required fields (`timestamp`, `fragility_score`, `alert_level`, `trigger_protocols`) and `additionalProperties: false` (AC1-AC2).
- Cross-field constraint via `allOf` + `if/then`: YELLOW → score∈[70,90), RED → score∈[90,100] (AC3).
- `fragility_score` uses `multipleOf: 0.01` to force ≤2 decimal precision; `trigger_protocols` enforces `minItems: 1` + `uniqueItems: true` (AD-3).
- 2 examples in `contracts/examples/` (yellow score=75.42 uniswap_v3; red score=94.10 uniswap_v3+aave_v3 with LUNA timestamp) (AC4).
- Loader `load_alert_schema()` + `validate_alert_payload()` follow Story 0.1/0.2 pattern with `lru_cache` (AC6).
- Test suite: 3 positive (2 examples + schema load), 4 missing-required (parametrized), 1 cross-field YELLOW-with-high-score, 1 minItems=0, plus 8 guardrails (RED-with-low-score, score>100, >2-decimals, lowercase level, GREEN rejected, unknown protocol, duplicate protocols, additional property, timestamp-without-Z) = 18 tests (AC5).
- Schema `description` explicitly flags AD-3 breaking-change policy: bump `$id` path instead of mutating (AC7).

### File List

**Tạo mới:**
- `contracts/fragility_alert.schema.json`
- `contracts/examples/payload_yellow.json`
- `contracts/examples/payload_red.json`
- `tests/unit/test_payload_schema.py`

**Update:**
- `core/schemas/__init__.py` — thêm `load_alert_schema()`, `_alert_validator()`, `validate_alert_payload()`, `_ALERT_SCHEMA_RELATIVE`
- `_bmad-output/sprint-status.yaml` — 0-3 → review

## Change Log

| Date | Change | Author |
| --- | --- | --- |
| 2026-07-05 | Story 0.3 implemented: fragility alert schema (4 fields + cross-field YELLOW/RED constraints) + 2 examples + loader + 18 tests. Status → review. | dev-story (Claude) |
| 2026-07-05 | Code-review complete: 1 P1 (`if`-clause guard hardening) + 2 P2 (boundary tests, timestamp) noted as deferred follow-ups; no blocking defects. Status → done. | code-review (Claude) |
