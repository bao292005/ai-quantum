-- ftx.sql — reproduces fixtures/backtest/ftx_2022_11_08.csv.gz
--
-- FTX collapse window. Block range 15,900,000 → 15,924,999.
-- Protocols: Uniswap V3 USDC/WETH 0.05% pool + Aave V2 LendingPool (Aave V3
-- was NOT on mainnet until 2023-01-27, so this window uses V2).
--
-- Engine: Dune Analytics (Spellbook decoded tables, DuneSQL / Trino dialect).
-- Reproducible SQL equivalent of tools/extract_fixtures.py --period ftx.
-- Returns the Story 0.1 11-column tick-data schema, ordered (block_number, log_index).
--
-- Run: paste into a new Dune query, Run, Export → CSV, rename to
--      ftx_2022_11_08.csv and gzip (see queries/README.md).

WITH univ3_swaps AS (
    SELECT
        evt_block_number                           AS block_number,
        evt_block_time                             AS block_timestamp,
        'uniswap_v3'                               AS protocol,
        'swap'                                     AS event_type,
        contract_address                           AS pool_address,
        0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 AS token0,  -- USDC
        0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 AS token1,  -- WETH
        CAST(amount0 AS VARCHAR)                   AS amount0,  -- signed int256
        CAST(amount1 AS VARCHAR)                   AS amount1,
        evt_tx_hash                                AS tx_hash,
        evt_index                                  AS log_index
    FROM uniswap_v3_ethereum.Pool_evt_Swap
    WHERE contract_address = 0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640  -- USDC/WETH 0.05%
      AND evt_block_number BETWEEN 15900000 AND 15924999
),

aave_borrow AS (
    SELECT
        evt_block_number, evt_block_time,
        'aave_v2' AS protocol, 'borrow' AS event_type,
        0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9 AS pool_address,
        reserve   AS token0,
        0x0000000000000000000000000000000000000000 AS token1,
        CAST(amount AS VARCHAR) AS amount0,
        '0'       AS amount1,
        evt_tx_hash, evt_index
    FROM aave_v2_ethereum.LendingPool_evt_Borrow
    WHERE evt_block_number BETWEEN 15900000 AND 15924999
),

aave_supply AS (
    SELECT
        evt_block_number, evt_block_time,
        'aave_v2' AS protocol, 'supply' AS event_type,
        0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9 AS pool_address,
        reserve   AS token0,
        0x0000000000000000000000000000000000000000 AS token1,
        CAST(amount AS VARCHAR) AS amount0,
        '0'       AS amount1,
        evt_tx_hash, evt_index
    FROM aave_v2_ethereum.LendingPool_evt_Deposit
    WHERE evt_block_number BETWEEN 15900000 AND 15924999
),

aave_liquidation AS (
    SELECT
        evt_block_number, evt_block_time,
        'aave_v2' AS protocol, 'liquidation' AS event_type,
        0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9 AS pool_address,
        collateralAsset                 AS token0,
        debtAsset                       AS token1,
        CAST(liquidatedCollateralAmount AS VARCHAR) AS amount0,
        CAST(debtToCover AS VARCHAR)                AS amount1,
        evt_tx_hash, evt_index
    FROM aave_v2_ethereum.LendingPool_evt_LiquidationCall
    WHERE evt_block_number BETWEEN 15900000 AND 15924999
),

unioned AS (
    SELECT * FROM univ3_swaps
    UNION ALL SELECT * FROM aave_borrow
    UNION ALL SELECT * FROM aave_supply
    UNION ALL SELECT * FROM aave_liquidation
)

SELECT
    block_number,
    date_format(block_timestamp, '%Y-%m-%dT%H:%i:%sZ') AS block_timestamp,
    protocol,
    event_type,
    pool_address,
    token0,
    token1,
    amount0,
    amount1,
    tx_hash,
    log_index
FROM unioned
ORDER BY block_number, log_index;
