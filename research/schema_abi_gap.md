# Story 1R.2: Event Schema ↔ ABI Reconciliation

## Purpose

This report reconciles the current normalized schema:

`contracts/tick_data.schema.json`

against real on-chain event ABIs for:

- Uniswap V3 Pool:
  - `Swap`
  - `Mint`
  - `Burn`
- Aave V3 Pool:
  - `Borrow`
  - `Supply`
  - `Withdraw`
  - `LiquidationCall`

The goal is to identify whether the current schema has enough fields to support Track 1B decoder work before raw Ethereum logs are decoded into normalized tick data.

This is a research-only artifact. It does not modify `contracts/tick_data.schema.json`.

---

## ABI Sources

### Uniswap V3 Pool

- Source: Uniswap v3-core canonical event interface
- File: `contracts/interfaces/pool/IUniswapV3PoolEvents.sol`
- URL: https://github.com/Uniswap/v3-core/blob/main/contracts/interfaces/pool/IUniswapV3PoolEvents.sol
- Branch/date used: `main`, retrieved 2026-07-09
- Events checked:
  - `Swap`
  - `Mint`
  - `Burn`

Relevant event definitions:

```solidity
event Mint(
    address sender,
    address indexed owner,
    int24 indexed tickLower,
    int24 indexed tickUpper,
    uint128 amount,
    uint256 amount0,
    uint256 amount1
);

event Burn(
    address indexed owner,
    int24 indexed tickLower,
    int24 indexed tickUpper,
    uint128 amount,
    uint256 amount0,
    uint256 amount1
);

event Swap(
    address indexed sender,
    address indexed recipient,
    int256 amount0,
    int256 amount1,
    uint160 sqrtPriceX96,
    uint128 liquidity,
    int24 tick
);
```

### Aave V3 Pool

- Source: Etherscan verified Aave V3 Pool contract and Aave v3-core `IPool.sol`
- Ethereum mainnet Pool address: `0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2`
- Etherscan URL: https://etherscan.io/address/0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2#code
- Canonical interface URL: https://github.com/aave/aave-v3-core/blob/master/contracts/interfaces/IPool.sol
- Branch/date used: `master`, retrieved 2026-07-09
- Events checked:
  - `Borrow`
  - `Supply`
  - `Withdraw`
  - `LiquidationCall`

Relevant event definitions:

```solidity
event Supply(
    address indexed reserve,
    address user,
    address indexed onBehalfOf,
    uint256 amount,
    uint16 indexed referralCode
);

event Withdraw(
    address indexed reserve,
    address indexed user,
    address indexed to,
    uint256 amount
);

event Borrow(
    address indexed reserve,
    address user,
    address indexed onBehalfOf,
    uint256 amount,
    DataTypes.InterestRateMode interestRateMode,
    uint256 borrowRate,
    uint16 indexed referralCode
);

event LiquidationCall(
    address indexed collateralAsset,
    address indexed debtAsset,
    address indexed user,
    uint256 debtToCover,
    uint256 liquidatedCollateralAmount,
    address liquidator,
    bool receiveAToken
);
```

Note: `DataTypes.InterestRateMode` is ABI-encoded as `uint8` in the event signature.

---

## Current Schema Fields

Schema file:

`contracts/tick_data.schema.json`

The current schema is a normalized event schema shared by Uniswap V3, Aave V3, Aave V2, Track 1A/1B/1D and Epic 2 Graph builder.

Important constraint:

- `additionalProperties: false`

This means decoder output cannot contain fields outside the schema unless the schema is patched.

| Field | Required | Type | Constraint / Notes |
|---|---:|---|---|
| `block_number` | yes | integer | Ethereum block number, minimum `0` |
| `block_timestamp` | yes | string | ISO 8601 UTC timestamp ending with `Z` |
| `protocol` | yes | string enum | `uniswap_v3`, `aave_v3`, `aave_v2` |
| `event_type` | yes | string enum | `swap`, `mint`, `burn`, `borrow`, `supply`, `withdraw`, `liquidation` |
| `pool_address` | yes | string | Contract address, pool or lending pool |
| `token0` | yes | string | Ethereum address |
| `token1` | yes | string | Ethereum address |
| `amount0` | yes | string | Decimal string, negative allowed |
| `amount1` | yes | string | Decimal string, negative allowed |
| `tx_hash` | yes | string | Transaction hash |
| `log_index` | yes | integer | Log index, minimum `0` |

---

## Event Coverage

### Uniswap V3 — Swap

Signature:

`Swap(address,address,int256,int256,uint160,uint128,int24)`

