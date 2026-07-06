# Historical Backtest Fixtures

Ground-truth on-chain event fixtures for Success-Signal calibration (Story 4.1),
cross-validation (Story 4.2) and final proof (Story 6.3). Every row conforms to
the Story 0.1 tick-data schema (`contracts/tick_data.schema.json`) and is
validated + cross-checked against Etherscan by `tools/verify_fixtures.py`.

All data is **real mainnet on-chain data** extracted via the Etherscan V2 logs
API — no synthetic/generated rows. Reproduce with `tools/extract_fixtures.py`.

## Protocol note (Aave version)

Aave V3 was **not** deployed on Ethereum mainnet until **2023-01-27**. The LUNA
(2022-05) and FTX (2022-11) windows therefore use **Aave V2**
(`0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9`); the normal-market control
(2023-03) uses **Aave V3** (`0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2`).
The tick-data schema `protocol` enum was extended to include `aave_v2` for this
reason (see Story 0.1 change log).

## Storage strategy

The repo does **not** use Git LFS, so per Story 0.4 AC9 the fixtures are
committed **gzip-compressed** (`.csv.gz`). `tools/verify_fixtures.py` and any
downstream loader open `.csv` and `.csv.gz` transparently (`gzip.open` when the
extension is `.gz`). Raw `.csv` (produced by the extractor) is git-ignored.

| File | Rows | Raw | Gzipped |
| --- | --- | --- | --- |
| `luna_2022_05_09.csv.gz`   | 26,540 | 6.9 MB | 1.5 MB |
| `ftx_2022_11_08.csv.gz`    | 35,109 | 9.3 MB | 2.1 MB |
| `normal_2023_03_15.csv.gz` |  6,899 | 1.8 MB | 434 KB |

All raw files are < 50 MB (AC7); gzip is used only for repo footprint.

## Common columns (Story 0.1 schema, 11 fields)

`block_number, block_timestamp, protocol, event_type, pool_address, token0,
token1, amount0, amount1, tx_hash, log_index`

- Uniswap V3 events come from the USDC/WETH 0.05 % pool
  `0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640`; `amount0`/`amount1` are signed
  int256 deltas (USDC / WETH respectively).
- Aave events are single-asset: `token0` = reserve asset, `token1` = zero-address;
  `amount0` = principal (for `liquidation`, `amount0` = liquidated collateral,
  `amount1` = debt covered).

---

## luna_2022_05_09.csv.gz — LUNA/UST depeg

- **Block range:** 14,724,001 → 14,740,000
- **Timestamp range (UTC):** 2022-05-06T14:15:06Z → 2022-05-09T03:13:10Z
- **Protocol coverage:** uniswap_v3 (15,825) + aave_v2 (10,715)
- **Event types:** swap 15,825 · supply 5,788 · borrow 4,661 · liquidation 266
- **UST-depeg liquidation cascade onset (Success-Signal anchor):** block
  **14,732,113** @ **2022-05-07T21:14:48Z**
  tx `0x4b547ce88cec5c756bcc04fb2590e3fcebceeb305de6d012b1a85a8d810a6513`
  — this is the first cascading LUNA/UST liquidation (surge to ~26 liq/hour).
  Earlier isolated liquidations in the window (e.g. block 14,726,199 @
  2022-05-06T22:34:25Z) are routine pre-depeg events, not the LUNA collapse.
- **Expected RED alert deadline (Success Signal):** cascade-onset − 10 min =
  **2022-05-07T21:04:48Z**
- **Pre-cascade runway:** window start 2022-05-06T14:15:06Z → cascade onset
  2022-05-07T21:14:48Z = **~31h ≥ 24h** (AC1 satisfied).
- **Note:** the wider LUNA collapse cascaded through 2022-05-09 → 05-12. To
  capture the full 12h-after tail, re-run the extractor with `to_block=14745000`.

## ftx_2022_11_08.csv.gz — FTX collapse

- **Block range:** 15,900,000 → 15,924,999
- **Timestamp range (UTC):** 2022-11-04T23:40:47Z → 2022-11-08T11:25:23Z
- **Protocol coverage:** uniswap_v3 (32,305) + aave_v2 (2,804)
- **Event types:** swap 32,305 · supply 1,742 · borrow 1,054 · liquidation 8
- **First liquidation (Aave V2):** block **15,914,506** @ **2022-11-07T00:17:11Z**
  tx `0xd07de96feccc50c70067be69aa43a0ddc6c6d550fa22257e0c888f6ecc1ee3ff`
- **Expected RED alert deadline (Success Signal):** **2022-11-07T00:07:11Z**
- **Window-coverage note (AC1 deviation):** this fixture spans the FTX-collapse
  *onset* (2022-11-04 → 2022-11-08T11:25:23Z), not the full "2022-11-08 →
  2022-11-11" bankruptcy tail named in AC1. It still satisfies the fixture
  contract (≥1000 rows, ≥3 event_types, ≥1 Aave liquidation) and captures the
  first on-chain Aave V2 liquidation of the collapse — sufficient ground truth
  for Success-Signal calibration. To extend through the 11-09 → 11-11 cascade,
  re-run the extractor with `to_block=16_050_000`
  (`fixtures/backtest/queries/ftx.sql` documents the same range).

## normal_2023_03_15.csv.gz — control (normal market)

- **Block range:** 16,820,000 → 16,824,999
- **Timestamp range (UTC):** 2023-03-13T15:36:47Z → 2023-03-14T08:28:23Z
- **Protocol coverage:** uniswap_v3 (6,566) + aave_v3 (333)
- **Event types:** swap 6,566 · supply 203 · borrow 129 · liquidation 1
- **Expected behaviour:** control set — the pipeline must **not** emit a RED
  alert here (false-positive guard). The single isolated liquidation is routine.

---

## Data source & reproducibility

- **Source:** Etherscan V2 logs API (`module=logs&action=getLogs`), Ethereum
  mainnet (chainid=1). Decoded locally in `tools/extract_fixtures.py`.
- **Reproduce:** `python tools/extract_fixtures.py --period all`
  (requires `ETHERSCAN_API_KEY` in env or `.env`).
- **Dune equivalents:** see `queries/luna.sql`, `queries/ftx.sql`,
  `queries/normal.sql`.
- **Extraction date:** 2026-07-05
- **Verify:** `python tools/verify_fixtures.py` (schema + sanity + on-chain
  cross-check of 10 random rows/file).
