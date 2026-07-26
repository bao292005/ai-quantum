"""Unit tests for engine.tensor.features (Story 2B.2)."""

from __future__ import annotations

import pytest
import torch

from engine.tensor.adjacency import adjacency_tensor
from engine.tensor.features import FEATURE_ORDER, feature_tensor


def _features(**overrides) -> dict:
    base = {
        "tvl_usd": 1.0,
        "volume_24h_usd": 2.0,
        "price_usd": 3.0,
        "volatility": 4.0,
        "connectivity": 0.5,
    }
    base.update(overrides)
    return base


def _node(node_id: str, **feature_overrides) -> dict:
    return {"id": node_id, "type": "token", "features": _features(**feature_overrides)}


def _graph(nodes: list[dict], edges: list[dict] | None = None) -> dict:
    return {
        "snapshot_id": "550e8400-e29b-41d4-a716-446655440000",
        "block_range": {"start": 1, "end": 2},
        "created_at": "2023-10-24T12:03:00Z",
        "nodes": nodes,
        "edges": edges or [],
    }


# ---------------------------------------------------------------------------
# AC1 — shape & dtype
# ---------------------------------------------------------------------------

def test_shape_and_dtype() -> None:
    g = _graph([_node("a"), _node("b"), _node("c")])
    t = feature_tensor(g)
    assert t.shape == (3, 5)
    assert t.dtype == torch.float32


def test_single_node_shape() -> None:
    g = _graph([_node("a")])
    assert feature_tensor(g).shape == (1, 5)


# ---------------------------------------------------------------------------
# AC2 — column order matches FEATURE_ORDER
# ---------------------------------------------------------------------------

def test_feature_order_constant() -> None:
    assert FEATURE_ORDER == (
        "tvl_usd", "volume_24h_usd", "price_usd", "volatility", "connectivity",
    )


def test_column_values_in_order() -> None:
    g = _graph([_node("a", tvl_usd=10.0, volume_24h_usd=20.0, price_usd=30.0,
                       volatility=40.0, connectivity=0.9)])
    t = feature_tensor(g)
    assert t[0].tolist() == pytest.approx([10.0, 20.0, 30.0, 40.0, 0.9])


# ---------------------------------------------------------------------------
# AC3 — node ordering identical to adjacency_tensor
# ---------------------------------------------------------------------------

def test_row_ordering_matches_adjacency() -> None:
    nodes = [_node("a", tvl_usd=1.0), _node("b", tvl_usd=2.0), _node("c", tvl_usd=3.0)]
    g = _graph(nodes, edges=[{"src": "a", "dst": "b", "weight": 0.5,
                              "edge_type": "liquidity_flow"}])
    ft = feature_tensor(g)
    adj = adjacency_tensor(g)
    # both index nodes by appearance order: a=0,b=1,c=2
    assert ft.shape[0] == adj.shape[0] == 3
    assert ft[0, 0].item() == pytest.approx(1.0)  # node a tvl
    assert ft[2, 0].item() == pytest.approx(3.0)  # node c tvl


# ---------------------------------------------------------------------------
# AC4 — NaN / inf → 0 with warning
# ---------------------------------------------------------------------------

def test_nan_replaced_with_zero_and_warns() -> None:
    g = _graph([_node("a", volatility=float("nan"))])
    with pytest.warns(UserWarning, match="volatility"):
        t = feature_tensor(g)
    # volatility is column index 3
    assert t[0, 3].item() == 0.0


def test_inf_replaced_with_zero_and_warns() -> None:
    g = _graph([_node("a", tvl_usd=float("inf"))])
    with pytest.warns(UserWarning, match="tvl_usd"):
        t = feature_tensor(g)
    assert t[0, 0].item() == 0.0


# ---------------------------------------------------------------------------
# AC5 — robustness
# ---------------------------------------------------------------------------

def test_missing_feature_raises() -> None:
    node = {"id": "a", "type": "token", "features": {"tvl_usd": 1.0}}
    with pytest.raises(ValueError, match="missing required feature"):
        feature_tensor(_graph([node]))


def test_empty_nodes_raises() -> None:
    g = _graph([])
    with pytest.raises(ValueError, match="at least one node"):
        feature_tensor(g)


# ---------------------------------------------------------------------------
# AC6 — round-trip with build_graph (2A.3)
# ---------------------------------------------------------------------------

def test_roundtrip_with_build_graph() -> None:
    from engine.graph.builder import ZERO_ADDRESS, build_graph

    A = "0x" + "a" * 40
    W = "0x" + "c" * 40
    B = "0x" + "b" * 40
    D = "0x" + "d" * 40
    P1 = "0x" + "1" * 40
    P2 = "0x" + "2" * 40
    P3 = "0x" + "3" * 40
    tx = "0x" + "e" * 64

    def ev(block, proto, etype, pool, t0, t1, a0, a1):
        return {
            "block_number": block, "block_timestamp": "2023-10-24T12:00:00Z",
            "protocol": proto, "event_type": etype, "pool_address": pool,
            "token0": t0, "token1": t1, "amount0": a0, "amount1": a1,
            "tx_hash": tx, "log_index": 0,
        }

    g = build_graph([
        ev(1, "uniswap_v3", "swap", P1, A, W, "1000", "1"),
        ev(2, "uniswap_v3", "swap", P2, W, B, "1", "1000"),
        ev(3, "aave_v3", "borrow", P3, D, ZERO_ADDRESS, "500", "0"),
    ])
    ft = feature_tensor(g)
    adj = adjacency_tensor(g)
    n = len(g["nodes"])
    assert ft.shape == (n, 5)
    assert adj.shape == (n, n)
    # connectivity column (index 4) must be within [0,1] and finite
    conn = ft[:, 4]
    assert torch.all(conn >= 0) and torch.all(conn <= 1)
    assert torch.isfinite(ft).all()
