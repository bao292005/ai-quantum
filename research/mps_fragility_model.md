# Story 3R.1: MPS Fragility Math Spec `[RESEARCH]` — P0

## Purpose

This document is the **formal mathematical specification** for turning a
`GraphSnapshot`'s tensors into a scalar **Fragility raw** value via a
quantum-inspired **entanglement entropy** measure. It is the P0 prerequisite that
unblocks all of Epic 3: Story **3A.1 (Naive Tensor Contraction)** implements the
pipeline defined here, and Tracks **3B/3C** optimize it. The worked 3-node oracle
in §7 is the **exact test oracle** 3A.1 must reproduce.

Research/design artifact — defines math, not code. All numbers in §7 are verified
through the real `engine.tensor` code path (`/opt/anaconda3/bin/python3`).

### Inputs (contract from Epic 2)

| Symbol | Source | Shape | Properties |
|---|---|---|---|
| `A` | `engine.tensor.adjacency.adjacency_tensor` (2B.1) | `(N, N)` float32 | symmetric, `A_ij ≥ 0`, zero diagonal (unless self-loop) |
| `X` | `engine.tensor.features.feature_tensor` (2B.2) | `(N, F=5)` float32 | `X ≥ 0`, columns = `FEATURE_ORDER` (2R.1), finite (NaN/inf sanitized to 0) |

`N` is dynamic per snapshot (`N ≈ 10–15` for v1 per 2R.2), read from the node
list — never hard-coded. Feature columns (fixed order, 2R.1):
`tvl_usd, volume_24h_usd, price_usd, volatility, connectivity`.

Row/column index `i ∈ {0..N−1}` is the node order in `graph["nodes"]`, **shared**
by `A` and `X` (guaranteed by 2B.1/2B.2).

### Hyperparameters (v1 defaults; tuned in Epic 4)

| Symbol | Meaning | v1 default | Tuned by |
|---|---|---|---|
| `w ∈ R^F` | feature importance weights (node mass) | `w = (1,1,1,1,1)` | Epic 4 calibration (4.1/4.2) |
| log base | entropy unit | natural log `ln` (nats) | fixed |

`X` is assumed already normalized (Story 2B.3) so features are on a comparable
scale, making uniform `w` a sensible v1 baseline.

---

## 1. Model overview

QuantumRadar treats the DeFi state graph as a **bipartite pure quantum state**.
The node-weighted coupling matrix `W` plays the role of the (unnormalized)
amplitude matrix of a state `|ψ⟩ = Σ_ij W_ij |i⟩_L |j⟩_R` across the cut between a
"left" copy and "right" copy of the node set. Its **Schmidt decomposition** is the
SVD of `W`; the **entanglement entropy** across that cut is the von Neumann
entropy of the squared, normalized singular values.

**Thesis:** systemic fragility ⇔ high entanglement. When coupling energy is spread
evenly across many spectral modes (flat spectrum), a shock in one asset propagates
across the whole network → **high entropy → high fragility**. When one tightly-knit
cluster dominates (one large singular value), the rest is effectively decoupled →
**low entropy → low fragility**.

This directly realizes the "MPS / tensor-train → entanglement entropy" mandate:
- The single **bipartition SVD of `W`** is the minimal, faithful MPS realization
  for the v1 star/single-cut topology (3A.1 naive).
- The **bond dimension** `χ` = number of retained singular values (Schmidt rank).
  Sweeping `χ` is Track 3B; truncating to `χ` keeping 95% spectral energy is
  Track 3C (SVD truncation) — both operate on exactly the spectrum defined here.

---

## 2. Pipeline (the function 3A.1 implements)

Given `A ∈ R^{N×N}`, `X ∈ R^{N×F}`:

**Step 1 — Node mass.** Reduce features to a per-node non-negative scalar:

```
m = X · w              # m ∈ R^N,  m_i = Σ_f w_f · X_{i,f},  m_i ≥ 0
```

**Step 2 — Node-weighted coupling.** Scale each coupling by the geometric mean of
its endpoints' masses:

```
W = diag(√m) · A · diag(√m)          # W_ij = √(m_i · m_j) · A_ij
```

`W` is symmetric and non-negative. Economic reading: coupling between two
high-activity nodes (large pools, big flows) contributes more systemic risk than
coupling between dormant nodes.

**Step 3 — Schmidt spectrum (SVD).** Bipartition across the node cut:

```
W = U Σ Vᵀ ,   singular values  σ_1 ≥ σ_2 ≥ … ≥ σ_N ≥ 0
```

Since `W` is symmetric, `σ_k = |λ_k|` (absolute eigenvalues). `torch.linalg.svdvals(W)`
is the reference call. Bond dimension `χ` = count of `σ_k > 0` (Schmidt rank).

**Step 4 — Born-rule probabilities.**

```
p_k = σ_k² / Σ_j σ_j²        (Σ_k p_k = 1)
```

**Step 5 — von Neumann entanglement entropy** (`0·ln0 ≡ 0`):

