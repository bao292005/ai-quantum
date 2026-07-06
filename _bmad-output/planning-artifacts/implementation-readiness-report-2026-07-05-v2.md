---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - SPEC-mps-defi-risk (canonical)
  - ARCHITECTURE-SPINE.md
  - epics.md (v2-parallel-detailed, revision 2026-07-05)
  - sprint-status.yaml (77 entries)
  - 1-1-web3-rpc-websocket-connection.md (legacy story, superseded by Track 1A)
assessor: bmad-check-implementation-readiness
assessment_focus: "Verify v2 restructuring closed critical gaps + kiểm tra defect mới sinh"
previousReport: implementation-readiness-report-2026-07-05.md
---

# Implementation Readiness Assessment Report (v2)

**Date:** 2026-07-05
**Project:** QuantumRadar (ai-quantum)
**Delta from v1:** Epics v1 (16 stories, 5 epics, chuỗi tuyến tính) → v2 (62 stories, 7 epics, contract-first + 5 track song song)

---

## 1. Document Inventory

Không đổi so với v1. Bổ sung:
- `epics.md` revision **v2-parallel-detailed** (910 dòng, 62 stories)
- `sprint-status.yaml` cập nhật 77 entries theo cấu trúc mới
- `implementation-readiness-report-2026-07-05.md` (v1) làm baseline

---

## 2. PRD Analysis

Không đổi (SPEC vẫn là canonical). FR1–FR5 và NFR1–NFR5 giữ nguyên. **Success Signal** đã được lift lên `Additional Requirements` trong epics.md v2 — trước đây chỉ nằm trong SPEC.

---

## 3. Epic Coverage Validation

### Coverage Matrix (v2)

| FR / Signal | v1 Status | v2 Status | Story mới |
| --- | --- | --- | --- |
| FR1 (CSV + WSS) | ⚠️ Partial (thiếu CSV) | ✅ **Fixed** | Track 1D (1D.1–1D.3) |
| FR2 (Event filter) | ✅ | ✅ | Track 1B (1B.1–1B.4) — chi tiết hơn |
| FR3 (MPS) | ✅ | ✅ | Epic 2 + Epic 3 (27 stories) |
| FR4 (Yellow/Red) | ✅ | ✅ | Story 5.2, 5.3 |
| FR5 (JSON schema) | ✅ | ✅ **Nâng cấp** | Story 0.3 (schema) + 5.2 (formatter) |
| NFR1 (<50ms E2E) | ⚠️ Không có story test | ✅ **Fixed** | Story 6.1 |
| NFR2 (async) | ✅ | ✅ | Story 1A.2, 1C.4, 5.3 |
| NFR3 (multiprocess) | ✅ | ✅ | Story 4.3 |
| NFR4 (Ring RAM) | ✅ | ✅ | Track 1C |
| NFR5 (No GPU) | ⚠️ Ngầm định | ✅ **Fixed** | Story 6.2 |
| Success Signal | 🔴 CRITICAL GAP | ✅ **Fixed** | Story 4.1 (LUNA calibration + AC ngưỡng 10 phút) + Story 4.2 (FTX cross-val) + Story 6.3 (final proof) |

### Coverage Statistics

- Total FRs: 5 → **5/5 fully covered** (100%)
- NFRs: 5 → **5/5 covered với test story riêng**
- Success Signal: **3 story độc lập verify**

**Delta v1→v2: Đóng 100% critical & major coverage gap.**

---

## 4. UX Alignment

Không đổi — API-only product, không cần UX. Mâu thuẫn Brief vs SPEC về "Frontend Next.js Demo" **vẫn tồn tại** nhưng đã lock quyết định theo SPEC (không có Epic Frontend trong v2). **Recommendation:** chỉnh Brief để nhất quán.

---

## 5. Epic Quality Review (v2)

### 🔴 Critical Violations

**Không còn critical trong v2.** (v1 có 2: parallelization + success signal → đều đóng.)

### 🟠 Major Issues (mới phát sinh sau restructure)

**M1. Story-file backlog quá lớn — chỉ có 1/62 story có file chi tiết.**
- Story 1.1 (legacy) là ready-for-dev với đầy đủ Dev Context.
- 61 story mới chỉ có ~4-8 dòng trong epics.md.
- **Recommendation:** Chạy `bmad-create-story` batch cho ít nhất Epic 0 (5 story) trước khi khởi công.

