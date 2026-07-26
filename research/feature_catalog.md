# Story 2R.1: Node Feature Catalog & Sourcing

## Purpose

This report defines the **canonical node feature set** for the QuantumRadar
state graph and specifies, for each feature, its formula, data source, unit,
expected range, and missing-data policy.

It resolves a naming/semantics conflict between two existing sources and locks
the feature contract that **Story 2B.2 (Node Feature Tensor)** will implement.

This is a research-only artifact. It does **not** modify any code or schema
file. Any recommendation to change a locked contract (`graph_snapshot.schema.json`)
is captured here as a proposal for a separate build story.

References:

- Output feature contract (locked): `contracts/graph_snapshot.schema.json#/$defs/node/features`
- Input event schema: `contracts/tick_data.schema.json`
- Epic 2 Track 2R / Story 2B.2: `_bmad-output/epics.md`
- Topology dependency: Story 2R.2 (`connectivity` depends on graph topology)

---

## 1. Feature Set Reconciliation (AC1)

Two sources currently describe the node feature set, and they **disagree**:

| # | Schema 0.2 (`graph_snapshot.schema.json`, **LOCKED**) | Epics 2R.1 / 2B.2 (proposed) |
|---|---|---|
| 1 | `tvl_usd` | `tvl` |
| 2 | `volume_24h_usd` | `utilization` |
| 3 | `price_usd` | `price_delta` |
| 4 | `volatility` | `volatility` |
| 5 | `connectivity` | `borrow_rate` |

The conflict is not purely cosmetic:

- **`tvl_usd` ↔ `tvl`** — same concept; the schema name pins the unit (USD). Rename only.
- **`volatility`** — identical in both. No conflict.
- **`volume_24h_usd` vs `utilization`** — **different concepts.** Volume is a
  DEX throughput measure (Uniswap); utilization is a lending metric
  (`totalBorrows / totalLiquidity`, Aave).
- **`price_usd` vs `price_delta`** — related but different: an absolute price
  (level) vs a change/return over a window.
- **`connectivity` vs `borrow_rate`** — completely different: a graph-topology
  measure vs an Aave interest-rate signal.

### Constraint

`graph_snapshot.schema.json` states:
`"Contract locked; adding node/edge attributes is a breaking change (bump $id path)."`
Its `features` object also sets `additionalProperties: false` and lists all five
schema-0.2 names as `required`. Therefore the tensor layer (2B.2) **must** emit
exactly those five keys to pass validation. Choosing the epics set would require
bumping `$id` and rewriting `$defs/node/features` — a breaking change that
invalidates Story 0.2 and its tests.

### Decision

**Adopt the Schema 0.2 feature set as CANONICAL. Do NOT bump `$id`.**

Canonical feature vector (order fixed for tensor column indexing in 2B.2):

```
[ tvl_usd, volume_24h_usd, price_usd, volatility, connectivity ]   # F = 5
```

Rationale:

1. **Lowest risk / unblocks now.** Schema 0.2 is already locked, validated, and
   covered by tests. Keeping it lets 2B.2 proceed immediately with no schema
   churn and no re-validation of 0.2.
2. **Derivability.** All five schema-0.2 features are computable from the
   pipeline we already have (tick events + a price anchor + graph topology).
   The epics-only features (`utilization`, `borrow_rate`) are **Aave-reserve
   metrics not present in the tick_data event stream** (confirmed by
   `research/schema_abi_gap.md`: `borrowRate` is an ABI field explicitly
   deferred, and utilization needs `getReserveData` state that we do not yet
   ingest). Choosing them would add an external data dependency and block 2B.2.
3. **Consistency with prior directive.** Track 1B already deferred ABI-extra
   fields (`sqrtPriceX96`, `borrowRate`, …) until Epic 2 confirms need. This
   decision keeps that line: no premature schema expansion.

### Name mapping (epics → canonical)

| Epics name | Canonical name | Treatment |
|---|---|---|
| `tvl` | `tvl_usd` | Rename (same concept, USD unit pinned) |
| `volatility` | `volatility` | Identical |
| `price_delta` | `price_usd` | **Re-scope**: store absolute price level, not the delta. `price_delta` becomes an intermediate used to derive `volatility`. |
| `utilization` | *(dropped from v1)* | Aave-only; not in canonical set. See deferral below. |
| `borrow_rate` | *(dropped from v1)* | Aave-only; not in canonical set. See deferral below. |
| — | `volume_24h_usd` | Added by schema 0.2; DEX throughput. |
| — | `connectivity` | Added by schema 0.2; topology degree (see 2R.2). |