topic0:

`0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67`

Encoding:

- indexed: `sender`, `recipient`
- non-indexed: `amount0`, `amount1`, `sqrtPriceX96`, `liquidity`, `tick`

| ABI field | Schema field | Status |
|---|---|---|
| `sender` | — | missing |
| `recipient` | — | missing |
| `amount0` | `amount0` | match |
| `amount1` | `amount1` | match |
| `sqrtPriceX96` | — | missing |
| `liquidity` | — | missing |
| `tick` | — | missing |

### Uniswap V3 — Mint

Signature:

`Mint(address,address,int24,int24,uint128,uint256,uint256)`

topic0:

`0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde`

Encoding:

- indexed: `owner`, `tickLower`, `tickUpper`
- non-indexed: `sender`, `amount`, `amount0`, `amount1`

| ABI field | Schema field | Status |
|---|---|---|
| `sender` | — | missing |
| `owner` | — | missing |
| `tickLower` | — | missing |
| `tickUpper` | — | missing |
| `amount` | — | missing |
| `amount0` | `amount0` | match |
| `amount1` | `amount1` | match |

### Uniswap V3 — Burn

Signature:

`Burn(address,int24,int24,uint128,uint256,uint256)`

topic0:

`0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c`

Encoding:

- indexed: `owner`, `tickLower`, `tickUpper`
- non-indexed: `amount`, `amount0`, `amount1`

| ABI field | Schema field | Status |
|---|---|---|
| `owner` | — | missing |
| `tickLower` | — | missing |
| `tickUpper` | — | missing |
| `amount` | — | missing |
| `amount0` | `amount0` | match |
| `amount1` | `amount1` | match |

### Aave V3 — Borrow

Signature:

`Borrow(address,address,address,uint256,uint8,uint256,uint16)`

topic0:

`0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0`

Encoding:

- indexed: `reserve`, `onBehalfOf`, `referralCode`
- non-indexed: `user`, `amount`, `interestRateMode`, `borrowRate`

| ABI field | Schema field | Status |
|---|---|---|
| `reserve` | `token0` | renamed |
| `user` | — | missing |
| `onBehalfOf` | — | missing |
| `amount` | `amount0` | renamed |
| `interestRateMode` | — | missing |
| `borrowRate` | — | missing |
| `referralCode` | — | missing |

### Aave V3 — Supply

Signature:

`Supply(address,address,address,uint256,uint16)`

topic0:

`0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61`

Encoding:

- indexed: `reserve`, `onBehalfOf`, `referralCode`
- non-indexed: `user`, `amount`

| ABI field | Schema field | Status |
|---|---|---|
| `reserve` | `token0` | renamed |
| `user` | — | missing |
| `onBehalfOf` | — | missing |
| `amount` | `amount0` | renamed |
| `referralCode` | — | missing |

### Aave V3 — Withdraw

Signature:

`Withdraw(address,address,address,uint256)`

topic0:

`0x3115d1449a7b732c986cba18244e897a450f61e1bb8d589cd2e69e6c8924f9f7`

Encoding:

- indexed: `reserve`, `user`, `to`
- non-indexed: `amount`

| ABI field | Schema field | Status |
|---|---|---|
| `reserve` | `token0` | renamed |
| `user` | — | missing |
| `to` | — | missing |
| `amount` | `amount0` | renamed |

### Aave V3 — LiquidationCall

Signature:

`LiquidationCall(address,address,address,uint256,uint256,address,bool)`

topic0:

`0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286`

Encoding:

- indexed: `collateralAsset`, `debtAsset`, `user`
- non-indexed: `debtToCover`, `liquidatedCollateralAmount`, `liquidator`, `receiveAToken`

| ABI field | Schema field | Status |
|---|---|---|
| `collateralAsset` | `token0` | renamed |
| `debtAsset` | `token1` | renamed |
| `user` | — | missing |
| `debtToCover` | `amount0` | renamed |
| `liquidatedCollateralAmount` | `amount1` | renamed |
| `liquidator` | — | missing |
| `receiveAToken` | — | missing |

---

## Fields Matched

These fields are direct ABI-to-schema matches.

| Event | ABI field | Schema field | Notes |
|---|---|---|---|
| Uniswap V3 `Swap` | `amount0` | `amount0` | Direct match |
| Uniswap V3 `Swap` | `amount1` | `amount1` | Direct match |
| Uniswap V3 `Mint` | `amount0` | `amount0` | Direct match |
| Uniswap V3 `Mint` | `amount1` | `amount1` | Direct match |
| Uniswap V3 `Burn` | `amount0` | `amount0` | Direct match |
| Uniswap V3 `Burn` | `amount1` | `amount1` | Direct match |