```
S = − Σ_k p_k · ln p_k          (nats)
```

**Step 6 — Fragility raw** (normalize to `[0, 1]`):

```
F_raw = S / ln(N)               for N ≥ 2
F_raw = 0                        for N ≤ 1
```

`ln(N)` is the maximum possible entropy of `N` modes (a perfectly flat spectrum),
so `F_raw ∈ [0, 1]`: `1` = maximally entangled/fragile, `0` = a single dominant
mode (or no coupling).

### Degenerate guards
- `N ≤ 1`, or `Σ m_i = 0` (all features zero), or `Σ σ² = 0` (no edges) ⇒ `F_raw = 0`.
- Drop `p_k ≤ ε` (`ε = 1e-15`) before the log to avoid `−0·(−inf)` (Schmidt rank
  padding zeros contribute `0` to `S`).

---

## 3. Properties

- **Range:** `F_raw ∈ [0, 1]`. (Epic 4 maps this to the `0–100` Fragility score.)
- **Deterministic:** singular values are unique and ordered; `S` is invariant to
  the sign/rotation gauge freedom of `U, V`. Verified bit-identical on repeat
  (satisfies 3A.1 AC "result deterministic").
- **Scale invariance:** multiplying `A` (or all masses) by a constant `c > 0`
  leaves the normalized spectrum `p` — and thus `F_raw` — unchanged. Fragility is a
  measure of *coupling structure*, not absolute magnitude. (Absolute-level risk is
  injected later via calibration / feature levels.)
- **Permutation invariance:** relabeling nodes permutes rows/cols of `A` and `X`
  identically ⇒ same spectrum ⇒ same `F_raw`.
- **Monotone in coupling spread:** more, more-uniform edges raise `F_raw`;
  concentration into one node/cluster lowers it (see oracles §7).

---

## 4. Contraction order (compute cost)

For v1 (`N ≤ 15`) the whole cost is dominated by one `N×N` SVD, `O(N³)` ≈ a few
thousand FLOPs — negligible. The ordered operations:

```
X (N×F) · w (F)         → m   :  O(N·F)
diag(√m) A diag(√m)     → W   :  O(N²)
svdvals(W)              → σ   :  O(N³)
σ²; normalize; −Σp ln p → S   :  O(N)
S / ln N                → F_raw
```

At v1 scale the tensor is `<1 KB` (2R.2), so the naive path already meets the
Epic 3 `<30 ms` budget with wide margin; 3B/3C truncation matters only when
`N ≥ 128` (2R.2 threshold).

---

## 5. Epic 3 handoffs

| Track / Story | Consumes from this spec | Note |
|---|---|---|
| **3A.1 Naive contraction** | Steps 1–6 verbatim; oracle §7 as test | full-rank SVD, no truncation |
| **3A.4 Baseline metrics** | `F_raw` range + latency of §4 | tag `baseline-v0` |
| **3B Bond dimension** | keep top-`χ` of `σ` before Steps 4–6; sweep `χ` | accuracy vs baseline `F_raw` |
| **3C SVD truncation** | `auto_rank(σ, energy=0.95)` on the same spectrum | reconstruction/entropy error < 5% |
| **3R.2 Literature review** | justify entropy-as-risk proxy; §8 open assumptions | cites prior art |
| **3R.3 Naive baseline detector** | compare against a non-MPS scalar (e.g. `Σσ` / max degree) | proves MPS adds value |

## 6. Epic 4 handoff (calibration — out of scope here)

`F_raw ∈ [0,1]` is a raw, uncalibrated structural score. Epic 4 (4.1 LUNA, 4.2 FTX)
fits the mapping to the alert scale, e.g.

```
Fragility_score = 100 · σ_sigmoid( α · (F_raw − β) )      # α, β tuned on fixtures
alert = RED   if score ≥ 90
        YELLOW if score ≥ 70
```

The **Success Signal** (RED ≥ 10 min before the first liquidation) is validated
there, not here. This spec only guarantees a deterministic, well-ranged `F_raw`.

---

## 7. Worked 3-node oracle (test oracle for 3A.1)

All values verified through `adjacency_tensor` + `feature_tensor` + Steps 1–6
(natural log). Nodes are `pool`-typed; edge `edge_type` is irrelevant to the math
(only `weight` and endpoints enter `A`).

### Oracle A — complete triangle `K3`, uniform mass (primary, hand-checkable)

Setup: 3 nodes, every pair joined by `weight = 1`; every feature `= 0.2` so
`m_i = Σ_f 1·0.2 = 1.0`. Hence `W = A`.

```
A = W = [[0,1,1],
         [1,0,1],
         [1,1,0]]           m = (1, 1, 1)
```

Eigenvalues of `K3` adjacency: `{2, −1, −1}` ⇒ `σ = (2, 1, 1)`.

