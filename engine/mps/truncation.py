"""SVD truncation primitives (Track 3C — Stories 3C.1 / 3C.2 / 3C.4).

Reusable low-rank tools for the MPS engine. At v1 scale (``N ≈ 10–15``, Story
2R.2) the naive full-SVD forward pass (Story 3A.1) already clears the latency
budget by ~290× (`metrics/baseline.md`), so these primitives are **not wired
into `fragility_raw` for v1** — they are the toolkit for when the graph grows
past the 2R.2 dense/sparse threshold (``N ≥ 128``). See
`research/epic3_optimization_decision.md`.

- ``truncated_svd(matrix, rank)`` — rank-``r`` SVD (Story 3C.1).
- ``auto_rank(matrix, energy)`` — smallest rank retaining an energy fraction
  of the squared singular spectrum (Story 3C.2).
- ``numerical_rank`` + the rank-deficiency guard inside ``truncated_svd`` —
  detect near-singular matrices and fall back to the numerical rank instead of
  retaining null-space modes (Story 3C.4).
"""

from __future__ import annotations

import warnings

import torch

# Singular values at/below this (relative to the matrix scale in practice, but
# used absolutely here) are treated as numerical zeros.
_RANK_TOL = 1e-10


def numerical_rank(matrix: torch.Tensor, *, tol: float = _RANK_TOL) -> int:
    """Number of singular values strictly greater than ``tol``."""
    sv = torch.linalg.svdvals(matrix)
    return int((sv > tol).sum())


def truncated_svd(
    matrix: torch.Tensor,
    rank: int,
    *,
    tol: float = _RANK_TOL,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Rank-``r`` truncated SVD: ``matrix ≈ (U * S) @ Vh``.

    Args:
        matrix: 2-D tensor to decompose.
        rank: number of leading singular triplets to keep (clamped to
            ``min(matrix.shape)``).
        tol: numerical-zero threshold for the rank-deficiency guard.

    Returns:
        ``(U, S, Vh)`` with ``U`` ``(m, r)``, ``S`` ``(r,)``, ``Vh`` ``(r, n)``.

    Raises:
        ValueError: if ``rank < 1``.

    Warns:
        UserWarning: if ``matrix`` is rank-deficient (``numerical rank < k``);
            the effective rank is capped at the numerical rank so null-space
            modes are never retained (Story 3C.4 fallback — no crash).
    """
    if rank < 1:
        raise ValueError(f"rank must be >= 1; got {rank}")

    u, s, vh = torch.linalg.svd(matrix, full_matrices=False)
    k = s.shape[0]
    effective = min(rank, k)

    num_rank = int((s > tol).sum())
    if num_rank < k:
        warnings.warn(
            f"rank-deficient matrix (numerical rank {num_rank} < {k}); "
            f"capping truncation rank to {num_rank}",
            stacklevel=2,
        )
        effective = min(effective, max(1, num_rank))

    return u[:, :effective], s[:effective], vh[:effective, :]


def auto_rank(
    matrix: torch.Tensor,
    energy: float = 0.95,
    *,
    tol: float = _RANK_TOL,
) -> int:
    """Smallest rank ``R`` with ``Σ S[:R]² / Σ S² ≥ energy``.

    Args:
        matrix: 2-D tensor.
        energy: target retained energy fraction in ``(0, 1]``.

    Returns:
        The rank ``R`` (at least 1, at most ``min(matrix.shape)``).

    Raises:
        ValueError: if ``energy`` is not in ``(0, 1]``.
    """
    if not 0.0 < energy <= 1.0:
        raise ValueError(f"energy must be in (0, 1]; got {energy}")

    sv = torch.linalg.svdvals(matrix)
    sq = sv * sv
    total = float(sq.sum())
    if total == 0.0:
        return 1

    cumulative = torch.cumsum(sq, dim=0) / total
    idx = int(torch.searchsorted(cumulative, torch.tensor(energy, dtype=cumulative.dtype)))
    return min(idx + 1, sv.shape[0])


__all__ = ["truncated_svd", "auto_rank", "numerical_rank"]