---

## Fields Missing from Schema

These fields exist in the ABI events but are not currently represented in `contracts/tick_data.schema.json`.

| Event | Missing field | Why needed |
|---|---|---|
| Uniswap V3 `Swap` | `sender` | Decode swap caller |
| Uniswap V3 `Swap` | `recipient` | Decode swap recipient |
| Uniswap V3 `Swap` | `sqrtPriceX96` | Required to reconstruct pool price after swap |
| Uniswap V3 `Swap` | `liquidity` | Required to track pool liquidity after swap |
| Uniswap V3 `Swap` | `tick` | Required to track pool tick/price state after swap |
| Uniswap V3 `Mint` | `sender` | Decode liquidity mint sender |
| Uniswap V3 `Mint` | `owner` | Decode liquidity position owner |
| Uniswap V3 `Mint` | `tickLower` | Required for liquidity range lower bound |
| Uniswap V3 `Mint` | `tickUpper` | Required for liquidity range upper bound |
| Uniswap V3 `Mint` | `amount` | Required for minted liquidity amount |
| Uniswap V3 `Burn` | `owner` | Decode burned liquidity owner |
| Uniswap V3 `Burn` | `tickLower` | Required for liquidity range lower bound |
| Uniswap V3 `Burn` | `tickUpper` | Required for liquidity range upper bound |
| Uniswap V3 `Burn` | `amount` | Required for burned liquidity amount |
| Aave V3 `Borrow` | `user` | Decode user initiating borrow |
| Aave V3 `Borrow` | `onBehalfOf` | Decode debt beneficiary |
| Aave V3 `Borrow` | `interestRateMode` | Required to distinguish stable/variable debt mode |
| Aave V3 `Borrow` | `borrowRate` | Required for borrow-rate analytics |
| Aave V3 `Borrow` | `referralCode` | ABI field not represented in current schema |
| Aave V3 `Supply` | `user` | Decode supplier |
| Aave V3 `Supply` | `onBehalfOf` | Decode beneficiary receiving supplied position |
| Aave V3 `Supply` | `referralCode` | ABI field not represented in current schema |
| Aave V3 `Withdraw` | `user` | Decode withdrawer |
| Aave V3 `Withdraw` | `to` | Decode receiver of withdrawn asset |
| Aave V3 `LiquidationCall` | `user` | Decode liquidated user |
| Aave V3 `LiquidationCall` | `liquidator` | Decode liquidator |
| Aave V3 `LiquidationCall` | `receiveAToken` | Decode whether liquidator receives aToken or underlying asset |

---

## Fields in Schema Not in ABI (excess/renamed)

These fields are not direct event ABI fields. Some are ingestion metadata, while others are normalized names used by the schema.

| Schema field | Related ABI field/event | Status | Notes |
|---|---|---|---|
| `block_number` | block metadata | excess | Not part of event ABI; required ingestion metadata |
| `block_timestamp` | block metadata | excess | Not part of event ABI; required ingestion metadata |
| `protocol` | derived metadata | excess | Not part of event ABI; normalized protocol label |
| `event_type` | derived from `topic0` | excess | Not part of event ABI; normalized event label |
| `pool_address` | log emitter address | excess | Not part of event parameters; derived from emitting contract address |
| `token0` | Uniswap pool metadata; Aave `reserve`; Aave `collateralAsset` | renamed | Normalized token field |
| `token1` | Uniswap pool metadata; Aave `debtAsset` | renamed | Normalized token field |
| `amount0` | Uniswap `amount0`; Aave `amount`; Aave `debtToCover` | renamed | Direct match for Uniswap; normalized amount field for Aave |
| `amount1` | Uniswap `amount1`; Aave `liquidatedCollateralAmount` | renamed | Direct match for Uniswap; normalized amount field for Aave liquidation |
| `tx_hash` | transaction metadata | excess | Not part of event ABI; required ingestion metadata |
| `log_index` | log metadata | excess | Not part of event ABI; required ingestion metadata |

---

## Patch Proposal

Schema has material gaps for Uniswap V3 price reconstruction and Aave V3 lending/liquidation semantics.

Because `additionalProperties` is currently `false`, decoder output containing ABI-native fields will fail validation unless the schema is extended.

Proposed additive patch for `contracts/tick_data.schema.json`:

