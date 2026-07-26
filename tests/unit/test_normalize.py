"""Unit tests for engine.tensor.normalize (Story 2B.3)."""

from __future__ import annotations

import pytest
import torch

from engine.tensor.normalize import NormalizationState, normalize


def _sample() -> torch.Tensor:
    # 3 columns; col 2 has an outlier.
    return torch.tensor(
        [
            [1.0, 10.0, 5.0],
            [2.0, 20.0, 5.0],
            [3.0, 30.0, 1000.0],
            [4.0, 40.0, 5.0],
        ],
        dtype=torch.float32,
    )


# ---------------------------------------------------------------------------
# AC1 — API / method validation
# ---------------------------------------------------------------------------

def test_invalid_method_raises() -> None:
    with pytest.raises(ValueError, match="Unknown method"):
        normalize(_sample(), method="robust")


def test_returns_state_and_preserves_shape_dtype() -> None:
    out, state = normalize(_sample(), method="minmax")
    assert out.shape == (4, 3)
    assert out.dtype == torch.float32
    assert isinstance(state, NormalizationState)


# ---------------------------------------------------------------------------
# AC2 — minmax → [0,1]
# ---------------------------------------------------------------------------

def test_minmax_range_with_outlier() -> None:
    out, _ = normalize(_sample(), method="minmax")
    assert torch.all(out >= 0.0)
    assert torch.all(out <= 1.0)
    # each column min == 0 and max == 1
    assert torch.allclose(out.min(dim=0).values, torch.zeros(3))
    assert torch.allclose(out.max(dim=0).values, torch.ones(3))


# ---------------------------------------------------------------------------
# AC3 — zscore → mean≈0, std≈1
# ---------------------------------------------------------------------------

def test_zscore_mean_std() -> None:
    out, _ = normalize(_sample(), method="zscore")
    mean = out.mean(dim=0)
    std = out.std(dim=0, unbiased=False)
    assert torch.allclose(mean, torch.zeros(3), atol=1e-6)
    assert torch.allclose(std, torch.ones(3), atol=1e-6)


# ---------------------------------------------------------------------------
# AC2/AC3/AC5 — constant-column guard (no NaN)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method", ["minmax", "zscore"])
def test_constant_column_no_nan(method: str) -> None:
    t = torch.tensor([[5.0, 1.0], [5.0, 2.0], [5.0, 3.0]], dtype=torch.float32)
    out, _ = normalize(t, method=method)
    assert torch.isfinite(out).all()
    # constant column 0 → all zeros
    assert torch.all(out[:, 0] == 0.0)


def test_single_row_no_nan() -> None:
    t = torch.tensor([[1.0, 2.0, 3.0]], dtype=torch.float32)
    for method in ("minmax", "zscore"):
        out, _ = normalize(t, method=method)
        assert torch.isfinite(out).all()


# ---------------------------------------------------------------------------
# AC4 — state persistence / reuse
# ---------------------------------------------------------------------------

def test_apply_matches_normalize() -> None:
    t = _sample()
    out, state = normalize(t, method="zscore")
    reapplied = state.apply(t)
    assert torch.allclose(out, reapplied)


def test_state_applies_fit_params_to_new_tensor() -> None:
    train = _sample()
    _, state = normalize(train, method="minmax")
    # inference tensor at the train column min/max → maps to 0 and 1.
    infer = torch.tensor([[1.0, 10.0, 5.0], [4.0, 40.0, 1000.0]], dtype=torch.float32)
    out = state.apply(infer)
    assert out[0, 0].item() == pytest.approx(0.0)   # col0 min
    assert out[1, 0].item() == pytest.approx(1.0)   # col0 max
    assert out.dtype == torch.float32


# ---------------------------------------------------------------------------
# AC6 — round-trip with feature_tensor (2B.2)
# ---------------------------------------------------------------------------

def test_roundtrip_with_feature_tensor() -> None:
    from engine.graph.builder import ZERO_ADDRESS, build_graph
    from engine.tensor.features import feature_tensor

    A = "0x" + "a" * 40
    W = "0x" + "c" * 40
    B = "0x" + "b" * 40
    tx = "0x" + "e" * 64

    def ev(block, pool, t0, t1, a0, a1):
        return {
            "block_number": block, "block_timestamp": "2023-10-24T12:00:00Z",
            "protocol": "uniswap_v3", "event_type": "swap", "pool_address": pool,
            "token0": t0, "token1": t1, "amount0": a0, "amount1": a1,
            "tx_hash": tx, "log_index": 0,
        }

    g = build_graph([
        ev(1, "0x" + "1" * 40, A, W, "1000", "1"),
        ev(2, "0x" + "2" * 40, W, B, "1", "1000"),
    ])
    ft = feature_tensor(g)
    out, state = normalize(ft, method="minmax")
    assert out.shape == ft.shape
    assert torch.isfinite(out).all()
    assert torch.all(out >= 0.0) and torch.all(out <= 1.0)
