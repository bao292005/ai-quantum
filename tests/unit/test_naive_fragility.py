"""Unit tests for engine.mps.naive (Story 3A.1 — Naive Tensor Contraction).

Oracle values are locked by research/mps_fragility_model.md §7 and verified
through the real Epic-2 tensor code path:
  Oracle A (K3 triangle, m=(1,1,1))      -> 0.789690
  Oracle B (triangle,     m=(1,1,4))      -> 0.741117
  Path 1-2-3 (m=(1,1,1))                  -> 0.630930
"""

from __future__ import annotations

import math

import pytest
import torch

from engine.mps.naive import fragility_raw, fragility_raw_from_graph
from engine.tensor.adjacency import adjacency_tensor
from engine.tensor.features import FEATURE_ORDER, feature_tensor

TOL = 1e-5


def _feats(values):
    return dict(zip(FEATURE_ORDER, values))


def _graph(feature_rows, edges):
    return {
        "snapshot_id": "550e8400-e29b-41d4-a716-446655440000",
        "block_range": {"start": 0, "end": 1},
        "created_at": "2023-01-01T00:00:00Z",
        "nodes": [
            {"id": f"n{i + 1}", "type": "pool", "features": _feats(f)}
            for i, f in enumerate(feature_rows)
        ],
        "edges": edges,
    }


_TRIANGLE = [
    {"src": "n1", "dst": "n2", "weight": 1.0, "edge_type": "liquidity_flow"},
    {"src": "n1", "dst": "n3", "weight": 1.0, "edge_type": "liquidity_flow"},
    {"src": "n2", "dst": "n3", "weight": 1.0, "edge_type": "liquidity_flow"},
]
_PATH = [
    {"src": "n1", "dst": "n2", "weight": 1.0, "edge_type": "liquidity_flow"},
    {"src": "n2", "dst": "n3", "weight": 1.0, "edge_type": "liquidity_flow"},
]

_ORACLE_A = _graph([[0.2] * 5] * 3, _TRIANGLE)              # m = (1,1,1)
_ORACLE_B = _graph([[0.2] * 5, [0.2] * 5, [0.8] * 5], _TRIANGLE)  # m = (1,1,4)
_ORACLE_PATH = _graph([[0.2] * 5] * 3, _PATH)


def _AX(graph):
    return adjacency_tensor(graph), feature_tensor(graph)


# ---------------------------------------------------------------------------
# Oracle reproduction (core AC)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("graph", "expected"),
    [
        (_ORACLE_A, 0.789690),
        (_ORACLE_B, 0.741117),
        (_ORACLE_PATH, 0.630930),
    ],
)
def test_oracle_values_from_tensors(graph, expected):
    A, X = _AX(graph)
    assert fragility_raw(A, X) == pytest.approx(expected, abs=TOL)


def test_oracle_values_from_graph_helper():
    assert fragility_raw_from_graph(_ORACLE_A) == pytest.approx(0.789690, abs=TOL)
    assert fragility_raw_from_graph(_ORACLE_B) == pytest.approx(0.741117, abs=TOL)


# ---------------------------------------------------------------------------
# Range & discrimination
# ---------------------------------------------------------------------------

def test_score_in_unit_interval():
    for g in (_ORACLE_A, _ORACLE_B, _ORACLE_PATH):
        A, X = _AX(g)
        s = fragility_raw(A, X)
        assert 0.0 <= s <= 1.0


def test_triangle_more_fragile_than_path():
    a = fragility_raw(*_AX(_ORACLE_A))
    p = fragility_raw(*_AX(_ORACLE_PATH))
    assert a > p


# ---------------------------------------------------------------------------
# Determinism (AC: result deterministic)
# ---------------------------------------------------------------------------

def test_deterministic_repeat():
    A, X = _AX(_ORACLE_B)
    first = fragility_raw(A, X)
    for _ in range(5):
        assert fragility_raw(A, X) == first


# ---------------------------------------------------------------------------
# Degenerate guards
# ---------------------------------------------------------------------------

def test_single_node_returns_zero():
    A = torch.zeros((1, 1))
    X = torch.ones((1, 5))
    assert fragility_raw(A, X) == 0.0


def test_no_edges_returns_zero():
    A = torch.zeros((3, 3))
    X = torch.ones((3, 5))
    assert fragility_raw(A, X) == 0.0


def test_zero_mass_returns_zero():
    A, _ = _AX(_ORACLE_A)
    X = torch.zeros((3, 5))
    assert fragility_raw(A, X) == 0.0


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_row_count_mismatch_raises():
    A = torch.zeros((3, 3))
    X = torch.ones((2, 5))
    with pytest.raises(ValueError):
        fragility_raw(A, X)


def test_non_square_adjacency_raises():
    A = torch.zeros((3, 4))
    X = torch.ones((3, 5))
    with pytest.raises(ValueError):
        fragility_raw(A, X)


def test_negative_mass_raises():
    A, _ = _AX(_ORACLE_A)
    X = torch.full((3, 5), -1.0)
    with pytest.raises(ValueError):
        fragility_raw(A, X)


# ---------------------------------------------------------------------------
# AC-sized input (50x50) — finite, in range
# ---------------------------------------------------------------------------

def test_50x50_forward_finite():
    torch.manual_seed(0)
    n = 50
    m = torch.rand(n, n)
    A = (m + m.t()) / 2  # symmetric non-negative
    A.fill_diagonal_(0.0)
    X = torch.rand(n, 5)
    s = fragility_raw(A, X)
    assert math.isfinite(s)
    assert 0.0 <= s <= 1.0


# ---------------------------------------------------------------------------
# Feature weights hook
# ---------------------------------------------------------------------------

def test_uniform_weights_default_matches_explicit():
    A, X = _AX(_ORACLE_B)
    default = fragility_raw(A, X)
    explicit = fragility_raw(A, X, feature_weights=torch.ones(5))
    assert default == pytest.approx(explicit, abs=1e-9)
