# Story 3R.2: Tensor-Network Systemic-Risk Literature Review `[RESEARCH]` — P1

## Purpose

Survey prior art behind QuantumRadar's core bet — using an **entanglement-entropy
/ spectral** measure of a financial coupling matrix as a **systemic-risk proxy** —
to (a) justify the approach, (b) borrow proven techniques, and (c) flag which of
our assumptions have **no precedent** (research risk). Feeds the Fragility model
(3R.1, `research/mps_fragility_model.md`) and the baseline comparison (3R.3).

Research-only artifact. No code changes. All sources below are real and were
retrieved via web search (2026-08); links are in §Sources.

---

## 1. What the literature establishes

### A. MPS / tensor trains are a legitimate ML/data technique (not just physics)

Stoudenmire & Schwab (NeurIPS 2016) showed that **matrix product states (MPS) =
the tensor-train decomposition** can parameterize supervised-learning models,
reaching <1% error on MNIST. MPS has since been used to compress neural-net weight
layers and for time-series ML (Phys. Rev. Research). **Takeaway:** the MPS
machinery QuantumRadar borrows (SVD along a bond, bond dimension = Schmidt rank,
truncation to keep dominant singular values) is a mature, well-understood tool
outside physics — Tracks 3B/3C (bond-dim sweep, SVD truncation) rest on solid
ground.

### B. Entropy of a correlation/coupling matrix's SVD spectrum predicts stress

Multiple independent lines find that **entropy derived from the singular/eigen
spectrum of a financial correlation matrix carries predictive power** for market
dynamics and can label *normal / bubble / crash* regimes (correlation-based
financial networks & entropy measures; entropy-based measures of connectedness for
crash forecasting; entropy of markets under macro shocks). Notably, **time-varying
entropy computed from the SVD of the correlation matrix** has been reported to
anticipate market moves. **Takeaway:** QuantumRadar's Step 3–5 (SVD of the coupling
matrix → Born probabilities `p_k = σ_k²/Σσ²` → `S = −Σ p_k ln p_k`) is a
recognized construction, not an invention; our novelty is the *input* (on-chain
DeFi coupling) not the *operator*.

### C. Spectral / eigenvalue measures are standard systemic-risk indicators

- The **largest eigenvalue** of a banking stability/leverage matrix is used as a
  *Spectral Systemic Risk Index* — the max expected system-wide capital loss per
  step — and an **eigen-pair "R-number"** gives an early-warning signal for
  contagion (Annals of Operations Research, 2021). The largest eigenvalue is a
  proxy for **spillover beyond pairwise correlations**.
- **Eigenvector (Bonacich) centrality** of an interbank connectivity matrix ranks
  systemically important nodes (Thai interbank study).
- Growth of the **largest eigenvalue of the interbank leverage matrix** can flip a
  system from stable to unstable — even via integration/diversification that is
  *believed* to add stability.

**Takeaway:** using the top of the spectrum as the dominant risk signal is
orthodox. This *cross-checks* our entropy measure: entropy summarizes the *whole*
normalized spectrum's shape, while `σ_1` alone is the classic scalar. 3R.3's
baseline should include a largest-eigenvalue / centrality detector precisely
because it is the established alternative.

### D. DeFi fragility specifically comes from *synchronizing dependence structure*

A 2026 network-based study of DeFi TVL dynamics finds systemic fragility is driven
by the **gradual synchronization of dependence structures rather than short-term
price volatility**, with elevated structural fragility coinciding with aggregate
liquidity instability **even when volatility is subdued**. Broader DeFi work models
**liquidation cascades** as price-contagion feedback loops that jump across
interconnected protocols. **Takeaway:** this is the strongest external validation
of the QuantumRadar thesis — "coupling structure, not volatility, is the leading
indicator." It supports our design choice that Fragility is **scale-invariant** in
magnitude and driven by how coupling is *distributed* across modes.

### E. Contagion has a topology-based "reproduction number"

A cascade condition analogous to the epidemic **R₀** characterizes whether one
defaulting node can trigger a system-wide cascade — an easily computed,
topology-only systemic-risk measure (assortative banking networks). **Takeaway:**
an appealing v2 cross-metric and a natural ground-truth companion to lead-time
evaluation in Epic 4/6.

### F. Random Matrix Theory warns: separate signal from noise

RMT (Marchenko–Pastur law) is the standard tool to distinguish **noise vs signal**
in financial correlation matrices; only eigenvalues outside the RMT bulk are
informative. **Takeaway (caveat, see risk R4):** our small graph (`N ≈ 10–15`, 2R.2)
is *below* the regime where MP noise dominates, so we can use the full spectrum in
v1 — but if `N` grows we must MP-filter the spectrum before computing entropy, or
entropy will drift with noise.

---

## 2. Lessons applied to QuantumRadar

