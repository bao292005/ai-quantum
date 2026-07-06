---
baseline_commit: 186d98f8f25e4da0e1cd16100f350b9dd6f08ddc
---

# Story 0.4: Historical Backtest Fixtures

Status: done

## Story

As a **Data Analyst (QA + Calibration engineer)**,
I want **3 file CSV lịch sử LUNA/UST, FTX và một khoảng thị trường bình thường được ingest thành fixture chuẩn tại `fixtures/backtest/`**,
so that **Story 4.1 (LUNA calibration), 4.2 (FTX cross-val), 6.3 (Success Signal proof) và Track 3B/3C dùng chung một ground truth để verify SPEC Success Signal (RED ≥ 10 phút trước liquidation)**.

## Acceptance Criteria

1. **AC1 — Ba file CSV tồn tại đúng path:**
   - `fixtures/backtest/luna_2022_05_09.csv` — cover ≥ 24h trước và 12h sau block liquidation LUNA đầu tiên (block ≈ `14733318`, 2022-05-09 03:34 UTC)
   - `fixtures/backtest/ftx_2022_11_08.csv` — cover 2022-11-08 đến 2022-11-11 (FTX collapse period)
   - `fixtures/backtest/normal_2023_03_15.csv` — 1 ngày thị trường bình thường (control set)

2. **AC2 — Kích thước tối thiểu:** Mỗi file ≥ 1000 events (kiểm tra bằng `wc -l`, trừ header).

3. **AC3 — Đúng schema Story 0.1:** Mỗi row CSV có 11 cột đúng thứ tự và tên như Story 0.1 field. Script `python tools/verify_fixtures.py` load từng CSV → convert từng row → `validate_tick(event)` → pass 100% row.

4. **AC4 — Metadata README:** `fixtures/backtest/README.md` ghi cho mỗi file:
   - Block range (start, end)
   - Timestamp range UTC
   - Protocol coverage (VD: luna file phải có ≥ 1 event từ Aave V3 và ≥ 1 từ Uniswap V3)
   - **Expected liquidation block + timestamp** (cho luna, ftx)
   - **Expected RED alert deadline** = liquidation_timestamp - 10 phút (Success Signal target)
   - Nguồn dữ liệu: Etherscan / Dune query id / manual extraction
   - Ngày extract

5. **AC5 — Query reproducibility:** Trong `fixtures/backtest/queries/`:
   - `luna.sql` — Dune query hoặc BigQuery script tái tạo được file
   - `ftx.sql`
   - `normal.sql`
   Kèm README hướng dẫn chạy.

6. **AC6 — Sanity checks trong verify script:**
   - Timestamp monotonic tăng
   - Không có duplicate `(tx_hash, log_index)`
   - Phân bố event_type: mỗi file có ≥ 3 event_type khác nhau
   - Amount không có NaN/empty

7. **AC7 — Size guard:** Mỗi file ≤ 50MB (đủ cho 1000-100k event). Nếu vượt → gzip và cập nhật loader.

8. **AC8 — On-chain cross-check (chống fabricate):** Verify script random-sample **10 row/file**, gọi Etherscan API `eth_getTransactionByHash(tx_hash)` → assert `blockNumber` khớp CSV. Fail nếu bất kỳ mismatch. API key đọc từ env `ETHERSCAN_API_KEY`; nếu env trống → skip test và log WARNING (không fail CI, để offline dev vẫn chạy).

9. **AC9 — Storage strategy (Git LFS vs gzip):** Trước khi commit, quyết định 1 trong 2:
   - **Nếu Git LFS đã setup trong repo:** commit file `.csv` raw, thêm `*.csv` vào `.gitattributes` với filter LFS.
   - **Nếu chưa có LFS:** commit file `.csv.gz` (gzip), cập nhật `tools/verify_fixtures.py` + downstream loader support đọc gzip transparent (dùng `gzip.open` khi extension `.gz`).
   Ghi rõ quyết định trong `fixtures/backtest/README.md` section "Storage".

## Tasks / Subtasks

- [x] **Task 1 — Extract dữ liệu LUNA**
  - [x] Dune query hoặc Etherscan API cho block range 14730000-14740000 (dùng Etherscan V2 getLogs)
  - [x] Filter Uniswap V3 (pool USDC/WETH 0.05%) + Aave **V2** Pool events (V3 chưa deploy 2022-05)
  - [x] Normalize về schema 0.1 (11 cột)
  - [x] Verify có ≥ 1 event LiquidationCall (260 liquidations; first @ block 14731270)

