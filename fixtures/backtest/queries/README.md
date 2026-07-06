# Fixture reproduction queries

SQL that reproduces the three backtest fixtures in `fixtures/backtest/`. Each
query returns the exact Story 0.1 tick-data schema (11 columns, same order and
naming) and the same row ordering (`block_number, log_index`) as the committed
`.csv.gz` files.

| Query | Fixture | Window | Aave version |
| --- | --- | --- | --- |
| `luna.sql`   | `luna_2022_05_09.csv.gz`   | blocks 14,730,002 – 14,740,000 | V2 |
| `ftx.sql`    | `ftx_2022_11_08.csv.gz`    | blocks 15,900,000 – 15,924,999 | V2 |
| `normal.sql` | `normal_2023_03_15.csv.gz` | blocks 16,820,000 – 16,824,999 | V3 |

> Aave V3 mainnet was not deployed until **2023-01-27**, so the LUNA (2022-05)
> and FTX (2022-11) windows use **Aave V2** decoded tables; the normal-market
> control (2023-03) uses **Aave V3**. See `../README.md` for the full note.

## Option A — Dune Analytics (SQL, recommended for reproducibility)

The `.sql` files are written in **DuneSQL** (Trino dialect) against Spellbook
decoded tables (`uniswap_v3_ethereum.Pool_evt_Swap`,
`aave_v2_ethereum.LendingPool_evt_*`, `aave_v3_ethereum.Pool_evt_*`).

1. Open <https://dune.com/queries> → **New query** (free tier is sufficient).
2. Paste the contents of the target `.sql` file.
3. **Run**, then **Export → CSV**.
4. Rename to the fixture name (e.g. `luna_2022_05_09.csv`) and gzip:
   ```bash
   gzip -9 luna_2022_05_09.csv        # → luna_2022_05_09.csv.gz
   mv luna_2022_05_09.csv.gz ../
   ```
5. Verify: `python tools/verify_fixtures.py`.

Notes:
- Dune's `amount0`/`amount1` for Uniswap V3 swaps are already signed int256, so
  they match the extractor's two's-complement decoding.
- `date_format(..., '%Y-%m-%dT%H:%i:%sZ')` yields the schema-required ISO 8601
  UTC string ending in `Z`.

## Option B — Etherscan V2 API (canonical extractor)

The committed fixtures were produced this way. It needs only a free Etherscan
API key and no Dune account:

```bash
export ETHERSCAN_API_KEY=...          # or put it in repo-root .env
python tools/extract_fixtures.py --period all   # or: luna | ftx | normal
gzip -9 fixtures/backtest/*.csv                 # per AC9 (no Git LFS)
python tools/verify_fixtures.py
```

`tools/extract_fixtures.py` calls `module=logs&action=getLogs`, chunks each
block range under Etherscan's 1000-row cap, and decodes Uniswap V3 Swap and
Aave V2/V3 Borrow/Supply(Deposit)/LiquidationCall logs locally.

## Determinism

Both options draw from the same immutable on-chain logs, so the row set is
identical. Ordering is pinned by the final `ORDER BY block_number, log_index`
(Dune) / an in-memory sort on the same key (extractor). `tools/verify_fixtures.py`
additionally cross-checks 10 random rows/file against
`eth_getTransactionByHash` to guarantee no fabricated rows.
