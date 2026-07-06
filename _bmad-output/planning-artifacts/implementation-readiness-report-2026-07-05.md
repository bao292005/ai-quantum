---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - SPEC.md (spec-mps-defi-risk) — canonical requirements ground truth
  - prfaq-mps-defi-risk.md — market narrative & FAQ
  - briefs/brief-mps-defi-risk-20260703/brief.md — product brief
  - architecture/architecture-mps-defi-risk/ARCHITECTURE-SPINE.md — invariants
  - epics.md — 5 epics, 16 stories
  - 1-1-web3-rpc-websocket-connection.md — first drafted story
  - sprint-status.yaml — tracking file
assessor: bmad-check-implementation-readiness
assessment_focus: "Traceability + Parallelization (per user requirement: tasks trong epic phải parallel được)"
---

# Implementation Readiness Assessment Report

**Date:** 2026-07-05
**Project:** QuantumRadar (ai-quantum)
**Reviewer:** Product Manager (BMad IR skill)
**User Priority:** Tasks trong epic phải cho phép nhiều người/agent làm song song.

---

## 1. Document Inventory

| Type | Path | Status |
| --- | --- | --- |
| Requirements ground truth | `_bmad-output/specs/spec-mps-defi-risk/SPEC.md` | ✓ dùng làm PRD |
| Product narrative | `_bmad-output/prfaq-mps-defi-risk.md` | ✓ tham chiếu |
| Product brief | `_bmad-output/briefs/brief-mps-defi-risk-20260703/brief.md` | ✓ tham chiếu |
| Architecture | `_bmad-output/architecture/architecture-mps-defi-risk/ARCHITECTURE-SPINE.md` | ✓ |
| Epics & Stories | `_bmad-output/epics.md` | ✓ (5 Epics / 16 stories) |
| Story file | `_bmad-output/1-1-web3-rpc-websocket-connection.md` | ✓ (only 1) |
| Sprint plan | `_bmad-output/sprint-status.yaml` | ✓ |
| UX | — | ❌ Not found (chấp nhận: sản phẩm API, non-goal) |
| PRD (formal) | — | ⚠️ Không có; SPEC đóng vai trò tương đương |

**Kỷ luật vị trí (Warning):** Config `planning_artifacts = _bmad-output/planning-artifacts` nhưng artefact thực nằm ở `_bmad-output/` root. Nên chuẩn hoá để các workflow tương lai tự tìm được.

---

## 2. PRD Analysis (từ SPEC + Architecture)

### Functional Requirements (canonical từ SPEC + refine trong epics.md)

- **FR1** — Đọc tick-data lịch sử & realtime (CSV hoặc Web3 RPC), 3-5 protocol L1 Ethereum. *(SPEC CAP-1)*
- **FR2** — Lọc sự kiện: Swap/Mint/Burn (Uniswap V3) và Borrow/Supply/Withdraw/LiquidationCall (Aave V3). *(AD-5)*
- **FR3** — Lõi PyTorch tính Entanglement bằng MPS → Fragility Index 0-100. *(CAP-2)*
- **FR4** — Bắn Webhook Yellow (≥70%) / Red (≥90%). *(CAP-3)*
- **FR5** — Payload Webhook tuân JSON schema cố định: `timestamp`, `fragility_score`, `alert_level`, `trigger_protocols`. *(AD-3)*

### Non-Functional Requirements

- **NFR1** — E2E latency (block-mới → Webhook) < 50ms.
- **NFR2** — Toàn bộ I/O async (`asyncio`).
- **NFR3** — Lõi PyTorch chạy trên Process/Thread riêng biệt.
- **NFR4** — Ring buffer 10 blocks in-memory (deque/numpy), no disk I/O runtime.
- **NFR5** — Local-first, CPU standard, không GPU.

### Additional Requirements

- Stack pinned: Python 3.11+, PyTorch 2.1+, Web3.py 6.11+, FastAPI 0.104+, Uvicorn 0.23+.
- Structural seed: `ingestion/ engine/ emitter/ core/`.
- Success Signal (SPEC): Backtest LUNA/UST hoặc FTX phải bắn Red ≥10 phút trước liquidation dây chuyền.

### PRD Completeness Assessment

- ✅ SPEC ngắn gọn, đủ để làm contract.
- ⚠️ **Mâu thuẫn scope** giữa SPEC và Brief:
  - SPEC Non-goals: "Không có Dashboard phức tạp (dành cho v2)".
  - Brief In-scope: "Frontend Next.js dashboard nội bộ để demo".
  - Epics.md: **không có Epic Frontend nào** → theo SPEC (đúng).
  - **Cần chốt lại**: bỏ dashboard Demo hay giữ? Nếu giữ → thiếu Epic 6.