| # | Lesson from literature | Design consequence |
|---|---|---|
| L1 | MPS = tensor-train; bond dim = Schmidt rank; SVD truncation is standard | 3B/3C (bond sweep, 95%-energy truncation) are principled, not ad-hoc |
| L2 | Entropy of a matrix's SVD spectrum predicts regime/crash | Validates 3R.1 Steps 3–5 (`S = −Σ p_k ln p_k`, `p_k = σ_k²/Σσ²`) |
| L3 | Largest eigenvalue / eigenvector centrality = orthodox systemic-risk scalar | 3R.3 baseline MUST include `σ_1`/centrality detector as the comparison |
| L4 | DeFi fragility = synchronization of dependence, not volatility | Supports scale-invariant `F_raw`; features are structure, not raw price |
| L5 | Topology cascade R₀ is a cheap systemic measure | Candidate v2 cross-metric + Epic 4 ground-truth companion |
| L6 | RMT: filter spectrum noise before trusting it | Safe at v1 N; add MP-filter gate if `N` grows (R4) |

---

## 3. Assumptions in QuantumRadar that LACK clear precedent (research risk)

These are where we go **beyond** the surveyed literature — the honest novelty /
risk surface. Each must be validated empirically (Epic 4) or flagged as unproven.

- **R1 — "Entanglement entropy of an on-chain DeFi coupling graph" is novel.**
  The literature computes spectral entropy of *price-correlation* matrices of
  traded assets. We compute it on a *heterogeneous protocol/pool/token coupling
  graph built from raw swap/borrow events*. No surveyed work does exactly this;
  the mapping (events → weighted adjacency → entropy) is our contribution and is
  **unvalidated** until LUNA/FTX backtests (Epic 4).

- **R2 — Node-mass weighting `W = diag(√m)·A·diag(√m)` with `m = X·w`.**
  Combining a feature-derived node mass with the adjacency before spectral
  analysis is our own construction. Standard work uses the bare correlation/leverage
  matrix. The `√m` symmetric scaling is a modelling choice, not a cited method.

- **R3 — Directionality is discarded (symmetrization).**
  We symmetrize naturally-directed borrow edges (2B.1 v1). Interbank literature
  often keeps directed leverage matrices (the largest eigenvalue there is of a
  *non-symmetric* matrix). Whether symmetrization loses cascade-direction signal is
  untested → candidate for 3R.2 follow-up if discrimination is weak.

- **R4 — Full spectrum used without RMT noise filtering.**
  Justified only because `N` is tiny in v1 (§1F). Not a precedent-backed choice at
  larger `N`.

- **R5 — Static per-snapshot entropy, no temporal model.**
  Literature emphasizes *time-varying* entropy trajectories and *synchronization
  over time* (§1B/§1D). Our v1 emits a per-block scalar; the alerting temporal logic
  (rate-of-change, persistence) is deferred to Epic 4 calibration and may be
  necessary for the 10-minute lead-time Success Signal.

---

## 4. Recommendation

- **Proceed** with the 3R.1 entropy-of-spectrum Fragility model — it is
  well-grounded on the *operator* side (L1, L2) and on the *DeFi thesis* side (L4).
- **De-risk R1/R2** empirically: Epic 4 must show the on-chain-graph entropy beats
  a trivial baseline (3R.3) on lead-time and false-positive rate; otherwise the
  novel input mapping is not earning its complexity.
- **Track R4/R5** as scaling/temporal gates, not v1 blockers.
- **Feed 3R.3:** the baseline detector must include a largest-eigenvalue /
  eigenvector-centrality scalar (L3) as the "is MPS worth it?" control.

---

## Sources

1. Stoudenmire & Schwab, "Supervised Learning with Quantum-Inspired Tensor Networks," NeurIPS 29 (2016) — [arXiv:1605.05775](https://arxiv.org/abs/1605.05775)
2. "Systemic Risk in DeFi: A Network-Based Fragility Analysis of TVL Dynamics" (2026) — [arXiv:2601.08540](https://arxiv.org/pdf/2601.08540)
3. "A perspective on correlation-based financial networks and entropy measures" — [arXiv:2004.09448](https://arxiv.org/pdf/2004.09448)
4. Qyrana, "Forecasting stock market crashes through entropy-based proper measures of connectedness" — [SSRN 5005696](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5005696)
5. "Early warning of systemic risk in global banking: eigen-pair R number for financial contagion," Annals of Operations Research (2021) — [Springer 10.1007/s10479-021-04120-1](https://link.springer.com/article/10.1007/s10479-021-04120-1)
6. Nacaskul & Sabborriboon, "Systemic Risk … Eigenvector Centrality Analysis of Thai Interbank Connectivity Matrices" — [SSRN 2710476](https://doi.org/10.2139/ssrn.2710476)
7. "A framework for analyzing contagion in assortative banking networks" — [PMC5322905](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5322905/)
8. "The Impact of Financial and Macroeconomic Shocks on the Entropy of Financial Markets" — [PMC7514798](https://pmc.ncbi.nlm.nih.gov/articles/PMC7514798/)
9. "Financial market predictability with tensor decomposition and links forecast," Applied Network Science — [Springer 10.1007/s41109-017-0028-1](https://appliednetsci.springeropen.com/articles/10.1007/s41109-017-0028-1)