### Deferred Aave signals (future breaking change — NOT in v1)

`utilization` and `borrow_rate` are genuinely useful for **Aave fragility**
(Epic 3/4). They are intentionally out of scope for v1 because they require
Aave reserve state (`getReserveData`) that the current tick_data stream does not
carry. If Epic 3/4 fragility math proves they are required:

- This is a **breaking change**: bump `$id` of `graph_snapshot.schema.json`,
  extend `$defs/node/features` (e.g. add `utilization`, `borrow_rate`, both
  `number, minimum 0`), and re-run Story 0.2 validation/tests.
- Feed the change back to Story 0.2 as a `v2` schema story. Do **not** patch it
  from 2B.2.

> **Recommendation to PM/Architect:** keep the 5 locked features for v1. Revisit
> a `graph_snapshot.schema.json` v2 only when Epic 3 fragility math (Story 3R.1)
> demonstrates an Aave-utilization/borrow-rate dependency.

---

## 2. Feature Catalog (AC2, AC3)

Input schema 0.1 (`tick_data.schema.json`) fields available per event:
`block_number, block_timestamp, protocol, event_type, pool_address,
token0, token1, amount0, amount1, tx_hash, log_index`.

"Source" column legend:
- **0.1-direct** — computable purely from tick_data fields.
- **0.1 + price anchor** — computable from tick_data but needs a USD reference
  (stablecoin/WETH leg or oracle) to express in USD.
- **state snapshot** — needs on-chain state not in the event stream (e.g. pool
  reserves via `getReserves` / Aave `getReserveData`).
- **topology (2R.2)** — computed at graph-build time from the edge set.

| Feature | Formula / definition | Input (schema 0.1) | Source class | Unit | Expected range |
|---|---|---|---|---|---|
| `tvl_usd` | Total value locked = Σ(reserve_token · price_token) for the pool/protocol node. Reserves are **absolute balances**, not event deltas. | *not derivable from events alone* → needs pool reserves | **state snapshot** + price anchor | USD | `[0, ~1e10]`, ≥ 0 |
| `volume_24h_usd` | Rolling 24h swap volume: `Σ |amount_usd|` over swaps with `block_timestamp` in trailing 24h window. Token amount from `amount0/amount1`; USD via price anchor. | `event_type=swap`, `amount0`, `amount1`, `block_timestamp`, `token0/1` | **0.1 + price anchor** | USD | `[0, ~1e9]`, ≥ 0 |
| `price_usd` | Instantaneous pool price. From a Uniswap swap: relative price `p = |amount1 / amount0|` (token0-in-token1), anchored to USD when one leg is a stablecoin/WETH. Fallback: oracle. | `amount0`, `amount1` (ratio); `token0/1` to identify anchor leg | **0.1 + price anchor** (relative price is 0.1-direct; USD needs anchor) | USD | `(0, ~1e6]`, ≥ 0 |
| `volatility` | Realized volatility = `std(r)` over a window, where `r = log-returns of price_usd` (a rolling series of the feature above). | derived from `price_usd` time series (which uses `amount0/1`, `block_timestamp`) | **derived** (needs price series; no single event) | dimensionless (std of log-returns) | `[0, ~2]`, ≥ 0 |
| `connectivity` | Normalized node degree = `degree(node) / (N − 1)` from the graph edge set (topology defined in 2R.2). | graph edges (not raw events) | **topology (2R.2)** | dimensionless | `[0, 1]` (schema enforces `max 1`) |

### Derivable vs auxiliary-source summary (AC3)

- **Directly / mostly from schema 0.1:**
  - `volume_24h_usd` — token-level volume is 0.1-direct; only the USD conversion
    needs a price anchor.
  - `price_usd` — the *relative* swap price is 0.1-direct; USD anchoring needs a
    stablecoin/WETH leg (usually available) or an oracle fallback.
  - `volatility` — computed from the `price_usd` series, so it inherits the same
    dependency (no extra external source beyond price).

