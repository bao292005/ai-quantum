-- normal.sql — reproduces fixtures/backtest/normal_2023_03_15.csv.gz
--
-- Normal-market control window. Block range 16,820,000 → 16,824,999.
-- Protocols: Uniswap V3 USDC/WETH 0.05% pool + Aave V3 Pool (Aave V3 mainnet
-- is live from 2023-01-27, so this control window uses V3, not V2).
--
-- Engine: Dune Analytics (Spellbook decoded tables, DuneSQL / Trino dialect).
-- Reproducible SQL equivalent of tools/extract_fixtures.py --period normal.
-- Returns the Story 0.1 11-column tick-data schema, ordered (block_number, log_index).
--
-- Expected behaviour: the pipeline must NOT raise a RED alert on this control
-- set (false-positive guard). The single isolated liquidation is routine.
--
-- Run: paste into a new Dune query, Run, Export → CSV, rename to
--      normal_2023_03_15.csv and gzip (see queries/README.md).

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
      AND evt_block_number BETWEEN 16820000 AND 16824999
),

aave_borrow AS (
    SELECT
        evt_block_number, evt_block_time,
        'aave_v3' AS protocol, 'borrow' AS event_type,
        0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2 AS pool_address,  -- Aave V3 Pool
        reserve   AS token0,
        0x0000000000000000000000000000000000000000 AS token1,
        CAST(amount AS VARCHAR) AS amount0,
        '0'       AS amount1,
        evt_tx_hash, evt_index
    FROM aave_v3_ethereum.Pool_evt_Borrow
    WHERE evt_block_number BETWEEN 16820000 AND 16824999
),

aave_supply AS (
    SELECT
        evt_block_number, evt_block_time,
        'aave_v3' AS protocol, 'supply' AS event_type,
        0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2 AS pool_address,
        reserve   AS token0,
        0x0000000000000000000000000000000000000000 AS token1,
        CAST(amount AS VARCHAR) AS amount0,
        '0'       AS amount1,
        evt_tx_hash, evt_index
    FROM aave_v3_ethereum.Pool_evt_Supply
    WHERE evt_block_number BETWEEN 16820000 AND 16824999
),

aave_liquidation AS (
    SELECT
        evt_block_number, evt_block_time,
        'aave_v3' AS protocol, 'liquidation' AS event_type,
        0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2 AS pool_address,
        collateralAsset                 AS token0,
        debtAsset                       AS token1,
        CAST(liquidatedCollateralAmount AS VARCHAR) AS amount0,
        CAST(debtToCover AS VARCHAR)                AS amount1,
        evt_tx_hash, evt_index
    FROM aave_v3_ethereum.Pool_evt_LiquidationCall
    WHERE evt_block_number BETWEEN 16820000 AND 16824999
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
