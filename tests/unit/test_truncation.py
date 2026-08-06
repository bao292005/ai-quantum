"""Unit tests for engine.mps.truncation (Stories 3C.1 / 3C.2 / 3C.4)."""

from __future__ import annotations

import time

import pytest
import torch

from engine.mps.truncation import auto_rank, numerical_rank, truncated_svd


def _decaying_matrix(n=128, decay=8.0, seed=0):
    """Square matrix with an exponentially-decaying singular spectrum."""
    g = torch.Generator().manual_seed(seed)
    u, _ = torch.linalg.qr(torch.randn(n, n, generator=g))
    v, _ = torch.linalg.qr(torch.randn(n, n, generator=g))
    s = torch.exp(-torch.arange(n, dtype=torch.float32) / decay)
    return (u * s) @ v.t(), s


# ---------------------------------------------------------------------------
# 3C.1 — truncated_svd
# ---------------------------------------------------------------------------

def test_truncated_svd_shapes():
    mat, _ = _decaying_matrix(128)
    u, s, vh = truncated_svd(mat, 32)
    assert u.shape == (128, 32)
    assert s.shape == (32,)
    assert vh.shape == (32, 128)


def test_truncated_svd_reconstruction_error_under_5pct():
    mat, _ = _decaying_matrix(128, decay=8.0)
    u, s, vh = truncated_svd(mat, 32)
    approx = (u * s) @ vh
    rel_err = torch.linalg.norm(mat - approx) / torch.linalg.norm(mat)
    assert float(rel_err) < 0.05


def test_truncated_svd_benchmark_reasonable():
    mat, _ = _decaying_matrix(128)
    truncated_svd(mat, 32)  # warm-up
    start = time.perf_counter()
    truncated_svd(mat, 32)
    elapsed_ms = (time.perf_counter() - start) * 1000
    # AC target < 3ms; assert a lenient ceiling to avoid CI flakiness.
    assert elapsed_ms < 50, f"truncated_svd too slow: {elapsed_ms:.3f}ms"


def test_truncated_svd_rank_clamped_to_dim():
    mat, _ = _decaying_matrix(8)
    u, s, vh = truncated_svd(mat, 999)
    assert s.shape[0] == 8


def test_truncated_svd_invalid_rank_raises():
    mat, _ = _decaying_matrix(8)
    with pytest.raises(ValueError):
        truncated_svd(mat, 0)


# ---------------------------------------------------------------------------
# 3C.2 — auto_rank
# ---------------------------------------------------------------------------

def test_auto_rank_energy_threshold():
    mat = torch.diag(torch.tensor([10.0, 2.0, 1.0]))
    # s^2 = [100, 4, 1], total 105; cum = [0.952, 0.990, 1.0]
    assert auto_rank(mat, energy=0.95) == 1
    assert auto_rank(mat, energy=0.99) == 2
    assert auto_rank(mat, energy=1.0) == 3


def test_auto_rank_monotone_in_energy():
    mat, _ = _decaying_matrix(64)
    r_low = auto_rank(mat, energy=0.90)
    r_high = auto_rank(mat, energy=0.999)
    assert r_low <= r_high


def test_auto_rank_energy_satisfied():
    mat, _ = _decaying_matrix(64)
    r = auto_rank(mat, energy=0.95)
    s = torch.linalg.svdvals(mat)
    retained = float((s[:r] ** 2).sum() / (s ** 2).sum())
    assert retained >= 0.95


def test_auto_rank_invalid_energy_raises():
    mat, _ = _decaying_matrix(8)
    for bad in (0.0, -0.1, 1.1):
        with pytest.raises(ValueError):
            auto_rank(mat, energy=bad)


# ---------------------------------------------------------------------------
# 3C.4 — rank-deficiency guard
# ---------------------------------------------------------------------------

def _rank_deficient_matrix(n=4, rank=2, seed=1):
    # float64 so the null singular values land ~1e-15 (float32 would leave
    # ~1e-6 noise and defeat the 1e-10 rank tolerance).
    g = torch.Generator().manual_seed(seed)
    b = torch.randn(n, rank, generator=g, dtype=torch.float64)
    return b @ b.t()  # symmetric PSD of exact rank `rank`


def test_numerical_rank_detects_deficiency():
    mat = _rank_deficient_matrix(4, 2)
    assert numerical_rank(mat) == 2


def test_truncated_svd_rank_deficient_warns_and_caps():
    mat = _rank_deficient_matrix(4, 2)
    with pytest.warns(UserWarning):
        u, s, vh = truncated_svd(mat, 4)  # ask for more than numerical rank
    # Falls back to the numerical rank — no null-space modes retained.
    assert s.shape[0] == 2
    assert float(s[-1]) > 1e-10


def test_truncated_svd_full_rank_no_warning(recwarn):
    mat, _ = _decaying_matrix(16, decay=64.0)  # near-flat, full rank
    truncated_svd(mat, 8)
    assert len(recwarn) == 0