```json
{
  "properties": {
    "sender": {
      "type": "string",
      "pattern": "^0x[0-9a-fA-F]{40}$"
    },
    "recipient": {
      "type": "string",
      "pattern": "^0x[0-9a-fA-F]{40}$"
    },
    "owner": {
      "type": "string",
      "pattern": "^0x[0-9a-fA-F]{40}$"
    },
    "user": {
      "type": "string",
      "pattern": "^0x[0-9a-fA-F]{40}$"
    },
    "onBehalfOf": {
      "type": "string",
      "pattern": "^0x[0-9a-fA-F]{40}$"
    },
    "to": {
      "type": "string",
      "pattern": "^0x[0-9a-fA-F]{40}$"
    },
    "liquidator": {
      "type": "string",
      "pattern": "^0x[0-9a-fA-F]{40}$"
    },
    "sqrtPriceX96": {
      "type": "string",
      "pattern": "^[0-9]+$",
      "maxLength": 80
    },
    "liquidity": {
      "type": "string",
      "pattern": "^[0-9]+$",
      "maxLength": 80
    },
    "tick": {
      "type": "integer"
    },
    "tickLower": {
      "type": "integer"
    },
    "tickUpper": {
      "type": "integer"
    },
    "amount": {
      "type": "string",
      "pattern": "^[0-9]+(\\.[0-9]+)?$",
      "maxLength": 80
    },
    "reserve": {
      "type": "string",
      "pattern": "^0x[0-9a-fA-F]{40}$"
    },
    "collateralAsset": {
      "type": "string",
      "pattern": "^0x[0-9a-fA-F]{40}$"
    },
    "debtAsset": {
      "type": "string",
      "pattern": "^0x[0-9a-fA-F]{40}$"
    },
    "debtToCover": {
      "type": "string",
      "pattern": "^[0-9]+(\\.[0-9]+)?$",
      "maxLength": 80
    },
    "liquidatedCollateralAmount": {
      "type": "string",
      "pattern": "^[0-9]+(\\.[0-9]+)?$",
      "maxLength": 80
    },
    "interestRateMode": {
      "type": "integer",
      "enum": [1, 2]
    },
    "borrowRate": {
      "type": "string",
      "pattern": "^[0-9]+$",
      "maxLength": 80
    },
    "referralCode": {
      "type": "integer",
      "minimum": 0
    },
    "receiveAToken": {
      "type": "boolean"
    }
  }
}
```

Recommendation: do not update `contracts/tick_data.schema.json` in this story without PM/Architect approval, because Story 0.1 and `tests/unit/test_tick_schema.py` depend on the current schema.

---

## Decoder Hints

| Event | topic0 | Indexed fields | Non-indexed fields |
|---|---|---|---|
| Uniswap V3 `Swap` | `0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67` | `sender`, `recipient` | `amount0`, `amount1`, `sqrtPriceX96`, `liquidity`, `tick` |
| Uniswap V3 `Mint` | `0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde` | `owner`, `tickLower`, `tickUpper` | `sender`, `amount`, `amount0`, `amount1` |
| Uniswap V3 `Burn` | `0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c` | `owner`, `tickLower`, `tickUpper` | `amount`, `amount0`, `amount1` |
| Aave V3 `Borrow` | `0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0` | `reserve`, `onBehalfOf`, `referralCode` | `user`, `amount`, `interestRateMode`, `borrowRate` |
| Aave V3 `Supply` | `0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61` | `reserve`, `onBehalfOf`, `referralCode` | `user`, `amount` |
| Aave V3 `Withdraw` | `0x3115d1449a7b732c986cba18244e897a450f61e1bb8d589cd2e69e6c8924f9f7` | `reserve`, `user`, `to` | `amount` |
| Aave V3 `LiquidationCall` | `0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286` | `collateralAsset`, `debtAsset`, `user` | `debtToCover`, `liquidatedCollateralAmount`, `liquidator`, `receiveAToken` |

---

## Summary

The current schema is sufficient for normalized metadata and simple amount-level ingestion, but it does not fully preserve ABI-native information from Uniswap V3 and Aave V3 events.

Most important gaps:

- Uniswap V3 `Swap` is missing `sqrtPriceX96`, `liquidity`, and `tick`.
- Uniswap V3 liquidity events are missing position owner and tick range fields.
- Aave V3 lending events are missing user-level fields such as `user`, `onBehalfOf`, `to`, and liquidation-specific fields.
- Aave V3 borrow analytics require `interestRateMode` and `borrowRate`.

Patch should be reviewed with PM/Architect before modifying `contracts/tick_data.schema.json`.
