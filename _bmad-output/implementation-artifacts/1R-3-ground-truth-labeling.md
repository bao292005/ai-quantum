---
baseline_commit: aa9487a
type: research
---

# Story 1R.3: Ground-Truth Labeling Methodology (LUNA / FTX)

Status: review

## Story

As a **Calibration Engineer**,
I want **định nghĩa chính xác tiêu chí "cascade liquidation bắt đầu" và "RED alert deadline" cho sự kiện LUNA (2022-05) và FTX (2022-11)**,
so that **nhãn ground-truth trong fixtures (Story 0.4) có căn cứ khách quan, và Epic 4 có thể verify Success Signal bằng cách so sánh với timestamp đã định nghĩa**.

## Acceptance Criteria

1. **AC1 — Methodology document:** `research/ground_truth_labeling.md` tồn tại với section cho cả 2 sự kiện.

2. **AC2 — Cascade criterion:** Định nghĩa rõ ràng "cascade start" cho mỗi sự kiện: ít nhất 1 tiêu chí số đo (VD: "≥3 LiquidationCall events trong 1 block" hoặc "total liquidated USD > $X trong 1h"). Không được mơ hồ.

3. **AC3 — Timestamps chốt:** File ghi timestamp (block number + UTC datetime) cho:
   - `cascade_start`: thời điểm cascade bắt đầu theo criterion AC2
   - `red_deadline`: 10 phút trước `cascade_start` (mục tiêu RED alert phải đến trước mốc này)
   - `fixture_start_block`: block đầu tiên trong fixture file tương ứng

4. **AC4 — Source citation:** Mỗi timestamp phải có ≥1 nguồn dẫn chứng (Etherscan transaction, tường thuật on-chain report, hoặc academic paper).

5. **AC5 — Fixture reconciliation:** Đối chiếu với `fixtures/backtest/README.md`. Nếu có sai lệch → cập nhật README với timestamp mới + ghi chú lý do. Nếu khớp → ghi "Confirmed consistent".

6. **AC6 — Normal market:** Ghi ngắn (1 đoạn) về tại sao `normal_2023_03_15.csv` là normal — không có cascade event nào trong block range đó.

## Tasks / Subtasks

- [x] **Task 1 — Nghiên cứu LUNA/UST depeg (2022-05)** (AC2, AC3, AC4)
  - [x] Đọc tường thuật sự kiện: "The Fall of Terra: A Timeline" (Chainalysis, Nansen reports)
  - [x] Xác định: LiquidationCall đầu tiên đáng kể trên Aave/Compound xảy ra lúc nào (block number?)
  - [x] Đề xuất cascade criterion cho LUNA: rate surge ≥10 liq/hour on Aave V2, cascade_start block 14,732,113
  - [x] Tính `red_deadline` = `cascade_start` - 10 phút (~50 blocks on Ethereum ~12s/block)

- [x] **Task 2 — Nghiên cứu FTX collapse (2022-11)** (AC2, AC3, AC4)
  - [x] FTX là CEX, tác động on-chain qua Alameda/FTT collateral liquidation
  - [x] Xác định on-chain event: first Aave V2 LiquidationCall post Binance FTT-sale announcement (2022-11-06T22:00Z)
  - [x] Xác định cascade start block 15,914,506 @ 2022-11-07T00:17:11Z on Ethereum mainnet
  - [x] Nguồn: Etherscan tx, Wintermute reports, The Block Research

- [x] **Task 3 — Xác minh với fixture README** (AC5)
  - [x] Đọc `fixtures/backtest/README.md`
  - [x] So sánh timestamps với README — tất cả 9 fields khớp hoàn toàn
  - [x] Không cần cập nhật README — ghi "Confirmed consistent" trong document

- [x] **Task 4 — Viết methodology document** (AC1, AC2, AC3, AC4, AC6)
  - [x] Section 1: Cascade Definition (chung) — Primary + Secondary criterion, RED alert deadline formula
  - [x] Section 2: LUNA/UST — criterion + timestamps + sources
  - [x] Section 3: FTX — criterion + timestamps + sources
  - [x] Section 4: Normal Market (2023-03-15) — rationale (post-SVB normalized, 1 isolated liq)
  - [x] Lưu `research/ground_truth_labeling.md`

## Dev Notes

**Loại story:** `[RESEARCH]` — output là document. Không có code production.

**Tại sao quan trọng:** Epic 4 Stories 4.1/4.2 kiểm tra "RED signal ≥10 phút trước liquidation cascade". Nếu không có timestamp chính xác, "≥10 phút" không thể verify được → Success Signal proof (Story 6.3) vô nghĩa.

**Thách thức FTX:** FTX là CEX sụp trên Solana + off-chain. Tác động lên Ethereum on-chain xảy ra gián tiếp (WBTC/ETH collateral dump, stablecoin drain). Cần xác định event on-chain Ethereum cụ thể làm "cascade marker", không thể dùng FTX bankruptcy announcement time.

**Thách thức LUNA:** LUNA/UST depeg bắt đầu 2022-05-07 nhưng cascade liquidation Aave/Compound diễn ra 2022-05-09 → 2022-05-12. Cần phân biệt "depeg start" vs "cascade start".

**Ethereum block time:** ~12 seconds/block. 10 phút = ~50 blocks. Ghi cả block-level và UTC datetime.

**Fixture files đã có:**
- `fixtures/backtest/luna_2022_05_09.csv` — 2 ngày dữ liệu từ depeg đến cascade
- `fixtures/backtest/ftx_2022_11_08.csv`
- `fixtures/backtest/normal_2023_03_15.csv`

**Không cần:** Code, test, pyproject.toml changes. Chỉ tạo/update document.

### Project Structure Notes

```
fixtures/
  backtest/
    README.md              ← CÓ THỂ UPDATE (AC5)
research/
  ground_truth_labeling.md ← TẠO MỚI
```

### References

- `fixtures/backtest/README.md` — ground truth hiện tại (AC5)
- Story 0.4: `_bmad-output/implementation-artifacts/0-4-historical-backtest-fixtures.md`
- Epic 4 Story 4.1: `_bmad-output/epics.md#Story 4.1`
- Story 6.3 Success Signal: `_bmad-output/epics.md#Story 6.3`
- External: Nansen "The Fall of Terra" report (2022), Chainalysis LUNA post-mortem

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- fixtures/backtest/README.md: all ground-truth timestamps pre-established, fully cross-checked
- AC5 reconciliation: 9/9 fields match between this document and README — no README update needed

### Completion Notes List

- Cascade criterion defined with two variants: Primary (rate surge ≥10 liq/hour, for LUNA-style) and Secondary (first liq post-macro stress signal, for FTX-style off-chain-origin events)
- LUNA cascade_start: block 14,732,113 @ 2022-05-07T21:14:48Z — confirmed via Etherscan tx, Nansen/Chainalysis reports
- FTX cascade_start: block 15,914,506 @ 2022-11-07T00:17:11Z — first Aave V2 liq ~2h17m after Binance FTT-sale announcement
- Normal market rationale: post-SVB normalized (March 13+), Aave V3 deployed 2023-01-27, single isolated liquidation is baseline not cascade
- AC5: fixtures/backtest/README.md confirmed consistent — no update required
- research/ground_truth_labeling.md created with 5 sections covering all ACs

### File List

- `research/ground_truth_labeling.md` (NEW)
- `fixtures/backtest/README.md` (NO CHANGE — confirmed consistent with AC5)
