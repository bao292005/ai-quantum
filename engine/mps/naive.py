"""Naive MPS tensor contraction → Fragility raw (Story 3A.1).

Reference implementation of the fragility model specified in
``research/mps_fragility_model.md`` (Story 3R.1). "Naive" = full-rank single
bipartition SVD, no bond-dimension truncation (that is Track 3C) and no
contraction-path optimization (Track 3D). Correctness first, performance later.

Pipeline (given adjacency ``A`` (N,N) and node features ``X`` (N,F)):

1. node mass     ``m = X · w``                     (w = feature weights, default 1)
2. weighted W    ``W = diag(√m) · A · diag(√m)``
3. Schmidt spec  ``σ = svdvals(W)``                (bipartition across the node cut)
4. Born probs    ``p_k = σ_k² / Σ σ_j²``
5. entropy       ``S = − Σ p_k ln p_k``            (nats, 0·ln0 ≡ 0)
6. fragility raw ``F_raw = S / ln(N)``             ∈ [0, 1]

The result is deterministic (singular values are unique and ordered; entropy is
invariant to the SVD gauge) and normalized to ``[0, 1]``. Calibration to the
``0–100`` alert score is Epic 4, not here.

Locked test oracle (``research/mps_fragility_model.md`` §7):
K3 triangle m=(1,1,1) → 0.789690; triangle m=(1,1,4) → 0.741117; path → 0.630930.
"""

from __future__ import annotations

import math
from typing import Any

import torch

# Probabilities at/below this are treated as exact zeros before the log, so
# Schmidt-rank padding (σ_k = 0) contributes 0 to the entropy sum.
_P_EPS = 1e-15


def fragility_raw(
    adjacency: torch.Tensor,
    features: torch.Tensor,
    *,
    feature_weights: torch.Tensor | None = None,
) -> float:
    """Compute the Fragility raw scalar from adjacency and feature tensors.

    Args:
        adjacency: ``(N, N)`` symmetric, non-negative coupling tensor
            (``engine.tensor.adjacency.adjacency_tensor``, Story 2B.1).
        features: ``(N, F)`` non-negative node feature tensor
            (``engine.tensor.features.feature_tensor``, Story 2B.2). Rows must be
            in the SAME node order as ``adjacency``.
        feature_weights: optional ``(F,)`` feature importance vector ``w`` (node
            mass ``m = X · w``). Defaults to all-ones (v1 baseline, Story 2R.1).

    Returns:
        Fragility raw in ``[0, 1]`` — ``0`` for a trivial graph (``N ≤ 1``, no
        coupling, or zero total mass), ``1`` for a maximally-entangled flat
        spectrum.

    Raises:
        ValueError: if ``adjacency`` is not square, ``features`` row count does
            not match ``N``, or any node mass is negative.
    """
    if adjacency.ndim != 2 or adjacency.shape[0] != adjacency.shape[1]:
        raise ValueError(
            f"adjacency must be square (N, N); got {tuple(adjacency.shape)}"
        )
    n = adjacency.shape[0]
    if features.ndim != 2 or features.shape[0] != n:
        raise ValueError(
            f"features must be (N, F) with N={n}; got {tuple(features.shape)}"
        )
    if n < 2:
        return 0.0

    a = adjacency.to(torch.float32)
    x = features.to(torch.float32)

    # Step 1 — node mass m = X · w
    if feature_weights is None:
        w = torch.ones(x.shape[1], dtype=torch.float32)
    else:
        w = feature_weights.to(torch.float32)
        if w.shape != (x.shape[1],):
            raise ValueError(
                f"feature_weights must be ({x.shape[1]},); got {tuple(w.shape)}"
            )
    m = x @ w
    if bool((m < 0).any()):
        raise ValueError("node mass m = X·w must be non-negative")
    if float(m.sum()) == 0.0:
        return 0.0

    # Step 2 — node-weighted coupling W = diag(√m) A diag(√m)
    root = torch.sqrt(m)
    w_coupling = root.unsqueeze(1) * a * root.unsqueeze(0)

    # Step 3 — Schmidt spectrum (bipartition SVD)
    sv = torch.linalg.svdvals(w_coupling)

    # Step 4 — Born probabilities
    s2 = sv * sv
    total = float(s2.sum())
    if total == 0.0:
        return 0.0
    p = s2 / s2.sum()
    p = p[p > _P_EPS]

    # Step 5 — von Neumann entanglement entropy (nats)
    entropy = float(-(p * torch.log(p)).sum())

    # Step 6 — normalize to [0, 1]
    return entropy / math.log(n)


def fragility_raw_from_graph(
    graph: dict[str, Any],
    *,
    feature_weights: torch.Tensor | None = None,
) -> float:
    """Convenience wrapper: build ``(A, X)`` from a GraphSnapshot then score.

    Builds the adjacency and feature tensors from ``graph`` (guaranteeing the
    shared node ordering) and delegates to :func:`fragility_raw`.
    """
    # Imported here to keep the tensor-only core free of the graph dependency.
    from engine.tensor.adjacency import adjacency_tensor
    from engine.tensor.features import feature_tensor

    a = adjacency_tensor(graph)
    x = feature_tensor(graph)
    return fragility_raw(a, x, feature_weights=feature_weights)


__all__ = ["fragility_raw", "fragility_raw_from_graph"]