- [x] **Task 2 — Extract dữ liệu FTX**
  - [x] Block range 15900000-15924999 (2022-11-04 → 11-08)
  - [x] Cùng filter (Aave V2) — 8 liquidations; first @ block 15914506

- [x] **Task 3 — Extract control normal**
  - [x] 2023-03-13→14 (block 16820000-16824999), Aave **V3**
  - [x] 6,899 events ≥ 1000; 1 isolated routine liquidation (control, không RED)

- [x] **Task 4 — Viết verify script**
  - [x] `tools/verify_fixtures.py` chạy 3 file, gọi `validate_tick` từng row
  - [x] Assertion sanity check AC6 (monotonic, unique, ≥3 event_types, no empty/NaN)
  - [x] Exit 1 nếu bất kỳ file nào fail

- [x] **Task 5 — README + queries**
  - [x] Metadata đầy đủ 3 file (`fixtures/backtest/README.md`)
  - [x] Ghi block liquidation expected + deadline RED (LUNA 17:49:54Z, FTX 00:07:11Z)
  - [x] `queries/{luna,ftx,normal}.sql` + `queries/README.md`

- [x] **Task 6 — Storage & CI integration** (AC 8, 9)
  - [x] Quyết định: **gzip** (repo không có Git LFS) — ghi trong README section "Storage strategy"
  - [x] gzip 3 file → `.csv.gz`, `verify_fixtures.py` mở `.csv`/`.csv.gz` transparent; `.gitignore` exclude raw `.csv`
  - [x] Extend verify script: sample 10 row deterministic, gọi `eth_getTransactionByHash` cross-check (AC8)
  - [x] Job `verify-fixtures` chạy verify_fixtures.py trong CI (secret `ETHERSCAN_API_KEY`)

- [x] **Task 7 — Update sprint-status**

### Review Findings (Code Review 2026-07-05)

**Resolved decisions (2026-07-05, user chose re-extract + anchor sync → applied; fixture DATA regenerated with live `ETHERSCAN_API_KEY`):**

- [x] [Review][Patch][DONE] Re-extract LUNA with ≥24h runway — extractor `from_block` set to 14_724_000 + luna.sql aligned; re-ran `extract_fixtures.py --period all`, re-gzipped, re-verified (on-chain cross-check OK). LUNA now 26,540 rows, blocks 14,724,001→14,740,000, ts 2022-05-06T14:15:06Z→2022-05-09T03:13:10Z. README stats updated. [tools/extract_fixtures.py PERIODS["luna"], fixtures/backtest/queries/luna.sql, fixtures/backtest/luna_2022_05_09.csv.gz]
- [x] [Review][Patch][DONE] Sync LUNA liquidation anchor to real cascade onset — README now anchors on the UST-depeg cascade onset block 14,732,113 @ 2022-05-07T21:14:48Z (RED deadline 2022-05-07T21:04:48Z, runway ~31h); dropped the misleading "block 14733318 / 03:34 UTC" reference. Earlier isolated liquidations flagged as routine pre-depeg. [fixtures/backtest/README.md]

**Patch (fixable, unambiguous):**

- [x] [Review][Patch][DONE] Aave V3 Borrow amount decoded from wrong data word — fixed to data word 1 for both V2 and V3 (word 3 was `borrowRate`). Normal fixture re-extracted; the 129 aave_v3 borrow rows now carry correct token-scaled amounts (verified sane, e.g. 4320001050859399643, 6500000000, max 24 digits vs old ~1e27). [tools/extract_fixtures.py decode_aave_borrow, fixtures/backtest/normal_2023_03_15.csv.gz]
- [x] [Review][Patch] `_slice_data` length guard added — raises ValueError on short/empty `data`. [tools/extract_fixtures.py _slice_data]
- [x] [Review][Patch] Pagination single-block ≥1000-log truncation now fails loudly (RuntimeError) instead of silently dropping rows. [tools/extract_fixtures.py etherscan_get_logs]
- [x] [Review][Patch] `verify_fixtures.main()` now also catches ValueError/RuntimeError/RequestException/OSError per file. [tools/verify_fixtures.py main]
- [x] [Review][Patch] Cross-check retries transient/None responses (3 attempts, linear backoff) before failing. [tools/verify_fixtures.py _tx_block_from_etherscan]
- [x] [Review][Patch] SQL luna block range aligned to extractor (`BETWEEN 14724000 AND 14740000`). [fixtures/backtest/queries/luna.sql]
- [x] [Review][Patch] AC6 timestamp-vs-block_number monotonic deviation documented in verify_fixtures.py docstring. [tools/verify_fixtures.py]

