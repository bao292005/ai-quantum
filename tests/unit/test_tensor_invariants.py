"""Tensor invariant tests (Story 2C.1).

Verifies symmetry, non-negativity, and mass conservation on 20+ sample graphs
across BOTH the dense (2B.1) and sparse (2B.4) adjacency variants, plus finiteness
of the node feature tensor (2B.2).
"""

from __future__ import annotations

import random

import pytest
import torch

from engine.graph.builder import ZERO_ADDRESS, build_graph
from engine.tensor.adjacency import adjacency_tensor
from engine.tensor.features import feature_tensor
from engine.tensor.sparse import sparse_adjacency_tensor

_TX = "0x" + "e" * 64
_TS = "2023-10-24T12:00:00Z"


# ---------------------------------------------------------------------------
# Sample-graph generation (AC1)
# ---------------------------------------------------------------------------

def _addr(n: int, width: int = 40) -> str:
    return "0x" + f"{n:0{width}x}"


def _build_graph_from_seed(seed: int) -> dict:
    """A build_graph() output with a seed-varied set of synthetic events."""
    rng = random.Random(seed)
    n_pools = rng.randint(1, 5)
    n_tokens = rng.randint(2, 8)
    n_events = rng.randint(1, 40)
    pools = [_addr(1000 + i) for i in range(n_pools)]
    tokens = [_addr(2000 + i) for i in range(n_tokens)]
    events = []
    for k in range(n_events):
        pool = rng.choice(pools)
        aave = rng.random() < 0.3
        protocol = "aave_v3" if aave else "uniswap_v3"
        t0 = rng.choice(tokens)
        t1 = rng.choice(tokens)
        events.append({
            "block_number": 1 + k,
            "block_timestamp": _TS,
            "protocol": protocol,
            "event_type": "borrow" if aave else "swap",
            "pool_address": pool,
            "token0": t0,
            "token1": ZERO_ADDRESS if aave else t1,
            "amount0": str(rng.randint(1, 100000)),
            "amount1": "0" if aave else str(rng.randint(0, 100000)),
            "tx_hash": _TX,
            "log_index": k,
        })
    return build_graph(events)


def _manual(nodes: list[str], edges: list[tuple[str, str, float]]) -> dict:
    def node(i):
        return {"id": i, "type": "token", "features": {
            "tvl_usd": 1.0, "volume_24h_usd": 1.0, "price_usd": 1.0,
            "volatility": 0.0, "connectivity": 0.5}}
    return {
        "snapshot_id": "550e8400-e29b-41d4-a716-446655440000",
        "block_range": {"start": 1, "end": 2},
        "created_at": _TS,
        "nodes": [node(i) for i in nodes],
        "edges": [{"src": s, "dst": d, "weight": w, "edge_type": "liquidity_flow"}
                  for s, d, w in edges],
    }


def _sample_graphs() -> list[dict]:
    graphs = [_build_graph_from_seed(s) for s in range(17)]
    # Manual edge cases to exercise the mass rule fully:
    graphs.append(_manual(["a"], []))                                  # single node, 0 edge
    graphs.append(_manual(["a", "b", "c"], [("a", "a", 0.4)]))         # self-loop
    graphs.append(_manual(["a", "b"], [("a", "b", 0.3), ("a", "b", 0.5)]))  # parallel
    graphs.append(_manual(["a", "b", "c"],
                          [("a", "b", 0.2), ("b", "c", 0.7), ("a", "a", 0.1)]))  # mixed
    return graphs


SAMPLE_GRAPHS = _sample_graphs()


def _expected_mass(graph: dict) -> float:
    total = 0.0
    for e in graph["edges"]:
        w = float(e["weight"])
        total += w if e["src"] == e["dst"] else 2.0 * w
    return total


def test_have_at_least_20_samples() -> None:
    assert len(SAMPLE_GRAPHS) >= 20


# ---------------------------------------------------------------------------
# AC2 — symmetry (dense + sparse)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("g", SAMPLE_GRAPHS)
def test_symmetry_dense(g: dict) -> None:
    a = adjacency_tensor(g)
    assert torch.allclose(a, a.T, atol=1e-6)


@pytest.mark.parametrize("g", SAMPLE_GRAPHS)
def test_sparse_matches_dense_and_symmetric(g: dict) -> None:
    dense = adjacency_tensor(g)
    sparse = sparse_adjacency_tensor(g).to_dense()
    assert torch.allclose(dense, sparse, atol=1e-6)
    assert torch.allclose(sparse, sparse.T, atol=1e-6)


# ---------------------------------------------------------------------------
# AC3 — non-negative (dense + sparse) + feature finite
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("g", SAMPLE_GRAPHS)
def test_non_negative(g: dict) -> None:
    dense = adjacency_tensor(g)
    assert torch.all(dense >= 0)
    sparse_vals = sparse_adjacency_tensor(g).values()
    if sparse_vals.numel() > 0:
        assert torch.all(sparse_vals >= 0)


@pytest.mark.parametrize("g", SAMPLE_GRAPHS)
def test_feature_tensor_finite(g: dict) -> None:
    ft = feature_tensor(g)
    assert ft.shape == (len(g["nodes"]), 5)
    assert torch.isfinite(ft).all()


# ---------------------------------------------------------------------------
# AC4/AC5 — mass conservation (dense + sparse)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("g", SAMPLE_GRAPHS)
def test_mass_conservation(g: dict) -> None:
    expected = _expected_mass(g)
    dense_mass = adjacency_tensor(g).sum().item()
    sparse_mass = sparse_adjacency_tensor(g).to_dense().sum().item()
    assert dense_mass == pytest.approx(expected, abs=1e-4)
    assert sparse_mass == pytest.approx(expected, abs=1e-4)
