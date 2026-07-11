---
baseline_commit: 0e04db60825409ad60bf9c50f73db6977cb733f6
type: setup
---

# Story E.1: RPC & API Credential Provisioning

Status: ready-for-dev

## Story

As a **Kỹ sư Dữ liệu**,
I want **lấy và điền `WSS_URL` (Alchemy/Infura) + `ETHERSCAN_API_KEY` vào `.env` với hướng dẫn rõ ràng**,
so that **pipeline realtime (Track 1A) và tool extract/verify fixtures kết nối được mainnet mà không hard-code secret**.

## Acceptance Criteria

1. **AC1 — Hướng dẫn tồn tại:** `docs/environment_setup.md` mô tả từng bước: nơi đăng ký Alchemy/Infura + Etherscan, tier miễn phí, rate limit, cách dán key vào `.env`.

2. **AC2 — `.env.example` đủ biến:** `.env.example` liệt kê `WSS_URL`, `ETHERSCAN_API_KEY` (và `WEBHOOK_TEST_URL` cho E.3) với placeholder rõ ràng + comment.

3. **AC3 — Smoke test WSS:** Kết nối `WSS_URL` qua `eth_subscribe("newHeads")` nhận được ít nhất 1 block header trong 30s.

4. **AC4 — Smoke test Etherscan:** 1 call tới Etherscan API (VD `?module=proxy&action=eth_blockNumber`) trả HTTP 200 + JSON hợp lệ.

5. **AC5 — Bảo mật:** `.env` nằm trong `.gitignore` (đã có), KHÔNG được commit. Chỉ `.env.example` được commit. `git status` không hiển thị `.env`.

## Tasks / Subtasks

- [ ] **Task 1 — Cập nhật `.env.example`** (AC2)
  - [ ] Đảm bảo có `WSS_URL=`, `ETHERSCAN_API_KEY=`, `WEBHOOK_TEST_URL=` với comment nguồn lấy
- [ ] **Task 2 — Viết `docs/environment_setup.md`** (AC1)
  - [ ] Section Alchemy/Infura: link đăng ký, chọn network Ethereum Mainnet, copy WSS endpoint
  - [ ] Section Etherscan: link tạo API key free
  - [ ] Section điền `.env`: `cp .env.example .env` rồi dán key
- [ ] **Task 3 — Smoke test kết nối** (AC3, AC4)
  - [ ] Chạy thử `python -c "..."` hoặc dùng `tools/check_env.py` (E.4) khi có
  - [ ] Ghi kết quả (block number nhận được, HTTP status) vào Completion Notes
- [ ] **Task 4 — Xác nhận bảo mật** (AC5)
  - [ ] `git check-ignore .env` trả về `.env`; `git status` không list `.env`

## Dev Notes

**Loại story:** `[SETUP]` — config/ops, không có code production. Tái dùng loader `ingestion/config.py` (Story 1A.1 đã done) để đọc `.env` — KHÔNG viết lại loader.

**Nguồn key (free-tier):**
- Alchemy: https://dashboard.alchemy.com — tạo app Ethereum Mainnet → WebSocket URL dạng `wss://eth-mainnet.g.alchemy.com/v2/<KEY>`.
- Infura fallback: `wss://mainnet.infura.io/ws/v3/<KEY>`.
- Etherscan: https://etherscan.io/myapikey — free 5 call/s.

**Smoke test tham khảo:**
```bash
# WSS - nhận 1 block rồi thoát (dùng loader 1A.1 nếu có, hoặc web3 trực tiếp)
python -c "import asyncio, os; from web3 import AsyncWeb3, WebSocketProvider; \
async def m(): \
  async with AsyncWeb3(WebSocketProvider(os.environ['WSS_URL'])) as w3: print(await w3.eth.block_number); \
asyncio.run(m())"

# Etherscan
curl -s "https://api.etherscan.io/api?module=proxy&action=eth_blockNumber&apikey=$ETHERSCAN_API_KEY"
```

**Không cần:** viết code mới ngoài lệnh smoke test một dòng. Story E.4 sẽ đóng gói kiểm tra này thành `tools/check_env.py`.

### Project Structure Notes

```
.env.example              ← UPDATE (thêm biến + comment)
.env                      ← TẠO local (KHÔNG commit)
docs/environment_setup.md ← TẠO MỚI
```

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

- `.env.example` (UPDATE)
- `docs/environment_setup.md` (NEW)
- `.env` (LOCAL — không commit)