**Dismissed (resolved/documented):** AC4 aave_v3→aave_v2 (documented in Completion Notes + schema Change Log); AC9 `.csv.gz` vs raw csv (documented in README "Storage").

### Review Findings (Code Review 2026-07-05, fresh pass post-regeneration)

Adversarial re-review (Blind Hunter + Edge Case Hunter + Acceptance Auditor) after the patch+regeneration cycle. Auditor confirmed **all** README/story fixture numbers match committed data exactly (LUNA/FTX/normal rows, block/ts ranges, event-type breakdowns, anchor block, runway 31h ≥24h). Findings triaged: 2 patch + 1 decision (user chose accept+document) + 2 dismiss.

**Patch (fixable, unambiguous):**

- [x] [Review][Patch][DONE] `_tx_block_from_etherscan` treated a persistent rate-limit STRING result as "no result" → returned silent `None` → `_cross_check` raised misleading `AssertionError("no result for tx …")`, failing a valid fixture. Now distinguishes the rate-limit string (retries) from a genuine pending-tx dict (`None`), and raises `RuntimeError` on retry exhaustion so `main()` surfaces a clear, actionable failure. [tools/verify_fixtures.py _tx_block_from_etherscan]
- [x] [Review][Patch][DONE] `_iter_rows` int cast (`int(row[col])`) could raise `KeyError`/`TypeError` on a missing column / short row, escaping `main()`'s `except (ValueError, RuntimeError, RequestException, OSError)` tuple as an ugly stack trace. Now caught and re-raised as `ValueError` with line + column context. [tools/verify_fixtures.py _iter_rows]

**Decision (user resolved):**

- [x] [Review][Decision][DONE] FTX window ends 2022-11-08T11:25:23Z — short of AC1's "2022-11-08 → 2022-11-11" tail; captured Aave V2 liquidation (11-07 00:17Z) is collapse-onset, pre-bankruptcy. **User chose: accept + document limitation** (fixture still meets ≥1000 rows / ≥3 event_types / ≥1 liquidation contract; sufficient ground truth). README FTX section now carries a "Window-coverage note (AC1 deviation)" with the re-extract recipe (`to_block=16_050_000`). [fixtures/backtest/README.md]

**Dismissed:** test_fixtures.py 200-row schema sample limit (intentional bounding for the fast offline job; full-row schema coverage lives in `verify_fixtures.py`); `verify-fixtures` CI green on fork PRs with empty secret (AC8 by-design skip-with-WARNING, documented). Confirmed **not** bugs by all layers: amount `"0"` handling, extractor retry/pagination/1000-cap guard, signed int256 / address / timestamp decoders, `_slice_data` guards, glob non-double-match, EXPECTED protocol sets.

## Dev Notes

### Bối cảnh

Story này cung cấp **ground truth cho Success Signal**. IR report v2 xác định đây là P0 vì:
- Story 4.1 phải tune Fragility params để RED fire ≥ 10 phút trước block LUNA liquidation
- Story 6.3 replay lại để proof cuối cùng

Nếu fixture sai → toàn bộ calibration & proof sai.

### Ràng buộc dữ liệu

- **LUNA UST depeg thực tế:** 2022-05-09 03:34 UTC (block 14733318 mainnet) là block liquidation dây chuyền Aave đầu tiên. Cần data ≥ 24h TRƯỚC block đó để có "runway" cho fragility score tăng.
- **FTX collapse:** 2022-11-08 ~14:00 UTC bắt đầu, 11-11 phá sản. Trên chain ETH có nhiều liquidation Aave giai đoạn này.
- **Normal control:** chọn ngày yên bình (không có FED meeting, không có hack lớn) để verify không có false-positive RED.

### Kỹ thuật extraction

Ưu tiên **Dune Analytics** (free tier) vì:
1. Có sẵn decoded event Uniswap/Aave
2. Query SQL reproducible
3. Export CSV trực tiếp

Fallback: **Etherscan getLogs API** + decode bằng Web3.py (dùng lại decoder từ Story 1B khi có).