**M2. Story 1.1 (legacy) chồng lấn Track 1A.**
- Sprint-status ghi cả `1-1-web3-rpc-websocket-connection: ready-for-dev` VÀ `1A-1-env-secrets-loader → 1A-5-heartbeat-metrics: backlog`.
- Story 1.1 legacy cover ~ Story 1A.1–1A.4, khác Story 1A.5 (heartbeat metrics).
- **Nguy cơ:** dev bị lẫn — làm cả legacy lẫn track mới → double work.
- **Recommendation:** Chọn 1 trong 2:
  - (a) Retire legacy 1-1 file, dùng 1A.1–1A.5;
  - (b) Giữ 1-1 = một tổng hợp Track 1A, chỉ tạo file 1A.5 (heartbeat) riêng.

**M3. Epic 0 story không đánh dấu là gate cho các Epic khác trong sprint-status.**
- Sprint-status không encode dependency "Track 1A blocked-by Story 0.1".
- **Nguy cơ:** dev pull story Track 2 trước khi 0.2 xong → thiếu contract.
- **Recommendation:** Thêm field `blocked_by:` cho mỗi track trong sprint-status hoặc note tại đầu file.

**M4. Story 3E.1 gate ngưỡng 30ms có thể quá chặt với baseline Track 3A.**
- Story 3A.1 dùng naive einsum, có thể p95 = vài trăm ms.
- Story 3B/3C/3D cần cắt giảm 90%+ để chạm gate.
- **Recommendation:** Story 3A.4 phải chốt baseline trước khi mở Story 3E.1 gate — đảm bảo không chặn CI vô lý.

**M5. Story 4.4 (Backpressure Circuit Breaker) sinh sau khi restructure — không có FR/NFR gốc.**
- Đây là good engineering nhưng không nằm trong SPEC.
- **Nguy cơ:** scope creep tương tự Story 1.6 Airflow trước đây.
- **Recommendation:** Confirm với PM: giữ hay dời v2.

### 🟡 Minor Concerns

**m1.** Chưa có story cho `contracts_whitelist.yaml` init (chỉ có Story 1B.3 load).
- Recommendation: gộp vào Story 1B.3 AC ("kèm file whitelist mẫu 3-5 pool").

**m2.** Story 5.4 (API Authentication) là mới — SPEC không nhắc.
- Nếu PoC internal-only, có thể defer. Nếu Enterprise ngay → giữ.

**m3.** Story 2C.3 (Nansen reference comparison) phụ thuộc dữ liệu ngoài — cần confirm nguồn public accessible.

**m4.** Persona "Data Analyst" chỉ xuất hiện ở Track 1D & 1E — cần confirm role này có trong team.

**m5.** Story 3D.2 (TorchScript compilation) yêu cầu "output bit-identical" — thực tế TorchScript có floating-point drift; nên nới sang `tolerance 1e-6`.

**m6.** Bảng Parallelization Guide ở cuối epics.md giả định **12 dev** — nếu team thực tế < 5 người, cần strategy khác (serialize track).

**m7.** Không có story dành cho **deployment** (Render/Railway theo PRFAQ) — có thể defer nhưng nên note.

### Best Practices Compliance (v2)

| Check | v1 | v2 |
| --- | --- | --- |
| Epic delivers user value | ⚠️ Technical epic (Epic 2, 3) | ⚠️ **Vẫn nghiêng technical** cho Epic 0, 2, 3 (chấp nhận được cho R&D PoC) |
| Epic independence | ❌ Tuyến tính | ✅ **Epic 0 unblocks song song** |
| Story sizing | ✅ | ✅ Nhỏ hơn |
| No forward dependencies | ⚠️ | ✅ **Fixed** — mọi story chỉ depend contract, không depend upstream code |
| DB tables when needed | N/A | N/A |
| Clear ACs | ❌ Vague | ✅ **Fixed** — mọi story có ngưỡng số (ms, MB, %, tolerance) |
| Traceability to FRs | ✅ | ✅ Nâng cấp (map cả NFR + Success Signal) |
| **Story files đầy đủ** | ⚠️ 1/16 | ⚠️ **1/62** — regression tương đối |

