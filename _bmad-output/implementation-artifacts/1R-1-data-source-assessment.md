---
baseline_commit: aa9487a
type: research
---

# Story 1R.1: Data Source Assessment (Etherscan / Dune / Alchemy)

Status: ready-for-dev

## Story

As a **Kỹ sư Dữ liệu**,
I want **đánh giá Etherscan, Dune Analytics và Alchemy về độ phủ, rate limit, chi phí, và độ sâu archival dữ liệu on-chain**,
so that **chúng ta chốt được nguồn primary + fallback cho ingestion (Track 1A) và backfill fixtures (0.4) trước khi viết code kết nối**.

## Acceptance Criteria

1. **AC1 — Bảng so sánh:** `research/data_sources.md` tồn tại và chứa bảng so sánh 3 nhà cung cấp với ít nhất các cột: `Provider`, `WSS support`, `Rate limit (req/s free)`, `Rate limit (req/s paid)`, `Archival depth`, `Cost/month (PoC tier)`, `LUNA block range available`, `FTX block range available`.

2. **AC2 — Khuyến nghị chốt:** File kết thúc bằng mục `## Decision` nêu: (a) nguồn primary WSS realtime, (b) nguồn fallback, (c) nguồn historical backfill, kèm lý do ngắn.

3. **AC3 — Block range verification:** Xác nhận cụ thể block range của LUNA (2022-05-07 → 2022-05-12) và FTX (2022-11-06 → 2022-11-11) trên Ethereum mainnet có thể truy cập từ nguồn đã chọn (sample query hoặc document).

4. **AC4 — Key / credential model:** Nêu cách quản lý API key cho môi trường dev và CI (`.env` pattern, env var name đề xuất).

## Tasks / Subtasks

- [ ] **Task 1 — Khảo sát Alchemy** (AC1, AC3)
  - [ ] Đăng ký / dùng free tier; kiểm tra WSS endpoint `wss://eth-mainnet.g.alchemy.com/v2/{KEY}`
  - [ ] Đo rate limit, ghi lại archival support (Alchemy hỗ trợ archive node)
  - [ ] Thử truy vấn block range LUNA (block ~14.7M-14.76M) và FTX (block ~15.8M-15.85M)

- [ ] **Task 2 — Khảo sát Infura** (AC1, AC3)
  - [ ] Kiểm tra WSS `wss://mainnet.infura.io/ws/v3/{KEY}`, rate limit free tier
  - [ ] Xác nhận archive access (Infura cần paid plan cho archive)
  - [ ] So sánh reliability và latency so với Alchemy

- [ ] **Task 3 — Khảo sát Dune Analytics** (AC1, AC3)
  - [ ] Kiểm tra Dune API v1 (REST, không có WSS) — phù hợp backfill, không realtime
  - [ ] Rate limit API, chi phí export CSV, có thể query LUNA/FTX events không
  - [ ] Ghi rõ: Dune KHÔNG phù hợp cho realtime WSS → chỉ làm backfill

- [ ] **Task 4 — Khảo sát Etherscan** (AC1, AC3)
  - [ ] API rate limit free (5 req/s), không có WSS native
  - [ ] Etherscan archives toàn bộ lịch sử — phù hợp reconcile (Story 1E.2) hơn là ingestion chính

- [ ] **Task 5 — Viết decision document** (AC1, AC2, AC4)
  - [ ] Tổng hợp bảng so sánh
  - [ ] Viết mục `## Decision` với primary/fallback/backfill
  - [ ] Đề xuất env var: `WSS_URL` (primary), `WSS_FALLBACK_URL` (fallback), `ALCHEMY_KEY`
  - [ ] Lưu tại `research/data_sources.md`

## Dev Notes

**Loại story:** `[RESEARCH]` — output là document quyết định, không có code production.

**Mục tiêu:** Quyết định này unblock Story 1A.2 (AsyncWeb3 client cần biết provider URL) và Story 1E.2 (Etherscan reconcile tool).

**Context biết trước:**
- Architecture AD-4: PHẢI dùng WebSocket (`eth_subscribe`/WSS) kết nối thẳng vào node — loại trừ REST-only providers cho realtime ingestion.
- Story 0.5 mock WSS (`ws://localhost:8546`) cover dev/CI → nguồn thật chỉ cần cho staging/production.
- Story 1A.1 đề xuất env var names: `WSS_URL`, `ALCHEMY_KEY` — align với naming đó.

**Block ranges ước tính (Ethereum mainnet):**
- LUNA depeg: ~block 14,700,000 – 14,760,000 (2022-05-07 → 2022-05-12)
- FTX collapse: ~block 15,800,000 – 15,850,000 (2022-11-06 → 2022-11-11)

**Lưu ý chi phí:** PoC chỉ cần free tier. Alchemy free = 300M compute units/month, đủ cho dev. Nếu free tier quá chậm cho archive queries → note và đề xuất paid plan budget.

**Không cần:** Code, test, pyproject.toml changes. Không tạo file nào ngoài `research/data_sources.md`.

### Project Structure Notes

```
research/                  ← tạo thư mục nếu chưa có (git-tracked)
  data_sources.md          ← output duy nhất của story này
```

### References

- Architecture: `_bmad-output/architecture/architecture-mps-defi-risk/ARCHITECTURE-SPINE.md#AD-4`
- Story 1A.1 (env var naming): `_bmad-output/implementation-artifacts/1A-1-env-secrets-loader.md`
- Story 1E.2 (Etherscan reconcile): `_bmad-output/epics.md#Story 1E.2`
- Epic 1 Track 1R: `_bmad-output/epics.md#Track 1R`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

- `research/data_sources.md` (NEW)
