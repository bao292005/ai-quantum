---
baseline_commit: 0e04db60825409ad60bf9c50f73db6977cb733f6
type: setup
---

# Story E.2: Contract & Wallet Address Registry

Status: ready-for-dev

## Story

As a **Kỹ sư Dữ liệu**,
I want **điền các địa chỉ mainnet thật cần giám sát vào `ingestion/whitelist.yaml` (Uniswap V3 pools, Aave V2/V3 Pool)**,
so that **EventRouter (1B.4) lọc đúng contract, không bỏ sót hoặc nhầm scope**.

## Acceptance Criteria

1. **AC1 — Địa chỉ core có mặt:** `ingestion/whitelist.yaml` chứa ít nhất:
   - Uniswap V3 USDC/WETH 0.05% pool: `0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640`
   - Aave V2 Pool: `0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9`
   - Aave V3 Pool: `0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2`

2. **AC2 — Metadata đầy đủ:** Mỗi entry ghi `protocol` đúng enum (`uniswap_v3` | `aave_v2` | `aave_v3`) và `token0`/`token1` (Uniswap = token thật; Aave single-asset = zero address).

3. **AC3 — Load không lỗi:** `ContractWhitelist.from_yaml("ingestion/whitelist.yaml")` (Story 1B.3) load file thật, `len(whitelist) >= 3`, không raise validation error.

4. **AC4 — Truy vết được:** Mỗi địa chỉ có comment kèm ký hiệu token + link/tham chiếu Etherscan để verify.

5. **AC5 — Địa chỉ lowercase + hợp lệ:** Tất cả địa chỉ normalize về lowercase, đúng 42 ký tự (`0x` + 40 hex).

## Tasks / Subtasks

- [ ] **Task 1 — Bổ sung địa chỉ vào whitelist.yaml** (AC1, AC2, AC4, AC5)
  - [ ] Thêm Aave V2 Pool entry (protocol: `aave_v2`) — cần cho fixture LUNA/FTX (Aave V3 chưa deploy 2022)
  - [ ] Xác nhận Uniswap V3 USDC/WETH + Aave V3 đã có (từ default 1B.3)
  - [ ] Mỗi entry kèm comment token symbol
- [ ] **Task 2 — Verify load** (AC3)
  - [ ] `python -c "from ingestion.whitelist import ContractWhitelist as W; w=W.from_yaml('ingestion/whitelist.yaml'); print(len(w))"` ≥ 3
  - [ ] Lookup từng địa chỉ core → trả entry đúng protocol

## Dev Notes

**Loại story:** `[SETUP]` — điền dữ liệu config. **BlockedBy:** 1B.3 (schema + loader `ContractWhitelist`). KHÔNG viết lại loader — chỉ cung cấp giá trị.

**Địa chỉ mainnet đã xác minh (từ `fixtures/backtest/README.md`):**

| Protocol | Address | Ghi chú |
|---|---|---|
| Uniswap V3 | `0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640` | USDC/WETH 0.05% (fixtures dùng) |
| Aave V2 | `0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9` | LUNA + FTX window (2022) |
| Aave V3 | `0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2` | Deploy 2023-01-27, normal-market window |

**Quan trọng — Aave V2 vs V3:** Aave V3 chưa deploy trên mainnet tới 2023-01-27. Fixture LUNA (2022-05) và FTX (2022-11) dùng **Aave V2**. Nếu chỉ whitelist Aave V3, router sẽ drop toàn bộ event Aave trong 2 fixture khủng hoảng → hỏng backtest Epic 4. **Phải có cả V2.**

**Lưu ý enum `protocol`:** schema tick-data (Story 0.1) đã mở rộng thêm `aave_v2`. Đảm bảo `AaveV3Decoder` / router xử lý được cả `aave_v2` (cùng ABI event Supply/Borrow/Withdraw/LiquidationCall).

### YAML mẫu (append vào `ingestion/whitelist.yaml`)

```yaml
# --- Aave V2 Pool (LendingPool) — LUNA/FTX 2022 window ---
"0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9":
  protocol: aave_v2
  token0: "0x0000000000000000000000000000000000000000"  # single-asset, reserve từ topics
  token1: "0x0000000000000000000000000000000000000000"
```

### Project Structure Notes

```
ingestion/whitelist.yaml  ← UPDATE (thêm Aave V2, xác nhận core addresses)
```

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

- `ingestion/whitelist.yaml` (UPDATE)