---

## 3. Epic Coverage Validation

### Coverage Matrix

| FR | Requirement | Epic Coverage | Status |
| --- | --- | --- | --- |
| FR1 | Ingest tick-data (CSV + Web3 RPC) | Epic 1 (Story 1.1 WebSocket) | ⚠️ **Partial** — thiếu **CSV Loader** dù SPEC & seed đều yêu cầu |
| FR2 | Event filter (Uniswap/Aave) | Epic 1 (Story 1.2) | ✅ Covered |
| FR3 | MPS Fragility Index | Epic 2 + 3 + 4 | ✅ Covered |
| FR4 | Yellow/Red Webhook | Epic 5 (Story 5.2, 5.3) | ✅ Covered |
| FR5 | JSON schema payload | Epic 5 (Story 5.2) | ✅ Covered |

### Coverage Statistics

- Total FRs: **5**
- Fully covered: **4** (80%)
- Partial: **1** (FR1 — thiếu CSV loader cho backtest)
- Missing: **0**

### Missing Requirements

**🟠 FR1 (Partial):** Không có story cho CSV Loader.
- **Impact:** Không thể chạy backtest LUNA/FTX → không thể verify Success Signal của SPEC.
- **Recommendation:** Thêm **Story 1.0 (hoặc 1.7): CSV Historical Data Loader** — parse CSV thành cùng schema với luồng WebSocket, feed vào Ring Buffer.

### NFR Coverage

| NFR | Story trực tiếp | Status |
| --- | --- | --- |
| NFR1 (<50ms E2E) | Story 1.1 test, Story 5.3 | ⚠️ **Không có story E2E latency test** đo từ block → webhook. Từng story test riêng lẻ. |
| NFR2 (async I/O) | Story 1.1, 5.3 | ✅ |
| NFR3 (separate process) | Story 4.2 | ✅ |
| NFR4 (Ring buffer RAM) | Story 1.3 | ✅ |
| NFR5 (CPU local) | Ngầm định | ⚠️ Không có acceptance test verify no-GPU |

### Success Signal Coverage

**🔴 CRITICAL GAP:** SPEC Success Signal = "Backtest LUNA/UST hoặc FTX bắn Red ≥10 phút trước". Story 4.1 chỉ nói "chạy dữ liệu FTX/LUNA điều chỉnh Sigmoid" nhưng **AC không require chứng minh 10-phút-lead-time**. Không có story E2E backtest scenario.
- **Recommendation:** Thêm **Story 6.1 (Epic mới hoặc Epic 4): E2E Backtest Success Scenario** với AC: "Cho dữ liệu 24h trước sự kiện LUNA/UST, hệ thống bắn tín hiệu RED ít nhất 10 phút trước block liquidation đầu tiên".

---

## 4. UX Alignment

**Trạng thái:** No UX document.

- ✅ **Chấp nhận được** — sản phẩm là API/Webhook (B2B integration), SPEC Non-goal đã loại dashboard phức tạp.
- ⚠️ **Cảnh báo (soft):** Brief nhắc "Frontend Next.js Demo". Nếu vẫn muốn giữ → cần Epic UX riêng + UX design.
- **Recommendation:** Chốt dứt điểm — Xoá dashboard khỏi Brief hoặc thêm Epic Demo + UX artefact.

---

## 5. Epic Quality Review

### 🔴 Critical Violations

**V1. Story dependencies không cho phép parallel work (yêu cầu chính của user).**
- Chain Epic 1: 1.1 → 1.2 → 1.3 → 1.4 → 1.5 (mỗi story AC bắt đầu bằng "Given luồng từ Story X-1").
- Epic 2: 2.1 → 2.2 → 2.3 (thuần tuyến tính).
- Epic 3: 3.1 → 3.2 → 3.3 (thuần tuyến tính).
- Epic 4: 4.1 → 4.2 (cần output Epic 3).
- Epic 5: 5.2 phụ thuộc Epic 4; 5.3 phụ thuộc 5.2 + 5.1.
- **Chỉ có 2 story độc lập thực sự:** Story 1.6 (Airflow) và Story 5.1 (FastAPI subscribe).
- **Hệ quả:** Chỉ 2/16 story chạy song song được → 14 story còn lại phải xếp hàng.