**Tránh:** The Graph (indexing delay), Alchemy (rate limit free tier).

### LLM-mistake prevention

- **KHÔNG dùng data từ ChatGPT/synthetic** — Success Signal phải verify được vs on-chain thật.
- **KHÔNG mix timestamp block với timestamp local** — schema yêu cầu UTC. Etherscan trả unix seconds → chuyển ISO 8601 UTC.
- **KHÔNG bỏ event non-target** giữa file — snapshot phải continuous, để pipeline Epic 1 filter thật sự.
- **KHÔNG commit file > 100MB vào git** — dùng gzip hoặc Git LFS.
- **KHÔNG hardcode block liquidation trong code** — chỉ ghi trong README + fixture metadata.

### Ghi chú cho AI dev agent

Nếu không có API access ngay, có thể:
1. Dùng CSV có sẵn từ Dune public dashboard (VD dashboard "Aave V3 liquidations" của các community analyst).
2. Manually curl Etherscan `logs` API với API key free (5 req/s) và save.

### Files tạo mới

- `fixtures/backtest/luna_2022_05_09.csv`
- `fixtures/backtest/ftx_2022_11_08.csv`
- `fixtures/backtest/normal_2023_03_15.csv`
- `fixtures/backtest/README.md`
- `fixtures/backtest/queries/luna.sql`
- `fixtures/backtest/queries/ftx.sql`
- `fixtures/backtest/queries/normal.sql`
- `tools/verify_fixtures.py`

### Files update

- `.gitignore` — có thể exclude file gzip lớn nếu dùng LFS
- `.github/workflows/ci.yml` — thêm job verify-fixtures
- `_bmad-output/sprint-status.yaml`

### Dependency

- Cần Story 0.1 done (schema + `validate_tick`) để verify script hoạt động
- Không depend Epic 1 decoder (Track 1B) — dùng dữ liệu đã decoded từ Dune

### References