```
σ²      = (4, 1, 1),   Σσ² = 6
p       = (4/6, 1/6, 1/6) = (0.666667, 0.166667, 0.166667)
S       = −(0.666667·ln0.666667 + 2·0.166667·ln0.166667)
        =  0.270310 + 0.597253 = 0.867563  nats
ln N    = ln 3 = 1.098612
F_raw   = 0.867563 / 1.098612 = 0.789690
```

**→ `F_raw(Oracle A) = 0.789690`** (`± 1e-6`).

### Oracle B — triangle, concentrated mass `(1,1,4)` (exercises feature weighting)

Setup: same triangle (`weight = 1`); node 3's features all `= 0.8` ⇒ `m_3 = 4`,
nodes 1–2 features all `= 0.2` ⇒ `m = (1, 1, 4)`, `√m = (1, 1, 2)`.

```
W = diag(√m) A diag(√m) = [[0,1,2],
                           [1,0,2],
                           [2,2,0]]
```

Eigenvalues `{ (1+√33)/2, (1−√33)/2, −1 } = {3.372281, −2.372281, −1}` ⇒
`σ = (3.372281, 2.372281, 1)`.

```
σ²    = (11.372281, 5.627719, 1.0),   Σσ² = 18.0
p     = (0.631794, 0.312651, 0.055556)
S     = 0.814200  nats
F_raw = 0.814200 / 1.098612 = 0.741117
```

**→ `F_raw(Oracle B) = 0.741117`** (`± 1e-6`).

### Contrast — path `1–2–3`, uniform mass (discrimination sanity)

Setup: edges `(1,2)` and `(2,3)` only, `weight = 1`, `m = (1,1,1)`.

```
σ = (√2, √2, 0),  p = (0.5, 0.5, 0),  S = ln 2 = 0.693147
F_raw = 0.693147 / 1.098612 = 0.630930
```

**Interpretation check:** fully-coupled triangle **0.7897** > concentrated triangle
**0.7411** > chain **0.6309**. Spreading coupling raises fragility; concentrating it
into one heavy node or a chain lowers it — as required by the thesis.

### Reference implementation (for the 3A.1 test)

```python
import math, torch
from engine.tensor.adjacency import adjacency_tensor
from engine.tensor.features import feature_tensor, FEATURE_ORDER

W_FEATURES = torch.ones(len(FEATURE_ORDER))          # w = ones(5), v1 default

def fragility_raw(graph: dict) -> float:
    A = adjacency_tensor(graph)                      # (N, N)
    X = feature_tensor(graph)                        # (N, 5)
    n = A.shape[0]
    m = X @ W_FEATURES                               # node mass (N,)
    if n < 2 or float(m.sum()) == 0.0:
        return 0.0
    root = torch.sqrt(m)
    W = root.unsqueeze(1) * A * root.unsqueeze(0)    # diag(√m) A diag(√m)
    s2 = torch.linalg.svdvals(W) ** 2
    total = float(s2.sum())
    if total == 0.0:
        return 0.0
    p = s2 / total
    p = p[p > 1e-15]
    S = float(-(p * torch.log(p)).sum())
    return S / math.log(n)
```

---

## 8. Open assumptions & research risks (feed 3R.2 / 3R.3)

1. **Symmetric coupling.** `A` symmetrizes directed `borrow_position` edges (2B.1
   v1 decision). A directed model would use `W Wᵀ` (or a channel-state) for the
   bipartition; deferred until 3R.2 shows directionality changes the ranking.
2. **Entropy = risk proxy is a modelling hypothesis**, not established prior art in
   DeFi. 3R.2 literature review must justify (tensor-network entanglement as a
   systemic-risk proxy) or flag it as novel/unvalidated.
3. **Uniform feature weight `w`.** Placeholder; some features (e.g. `price_usd`
   level) may be poor mass proxies. Epic 4 calibration owns `w`, `α`, `β`.
4. **Single bipartition.** v1 uses one cut (left|right node copies). A true
   N-site MPS chain with multiple cuts (mean/max entanglement over cuts) is a
   possible v2 refinement if the single-cut score under-discriminates on real
   fixtures.
5. **Scale invariance** means absolute leverage/TVL levels do not move `F_raw`.
   If Epic 4 finds absolute magnitude must matter, add a non-normalized term
   (e.g. blend `F_raw` with `Σσ`) — recorded as a calibration lever, not changed here.

---

## Decision (summary)

- **Fragility raw** = `S / ln(N)`, where `S` = von Neumann entropy of the
  normalized squared singular values of `W = diag(√m) · A · diag(√m)`, `m = X·w`.
- Range `[0, 1]`, deterministic, scale/permutation invariant, monotone in coupling
  spread.
- Bond dimension `χ` = retained Schmidt rank → clean hooks for 3B (sweep) and 3C
  (95%-energy truncation).
- Test oracles: **A = 0.789690**, **B = 0.741117** (`± 1e-6`), verified via the
  real Epic-2 tensor code path.
- No contract/schema change. Feeds Epic 3 build (3A.1) and Epic 4 calibration.