**V2. Success Signal của SPEC không có acceptance test tương đương** (đã nêu ở §3).

### 🟠 Major Issues

**M1. Acceptance Criteria quá mờ nhạt ở Epic 2, 3, 4.** Ví dụ:
- Story 2.1 AC: *"Given mảng JSON thô. When parse. Then trả về Graph object chuẩn."* — không định nghĩa "chuẩn" là gì, không có schema, không có ngưỡng.
- Story 2.3 AC: *"Then con người chốt nghiệm thu"* — không testable, không có tiêu chí PASS/FAIL.
- Story 3.1 AC: *"Then output log benchmark"* — không có target metric.
- Story 3.3 AC: *"mô hình chạy nhanh hơn"* — thiếu ngưỡng cụ thể (dù NFR đặt < 30ms).
- Story 4.1 AC: *"chỉ số khớp thực tế lịch sử"* — mơ hồ.

**M2. Story 1.6 (Airflow) là scope creep tiềm năng.**
- SPEC/Architecture không nhắc Airflow. Constraint "Local-first, OpEx=0" không phù hợp Airflow (heavy).
- Có mùi "technical epic" không tạo user value.
- **Nghi vấn:** loại bỏ hoặc dời sang v2 sau PoC.

**M3. Story 1.4 (Pipeline Orchestration) trùng lặp chức năng với 1.1–1.3.**
- Nếu 1.1, 1.2, 1.3 làm đúng contract thì việc kết nối chúng là composition thuần túy — không cần story riêng.
- Có thể merge vào 1.3 như AC bổ sung.

**M4. Story 4.2 (Multiprocessing Wrapper) đứng cuối** — dev phải viết lõi rồi mới wrap. Có thể dẫn tới rework khi shared memory / queue phá vỡ giả định trong Epic 3.

**M5. Runtime dependency (`Given luồng từ Story X`) khiến story sau không thể start khi story trước chưa done.**
- Đây là **forward dependency ẩn** — dev không thể pull nhánh, viết code, chạy CI cho 1.2 nếu 1.1 chưa merge.

### 🟡 Minor Concerns

- **m1.** Persona không nhất quán: Story 3.1 = "Kỹ sư AI", 3.2 = "Kỹ sư AI" nhưng có `(Human Tuning)` tag; Story 4.1 = "Quản lý Rủi ro" (không phải dev) — nên rõ ràng: role người viết code vs người review kết quả.
- **m2.** Story 1.5 "Data Analyst" persona → không có trong sprint plan tracking cho role này.
- **m3.** Story 1.1 file thực (`1-1-web3-rpc-websocket-connection.md`) chi tiết đầy đủ (Dev Context, Implementation Steps, Testing) — **rất tốt**, nên dùng làm template cho 15 story còn lại. Hiện các story khác chỉ có ~5 dòng AC.
- **m4.** Sprint plan liệt kê `1-6-airflow-batch-orchestration-automation` nhưng chưa quyết định giữ hay bỏ story này.
- **m5.** Tên epic sequence "Epic 3: MPS Algorithm Optimization" — nghe như technical milestone. Có thể re-frame theo user value.

### Best Practices Compliance

| Check | Result |
| --- | --- |
| Epics deliver user value | ⚠️ Epic 2, 3 nghiêng về technical R&D (chấp nhận cho PoC nhưng nên gộp) |
| Epic independence | ❌ Epic 2 depends Epic 1, Epic 3 depends Epic 2, Epic 4 depends Epic 3, Epic 5 depends Epic 4 (hoàn toàn tuyến tính) |
| Story sizing | ✅ Story nhỏ, có thể vài giờ đến 1-2 ngày |
| No forward dependencies | ⚠️ Backward chain rất mạnh (mỗi story AC nói "Given output từ story trước") |
| DB tables when needed | ✅ N/A (không có DB) |
| Clear ACs | ❌ Epic 2, 3, 4 vague — Epic 1, 5 tốt hơn |
| Traceability to FRs | ✅ Có FR Coverage Map |

---

## 6. Parallelization Analysis (theo yêu cầu user)

### Dependency Graph hiện tại

```
Epic 1: 1.1 → 1.2 → 1.3 → 1.4 → 1.5     (1.6 độc lập)
                    ↓
Epic 2:            2.1 → 2.2 → 2.3
                             ↓
Epic 3:                     3.1 → 3.2 → 3.3
                                       ↓
Epic 4:                               4.1 → 4.2
                                              ↓
Epic 5: 5.1 (độc lập)  |   5.2 ← 4.2  |   5.3 ← 5.2 + 5.1
```