---

## 6. Parallelization Analysis (v2)

### Dependency Graph

```
Epic 0 (5 stories, ~1 tuần)
  ├─ Track 1A (5) ──┐
  ├─ Track 1B (4) ──┤
  ├─ Track 1C (4) ──┼── Track 1E integration (3)
  ├─ Track 1D (3) ──┘
  ├─ Track 2A (4) ──┐
  ├─ Track 2B (4) ──┼── Track 2C validation (3)
  ├─ Track 3A (4) ──┐
  ├─ Track 3B (3) ──┤
  ├─ Track 3C (4) ──┤── Story 3E.1 gate (2)
  ├─ Track 3D (3) ──┘
  ├─ Epic 5 (4)     ── song song hoàn toàn với mọi Track khác
  └─────────── Epic 4 (4) ── sau 3E xong
                        └── Epic 6 (3) ── final gate
```

### Concurrency Capacity

- Max song song **sau Epic 0**: **11 tracks** (1A, 1B, 1C, 1D, 2A, 2B, 2C, 3A, 3B, 3C, 3D, 5) → chấp nhận 10-12 dev/agent.
- v1: max 2. **Cải thiện ×5-6.**

### Verified Independence (spot check)

- ✅ Story 2A.3 chỉ input mock JSON từ 0.4 → không đợi Epic 1.
- ✅ Story 3A.1 input mock GraphSnapshot từ 0.2 → không đợi Epic 2.
- ✅ Story 5.2 input mock Fragility → không đợi Epic 4.
- ⚠️ Story 1E.1 (Pipeline orchestrator) integrate 1A+1B+1C → **đúng là gate cuối Epic 1**, không phải problem.

---

## 7. Summary and Recommendations (v2)

### Overall Readiness Status

**✅ READY (với 1 khối việc pre-implementation)**

Từ **NEEDS WORK** ở v1 → **READY** ở v2. Tất cả critical/major coverage gap đã đóng. Còn lại là hygiene: sinh story files chi tiết + resolve legacy overlap.

### Critical Issues Requiring Immediate Action

**Không còn critical.**

### Pre-Implementation Action Items (thứ tự ưu tiên)

1. **[M2] Resolve legacy Story 1.1 vs Track 1A overlap** — quyết định giữ file legacy hay tạo mới 5 file Track 1A. Cập nhật sprint-status.yaml.
2. **[M1] Chạy `bmad-create-story` batch cho Epic 0** (5 stories) — sinh file chi tiết Dev Context + Testing Requirements như style Story 1.1.
3. **[M3] Encode dependency Epic 0 → các track** trong sprint-status.yaml (thêm field `blocked_by`).
4. **[M4] Verify baseline latency Track 3A trước khi enable Story 3E.1 gate** — thêm note trong Story 3E.1 "chỉ enable sau khi Story 3A.4 chốt baseline".
5. **[M5] Confirm scope Story 4.4 & 5.4** với PM (giữ hay defer v2).
6. **[UX conflict]** Xoá "Frontend Next.js Demo" khỏi Brief để nhất quán SPEC.
7. Chạy `bmad-sprint-planning` để phân công 11 track cho team.
8. Chạy `bmad-create-story` cho từng track theo lịch sprint.

### Coverage Snapshot

| Metric | v1 | v2 |
| --- | --- | --- |
| Epics | 5 | 7 |
| Stories | 16 | 62 |
| FR coverage | 80% | **100%** |
| NFR test coverage | 40% | **100%** |
| Success Signal test | 0 | **3 stories** |
| Max parallel dev | 2 | **11** |
| AC ngưỡng cụ thể | 3/16 | **62/62** |
| Story files chi tiết | 1/16 | **1/62 (M1)** |

### Final Note

Đợt review này xác nhận restructure v2 **đóng toàn bộ critical & major gap** của v1. Còn 5 major issues mới phát sinh (chủ yếu hygiene) và 7 minor. Không có gì chặn implementation — có thể vào Phase 4 sau khi hoàn tất Action Item 1–4 (ước lượng 1 sprint chuẩn bị).

---

*Assessment generated by BMad Implementation Readiness workflow (v2 pass) — 2026-07-05.*
