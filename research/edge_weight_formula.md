# Story 2A.4: Edge Weight Formula

## Purpose

Defines the canonical formula that Story 2A.3 (Graph Builder) uses to assign
`Edge.weight` for every edge in a `GraphSnapshot`. The weight must land in
`[0, 1]` (locked by `graph_snapshot.schema.json#/$defs/edge`) and reflect the
strength of a liquidity-flow / risk-propagation channel between two nodes.

Research-only artifact — no code. The 5 worked examples in §4 are the **ground
truth** for the unit tests Story 2A.3 will write.

References:
- Contract: `contracts/graph_snapshot.schema.json#/$defs/edge` (`weight` ∈ [0,1])
- Edge rules: `research/graph_topology.md` (2R.2)
- Volume / price limits: `research/feature_catalog.md` (2R.1)
- Consumer: Story 2A.3 (`_bmad-output/epics.md#Story 2A.3`)

---

## 1. The Three Components (AC1)

For an edge `e` connecting two nodes, the raw (un-normalized) score combines
three factors:

```
raw(e) = volume_usd(e) · time_decay(e) · corr(e)
```

### 1.1 `volume_usd(e)` — flow magnitude

USD value flowing through the edge, by `edge_type`:

| edge_type | volume_usd(e) source (from schema 0.1 events) |
|---|---|
| `liquidity_flow` (pool→token) | Σ `|amount|` of swap/mint/burn events on the pool for that token, over the snapshot window, × price anchor |
| `liquidity_flow` (protocol→pool) | Σ pool's edge volumes (aggregate of the pool's token edges) |
| `borrow_position` (Aave pool→reserve) | Σ borrow/supply/withdraw/liquidation `amount` for that reserve, × price anchor |
| `shared_collateral` (pool↔pool) | min(exposure of shared token in pool A, in pool B) — the bottleneck exposure of the contagion channel |

**Price limitation (from 2R.1):** USD needs a stablecoin/WETH leg or oracle. If
no price anchor is available in v1, use **token-native volume as a proxy** and
record it — this only rescales `raw`; because the final step is snapshot-relative
normalization (§2), a consistent proxy still yields sensible relative weights.

### 1.2 `time_decay(e)` — recency (AC3)

Recent flows matter more (a swap 5 minutes ago is more relevant to current
fragility than one 20 hours ago):

```
time_decay(e) = exp(-λ · Δt(e))
Δt(e)         = t_latest − t_event(e)        # seconds, ≥ 0
λ             = ln(2) / half_life
```

- `t_latest` = the most recent `block_timestamp` in the snapshot.
- `t_event(e)` = `block_timestamp` of the event that produced edge `e` (for
  aggregated edges, use the most recent contributing event).
- **Default `half_life = 3600 s` (1 hour)** → `λ = ln(2)/3600 ≈ 1.9254e-4 s⁻¹`.
  Half-life is a tunable knob; 1h is a reasonable v1 default for intraday
  systemic-risk signals. Larger half-life = slower decay (more history retained).

Properties: `Δt=0` (newest) → `time_decay = 1`; `Δt = half_life` → `0.5`;
`Δt → ∞` → `0`. Always in `(0, 1]`. **Guarantees AC3**: two edges with equal
`volume_usd` and equal `corr` but different times → the newer one has larger
`time_decay` → larger `raw` → larger normalized weight.

### 1.3 `corr(e)` — channel-strength multiplier per edge_type

A base multiplier in `(0, 1]` capturing how strongly the edge type transmits
risk:

| edge_type | corr(e) | rationale |
|---|---|---|
| `liquidity_flow` | `1.0` | direct liquidity movement — full-strength channel |
| `borrow_position` | `0.7` (default) | lending linkage; can later be replaced by collateral↔debt asset correlation |
| `shared_collateral` | `0.5` (default) or 30-day price correlation of the shared token, clamped to (0,1] | indirect contagion via a common asset |

Defaults are v1 constants; §Future notes how to replace `borrow_position` /
`shared_collateral` with data-driven correlations. `corr` is always in `(0, 1]`
so it never zeroes or inflates a channel by itself.

---

## 2. Normalization to [0, 1] (AC2)

Normalize **per snapshot** by the maximum raw score across all edges:

```
M          = max( raw(e) for e in snapshot.edges )
weight(e)  = raw(e) / M         if M > 0
weight(e)  = 0.0                if M == 0    # div-0 guard
```