**Max parallelism hiện tại: ~2 dev/agent cùng lúc** (rất tệ).

### Fix để parallelize — Đề xuất tái cấu trúc

**Nguyên tắc:** Contract-first + Mocks. Story sớm định nghĩa schema/interface → downstream stories mock lên schema đó để làm song song, tích hợp thật sau.

**Insert vào Epic 1 sớm:**
- **Story 0.1: Data Contract & Mock Fixtures** (schema JSON cho tick-data, mock CSV fixture cho backtest, Graph object JSON schema, Fragility payload schema).
  - Sau story 0.1, các track khác chạy song song:
    - Track A (Ingestion): 1.1 → 1.2 → 1.3
    - Track B (Tensor R&D): 2.1 → 2.2 → 2.3 (dùng mock JSON từ 0.1)
    - Track C (MPS Optimization): 3.1 → 3.2 → 3.3 (dùng mock Tensor từ contract)
    - Track D (Emitter API): 5.1, 5.2, 5.3 (dùng mock Fragility từ contract)
    - Track E (Calibration): 4.1 sau Track C done

**Loại bỏ hoặc gộp:**
- Story 1.4 → gộp AC vào 1.3.
- Story 1.6 (Airflow) → drop khỏi PoC (violation Local-first constraint).
- Story 2.3 & 3.2 (Human Review/Tuning) → không phải story dev độc lập; đổi thành checkpoint task trong sprint plan.

**Thêm:**
- Story 1.0/1.7: **CSV Historical Loader** (fill FR1 gap).
- Story 4.3 (hoặc Epic 6): **E2E Backtest Success Scenario** (fill Success Signal gap).
- Story 6.1: **End-to-End Latency Benchmark** (NFR1 direct test).

**Kết quả sau restructure:** 5 tracks song song → **5 dev/agent làm cùng lúc** thay vì 2.

---

## 7. Summary and Recommendations

### Overall Readiness Status

**⚠️ NEEDS WORK** — Không phải NOT READY, nhưng có 2 critical + 5 major issues phải xử lý trước khi implement để đảm bảo:
1. Success Signal có tracer được;
2. Nhiều dev/agent làm song song được (yêu cầu chính của user).

### Critical Issues Requiring Immediate Action

1. **[V1 / Parallelization]** Restructure Epic 1 với "Data Contract Story" (Story 0.1) → mở khoá 5 track song song thay vì 2.
2. **[V2 / Success Signal]** Thêm E2E Backtest story chứng minh "Red ≥10 phút trước LUNA/FTX" với AC đo lường được.
3. **[Scope conflict]** Chốt dashboard: bỏ hay giữ? SPEC vs Brief đang mâu thuẫn.

### Recommended Next Steps

1. **Chỉnh epics.md**: chèn Story 0.1 (Data Contract), Story 1.7 (CSV Loader), Story 4.3 (E2E Backtest), Story 6.1 (Latency Benchmark). Drop Story 1.6 (Airflow). Gộp 1.4 vào 1.3.
2. **Refine AC** cho Epic 2, 3, 4: thêm ngưỡng cụ thể (schema, latency target < X ms, độ trùng khớp ≥ Y%).
3. **Chuyển Story 2.3, 3.2 (Human tasks) sang sprint plan checkpoint** thay vì story cần dev pick up.
4. **Chốt Brief vs SPEC** về Frontend Demo — cập nhật SPEC hoặc gỡ khỏi Brief.
5. **Nhân bản chất lượng story 1.1** cho 15 story còn lại: Story Foundation + Dev Context + Implementation Steps + Testing.
6. **Cập nhật sprint-status.yaml** theo cấu trúc mới sau khi tái cấu trúc Epic.
7. Sau khi fix xong → chạy lại `bmad-check-implementation-readiness` để verify, rồi mới `bmad-sprint-planning` + `bmad-create-story` từng story.

### Final Note

Đánh giá này phát hiện **2 critical + 5 major + 5 minor** issues trên 4 category (traceability, parallelization, AC quality, scope). Ưu tiên xử lý V1 (parallelization) và V2 (success signal) trước khi mở implementation, vì cả hai đều đụng đến việc plan sprint và cấp phát story cho nhiều agent — yêu cầu quan trọng nhất bạn đã đặt ra.

---

*Assessment generated by BMad Implementation Readiness workflow — 2026-07-05.*
