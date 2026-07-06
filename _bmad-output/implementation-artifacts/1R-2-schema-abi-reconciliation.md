---
baseline_commit: aa9487a
type: research
---

# Story 1R.2: Event Schema ↔ ABI Reconciliation

Status: ready-for-dev

## Story

As a **Kỹ sư Dữ liệu**,
I want **đối chiếu `contracts/tick_data.schema.json` (Story 0.1) với ABI on-chain thật của Uniswap V3 Pool và Aave V3 Pool**,
so that **decoder Track 1B viết đúng ngay lần đầu mà không phải refactor sau khi đọc raw log thật**.

## Acceptance Criteria

1. **AC1 — Gap report:** `research/schema_abi_gap.md` tồn tại với 3 section: `## Fields Matched`, `## Fields Missing from Schema`, `## Fields in Schema Not in ABI (excess/renamed)`.

2. **AC2 — Event coverage:** Đối chiếu đủ 7 event: Uniswap V3 `Swap`, `Mint`, `Burn`; Aave V3 `Borrow`, `Supply`, `Withdraw`, `LiquidationCall`. Mỗi event có bảng map: `ABI field` → `schema field` → `status (match|missing|renamed)`.

3. **AC3 — Patch proposal:** Nếu có field `Missing from Schema`, đề xuất bản vá cụ thể cho `contracts/tick_data.schema.json` (diff format hoặc JSON snippet). Nếu không có gap → ghi "No patch needed".

4. **AC4 — ABI source:** Ghi rõ ABI được lấy từ đâu (Etherscan verified contract address + commit/date) để reproducible.

5. **AC5 — Decoder hint:** Với mỗi event, ghi thêm: `topic0` (keccak256 of event signature) và kiểu encoding (`indexed` vs `non-indexed`) để Story 1B.1/1B.2 decode đúng.

## Tasks / Subtasks

- [ ] **Task 1 — Lấy ABI Uniswap V3 Pool** (AC4)
  - [ ] Contract: `0x8f8EF111B67C04Eb1641f5ff19EE54Cda062f163` (Uniswap V3 Factory deployed, dùng pool đã verify)
  - [ ] Hoặc dùng ABI canonical từ Uniswap SDK: https://github.com/Uniswap/v3-core/blob/main/artifacts/contracts/UniswapV3Pool.sol/UniswapV3Pool.json
  - [ ] Extract chỉ events: Swap, Mint, Burn

- [ ] **Task 2 — Lấy ABI Aave V3 Pool** (AC4)
  - [ ] Contract Aave V3 Pool (Ethereum mainnet): `0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2`
  - [ ] Etherscan verified: https://etherscan.io/address/0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2#code
  - [ ] Extract events: Borrow, Supply, Withdraw, LiquidationCall

- [ ] **Task 3 — Đọc tick_data.schema.json hiện tại** (AC2)
  - [ ] File: `contracts/tick_data.schema.json`
  - [ ] List tất cả properties và types

- [ ] **Task 4 — Map Uniswap V3 events → schema** (AC2, AC5)
  - [ ] Swap: `sender, recipient, amount0, amount1, sqrtPriceX96, liquidity, tick` → map sang schema
  - [ ] Mint: `sender, owner, tickLower, tickUpper, amount, amount0, amount1`
  - [ ] Burn: `owner, tickLower, tickUpper, amount, amount0, amount1`
  - [ ] Tính `topic0` cho mỗi event (keccak256 của function signature)
  - [ ] Ghi indexed vs non-indexed

- [ ] **Task 5 — Map Aave V3 events → schema** (AC2, AC5)
  - [ ] Borrow: `reserve, user, onBehalfOf, amount, interestRateMode, borrowRate, referralCode`
  - [ ] Supply: `reserve, user, onBehalfOf, amount, referralCode`
  - [ ] Withdraw: `reserve, user, to, amount`
  - [ ] LiquidationCall: `collateralAsset, debtAsset, user, debtToCover, liquidatedCollateralAmount, liquidator, receiveAToken`
  - [ ] Tính topic0 cho mỗi event

- [ ] **Task 6 — Viết gap report và patch proposal** (AC1, AC3)
  - [ ] Tổng hợp bảng matched/missing/excess
  - [ ] Viết patch proposal nếu cần
  - [ ] Lưu `research/schema_abi_gap.md`

## Dev Notes

**Loại story:** `[RESEARCH]` — output là document + optional patch proposal. Nếu patch cần thiết, tạo thêm PR/note đề nghị update `contracts/tick_data.schema.json`.

**Priority P0 — chặn decoder 1B:** Story 1B.1 và 1B.2 viết decoder dựa trên schema 0.1. Nếu schema thiếu field (VD: `sqrtPriceX96` của Uniswap Swap cần để tính price), decoder sẽ sai ngay từ đầu.

**tick_data.schema.json hiện tại** (fields đã biết từ Story 0.1):
- `block_number`, `block_timestamp`, `protocol` (uniswap_v3|aave_v3)
- `event_type` (swap|mint|burn|borrow|supply|withdraw|liquidation)
- `pool_address`, `token0`, `token1`, `amount0`, `amount1`, `tx_hash`

**Potential gaps dự đoán:**
- Uniswap Swap: `sqrtPriceX96`, `tick` — quan trọng để tính actual price
- Aave LiquidationCall: `collateralAsset`, `debtAsset` — khác với `token0/token1` paradigm
- Aave Borrow: `interestRateMode` — không có trong schema cơ bản

**topic0 cần tính:** Ví dụ Swap = `keccak256("Swap(address,address,int256,int256,uint160,uint128,int24)")`. Dùng web3.py hoặc Ethereum keccak tool.

**Không cần:** Code production, test file. Chỉ tạo `research/schema_abi_gap.md`.

### Project Structure Notes

```
contracts/
  tick_data.schema.json    ← ĐỌC (đừng sửa trừ khi AC3 yêu cầu patch)
research/
  schema_abi_gap.md        ← TẠO MỚI
```

**Nếu cần patch schema:** Thảo luận với PM/Architect trước khi sửa `contracts/tick_data.schema.json` vì Story 0.1 đã `done` và có unit test phụ thuộc (`tests/unit/test_tick_schema.py`).

### References

- `contracts/tick_data.schema.json` — schema hiện tại cần đối chiếu
- `contracts/examples/tick_uniswap_swap.json` — example event đã có
- `contracts/examples/tick_aave_borrow.json`, `tick_aave_liquidation.json`
- Architecture AD-5: `_bmad-output/architecture/architecture-mps-defi-risk/ARCHITECTURE-SPINE.md#AD-5`
- Epics Story 1B.1/1B.2: `_bmad-output/epics.md#Track 1B`
- Uniswap V3 Pool ABI canonical: https://github.com/Uniswap/v3-core (official repo)
- Aave V3 Pool: Etherscan `0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

- `research/schema_abi_gap.md` (NEW)
- `contracts/tick_data.schema.json` (UPDATE — chỉ nếu AC3 xác định gap cần vá)