Properties:
- **Bounded:** every `raw(e) ≥ 0` and `raw(e) ≤ M`, so `weight(e) ∈ [0, 1]`. The
  strongest edge in the snapshot gets exactly `1.0`. **Auto-saturating** — an
  arbitrarily large volume cannot push weight above 1 (satisfies AC4 case 4).
- **Div-0 guard:** if all edges have `raw = 0` (e.g. zero volume everywhere), or
  there are 0 edges, every weight is `0.0` — no `NaN`/division error.
- **Single edge:** with one edge, `M = raw(e0)`; weight = `1.0` if `raw>0`, else
  `0.0`.

> **Alternative (documented, not chosen for v1):** a parameter-free squashing
> `weight(e) = tanh(raw(e) / scale)` is also bounded to [0,1) but requires
> choosing `scale` and is not snapshot-relative. Min-max is preferred for v1
> because it is self-scaling and needs no tuning. If cross-snapshot comparability
> of absolute weights becomes important later, switch to a fixed-`scale` tanh.

---

## 3. Time-Decay Worked Illustration (AC3)

Two `liquidity_flow` edges (`corr = 1.0`), same `volume_usd = 100`, at the same
snapshot (`t_latest = T`):

| edge | volume_usd | Δt (s) | time_decay = exp(-λΔt) | raw = vol·decay·1 |
|---|---:|---:|---:|---:|
| e_new | 100 | 0 | 1.000 | 100.0 |
| e_old | 100 | 3600 | 0.500 | 50.0 |

`M = 100` → `weight(e_new) = 1.00`, `weight(e_old) = 0.50`. **Newest edge has the
larger weight.** ✓

---

## 4. Five Boundary Cases (AC4)

Reference table for Story 2A.3 unit tests. `λ = ln(2)/3600`, `t_latest = T`.

### Case 1 — Single edge (div-0 guard)
- Input: 1 edge, `volume_usd = 250`, `Δt = 0`, `liquidity_flow`.
  `raw = 250·1·1 = 250`, `M = 250` → **weight = 1.0**.
- Sub-case (all-zero): 1 edge, `volume_usd = 0` → `raw = 0`, `M = 0` → guard →
  **weight = 0.0** (no division).

### Case 2 — Two edges, equal volume, different time (time-decay)
- e_new: `vol=100, Δt=0` → raw 100; e_old: `vol=100, Δt=3600` → raw 50. `M=100`.
- **weight(e_new)=1.0, weight(e_old)=0.5** — newest larger. ✓

### Case 3 — Zero-volume edge
- e_z: `vol=0, Δt=0` alongside e1: `vol=100, Δt=0` (raw 100). `M=100`.
- `raw(e_z)=0·1·1=0` → **weight(e_z)=0.0** regardless of recency. e1 → 1.0.

### Case 4 — Very large volume (saturation)
- e_big: `vol=1_000_000_000, Δt=0` → raw 1e9; e_small: `vol=100, Δt=0` → raw 100.
  `M = 1e9`.
- **weight(e_big)=1.0** (bounded, not >1); weight(e_small)=1e-7 ≈ 0.0.

### Case 5 — Different edge_type (corr multiplier)
- Same `vol=100, Δt=0` for three edges of different type:
  | edge_type | corr | raw = 100·1·corr |
  |---|---:|---:|
  | liquidity_flow | 1.0 | 100 |
  | borrow_position | 0.7 | 70 |
  | shared_collateral | 0.5 | 50 |
- `M = 100` → **weights: 1.0 / 0.70 / 0.50** respectively.

---

## Decision

**Formula:** `raw(e) = volume_usd(e) · exp(-λ·Δt(e)) · corr(e)`, then
`weight(e) = raw(e) / max_raw` (snapshot-relative min-max), with `weight = 0` when
`max_raw = 0`.

- **Half-life = 1 hour** → `λ = ln(2)/3600 ≈ 1.9254e-4 s⁻¹` (tunable).
- **corr:** `liquidity_flow = 1.0`, `borrow_position = 0.7`, `shared_collateral = 0.5`
  (v1 constants).
- **weight ∈ [0, 1]** guaranteed by min-max; div-0 guarded; auto-saturating.
- **volume_usd** uses a token-native proxy where a USD price anchor is missing
  (per 2R.1) — flag in the builder.

### Future (v2, not v1)
- Replace `borrow_position` corr with real collateral↔debt asset correlation.
- Replace `shared_collateral` corr with rolling price correlation of the shared token.
- Consider fixed-`scale` `tanh` normalization if absolute cross-snapshot weight
  comparability is needed.