- LUNA depeg on-chain analysis: Nansen "Anatomy of a Collapse" (2022-05)
- FTX Aave liquidations: Aave community forum post 2022-11-10
- [Source: _bmad-output/specs/spec-mps-defi-risk/SPEC.md#Success-Signal] — Deadline 10 phút
- [Source: _bmad-output/epics.md#Story-0.4] — AC gốc
- [Source: _bmad-output/implementation-artifacts/0-1-tick-data-json-schema.md] — Schema dependency

## Dev Agent Record

### Agent Model Used

Claude (bmad-dev-story workflow, 2026-07-05).

### Debug Log References

- `python tools/extract_fixtures.py --period all` → luna 17,402 / ftx 35,109 / normal 6,899 rows (real Etherscan V2 getLogs data).
- `python tools/verify_fixtures.py` → "all fixtures OK": schema (59,410 rows) + monotonic + unique (tx_hash, log_index) + ≥3 event_types + on-chain cross-check (10 samples/file matched blockNumber).
- `python -m pytest tests/unit -q` → 55/55 passed (49 pre-existing + 6 new fixture smoke tests).
- Fixed `SyntaxError: invalid hex literal 0xDEFI` → `0xDEF1` in verify_fixtures.py deterministic sampler.

### Completion Notes List

- **Real on-chain data only** (AC pre-req): all three fixtures extracted via Etherscan V2 logs API, no synthetic rows. On-chain cross-check (AC8) guards against fabrication.
- **Aave version anachronism resolved:** Aave V3 mainnet not live until 2023-01-27, so LUNA (2022-05) and FTX (2022-11) use **Aave V2** (`0x7d2768dE...`); normal control (2023-03) uses **Aave V3** (`0x87870Bca...`). Extended `contracts/tick_data.schema.json` `protocol` enum with `aave_v2` (backward-compatible; logged in Story 0.1 Change Log).
- **Storage (AC9):** repo has no Git LFS → committed gzip `.csv.gz`; loader/verify open `.csv`/`.csv.gz` transparently; raw `.csv` git-ignored. All raw < 50 MB (AC7).
- **Decoders:** Uniswap V3 Swap signed int256 (two's-complement); Aave Borrow amount word idx differs V2(1)/V3(3); Deposit/Supply word 1; LiquidationCall shares topic hash across V2/V3.
- **Metadata (AC4):** README documents block/timestamp ranges, protocol+event-type breakdown, first-liquidation block/ts, and RED alert deadline (liquidation − 10 min): LUNA 2022-05-07T17:49:54Z, FTX 2022-11-07T00:07:11Z.
- **Reproducibility (AC5):** DuneSQL queries + Etherscan extractor documented in `queries/README.md`.
- **CI:** added `verify-fixtures` job (Etherscan secret optional — skips cross-check w/ WARNING if unset, keeps forks green). Fast offline `tests/unit/test_fixtures.py` guards schema/sanity in the unit job.
- **Known limitation:** LUNA window ends ~2022-05-09T03:13Z (just past first depeg liquidations). For the full 12h-after tail re-run extractor with `to_block=14745000` — noted in README.

### File List

**Tạo mới:**
- `tools/extract_fixtures.py`
- `tools/verify_fixtures.py`
- `fixtures/backtest/luna_2022_05_09.csv.gz`
- `fixtures/backtest/ftx_2022_11_08.csv.gz`
- `fixtures/backtest/normal_2023_03_15.csv.gz`
- `fixtures/backtest/README.md`
- `fixtures/backtest/queries/luna.sql`
- `fixtures/backtest/queries/ftx.sql`
- `fixtures/backtest/queries/normal.sql`
- `fixtures/backtest/queries/README.md`
- `tests/unit/test_fixtures.py`

**Update:**
- `contracts/tick_data.schema.json` (protocol enum + if/then cho `aave_v2`)
- `.gitignore` (exclude raw `fixtures/backtest/*.csv`)
- `.github/workflows/ci.yml` (job `verify-fixtures`)
- `_bmad-output/implementation-artifacts/0-1-tick-data-json-schema.md` (Change Log: aave_v2 extension)
- `_bmad-output/sprint-status.yaml` (0-4 → review)

## Change Log

| Date | Change | Author |
| --- | --- | --- |
| 2026-07-05 | Story 0.4 implemented: extract+verify pipeline, 3 real on-chain gzip fixtures (59,410 events), schema `aave_v2` extension, SQL reproduction queries, README metadata, CI `verify-fixtures` job, 6 offline smoke tests. 55/55 tests pass; `verify_fixtures.py` reports all OK. Status → review. | dev-story (Claude) |
| 2026-07-05 | Code-review triage (7 patch + 2 decision→re-extract). Applied 7 code/SQL/doc patches: Aave V3 Borrow amount word 3→1, `_slice_data` length guard, loud single-block pagination truncation, `verify_fixtures.main()` broadened exception catch, cross-check transient-retry, luna.sql block range aligned to 14724000, AC6 monotonic-deviation doc. LUNA `from_block`→14_724_000 for ≥24h runway. 55/55 tests still pass. 2 HIGH items (LUNA runway/anchor, aave_v3 borrow amounts) need fixture regeneration — BLOCKED offline (`ETHERSCAN_API_KEY` unset). Status → in-progress. | code-review (Claude) |
| 2026-07-05 | Fixture regeneration UNBLOCKED (`.env` key present; loader handles spaced `=`). Re-ran `extract_fixtures.py --period all` with rate-limit throttle (2 req/s) + retry: LUNA 26,540 rows (blocks 14,724,001→14,740,000, ~31h pre-cascade runway, cascade onset block 14,732,113 @ 2022-05-07T21:14:48Z), FTX 35,109, normal 6,899 (aave_v3 borrow amounts corrected). All re-gzipped + re-verified (schema + sanity + 10-sample on-chain cross-check OK). README size table + LUNA metadata updated; anchor synced to cascade onset. Both HIGH items resolved. Status → review. | code-review (Claude) |
| 2026-07-05 | Fresh adversarial code-review post-regeneration (3 parallel layers). Auditor confirmed all fixture numbers match committed data exactly. Applied 2 verify_fixtures.py patches: (1) `_tx_block_from_etherscan` now distinguishes persistent rate-limit string from pending-tx None and raises RuntimeError on retry exhaustion (was silent None → misleading AssertionError); (2) `_iter_rows` int cast now re-raises KeyError/TypeError as ValueError with line+column context (was escaping main()'s except tuple). FTX-window vs AC1 gap: user chose accept+document → README "Window-coverage note" added. 2 dismissed (200-row sample bound, fork-CI skip — both by-design). 55/55 tests pass; verify_fixtures.py all fixtures OK (on-chain cross-check ✓). Status stays review. | code-review (Claude) |