- **Requires an auxiliary source (RISK — cannot be built from events alone):**
  - `tvl_usd` — **needs pool/reserve state snapshot** (`getReserves` for
    Uniswap; `getReserveData` for Aave). This is the single biggest sourcing gap
    for the feature set. See risk note below.
  - `connectivity` — **needs graph topology** from Story 2R.2 (computed at
    graph-build time, not per-event).

> **v1 risk / proxy note for `tvl_usd`:** because reserves are not in the event
> stream, v1 options are (a) periodic `eth_call` to read reserves (adds an RPC
> dependency), or (b) a **cumulative-flow proxy**: maintain a running balance by
> summing signed `amount0/amount1` deltas from mint/burn/swap events from a known
> seed block. Option (b) is 0.1-derivable but drifts without a seed snapshot.
> Recommend (a) for accuracy; flag to Story 2B.2 / 4R that a reserve-read path is
> required, otherwise `tvl_usd` must ship as a proxy in v1.

---

## 3. Missing-Data Policy & Normalization Hints (AC4)

Policy legend:
- **0** — substitute `0` and emit a warning.
- **last-known** — carry forward the previous valid value; `0` only if no prior.
- **NaN→2B.2** — leave `NaN` at feature-build time; Story 2B.2 replaces `NaN`
  with `0` and logs a warning (per its AC).

| Feature | Missing-data policy | Reason | Range for 2B.3 | Suggested normalization (2B.3 hint) |
|---|---|---|---|---|
| `tvl_usd` | last-known → else `0` | TVL is a slow-moving level; a gap should hold, not zero out. | `[0, ~1e10]` heavy-tailed | **log1p → minmax**. Raw minmax collapses small pools; log first. |
| `volume_24h_usd` | `0` | No trades in window is a *legitimate* zero, not missing. | `[0, ~1e9]` heavy-tailed | **log1p → minmax**. |
| `price_usd` | last-known → NaN→2B.2 | Price should persist across a quiet block; only zero as last resort. | `(0, ~1e6]` per-token scale varies hugely | **zscore per token** (or log then zscore). Do NOT global-minmax across tokens of different magnitudes. |
| `volatility` | `0` (insufficient history) with warning | Too few points → treat as calm (0), not missing. | `[0, ~2]` | **minmax with cap** (clip at a max, e.g. 2). |
| `connectivity` | `0` (isolated node) | A node with no edges has degree 0 by definition. | `[0, 1]` already normalized | **none** — already in `[0,1]` per schema. |

Notes for Story 2B.3:
- Features live on very different scales (`price_usd` for WBTC vs a memecoin can
  span 10+ orders of magnitude) → prefer **per-feature** (and for `price_usd`,
  **per-token**) normalization over a single global scaler.
- `connectivity` is pre-normalized; excluding it from the scaler avoids a no-op
  transform that could shift its `[0,1]` semantics.
- Heavy-tailed monetary features (`tvl_usd`, `volume_24h_usd`) need a **log**
  step before min-max, otherwise a few whale pools saturate the scale.

---

## Decision

**Canonical node feature set (v1), locked to `graph_snapshot.schema.json`:**

```
tvl_usd, volume_24h_usd, price_usd, volatility, connectivity      # F = 5, fixed order
```

- **Schema bump:** **NO.** Keep `graph_snapshot.schema.json` `$id` unchanged.
  Story 2B.2 emits exactly these 5 keys.
- **Epics feature names** (`tvl`, `utilization`, `price_delta`, `borrow_rate`)
  are reconciled via the mapping in §1; `utilization` and `borrow_rate` are
  **deferred** (Aave reserve-state metrics, out of v1 scope).
- **Future v2 (Aave fragility):** if Epic 3/4 (Story 3R.1) requires
  `utilization` / `borrow_rate`, treat as a **breaking change** — bump `$id`,
  extend `$defs/node/features`, and route back through Story 0.2. Do not patch
  from the tensor layer.
- **Open sourcing risk to flag downstream:** `tvl_usd` needs a reserve-state
  read (or a documented cumulative-flow proxy); `connectivity` depends on
  Story 2R.2 topology. Both are called out for 2B.2 / 4R planning.
