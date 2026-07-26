"""Unit tests for engine.tensor.sparse (Story 2B.4)."""

from __future__ import annotations

import random

import pytest
import torch

from engine.tensor.adjacency import adjacency_tensor
from engine.tensor.sparse import sparse_adjacency_tensor, tensor_storage_bytes


def _node(node_id: str) -> dict:
    return {
        "id": node_id,
        "type": "token",
        "features": {
            "tvl_usd": 1.0, "volume_24h_usd": 1.0, "price_usd": 1.0,
            "volatility": 0.0, "connectivity": 0.5,
        },
    }


def _graph(nodes: list[dict], edges: list[dict]) -> dict:
    return {
        "snapshot_id": "550e8400-e29b-41d4-a716-446655440000",
        "block_range": {"start": 1, "end": 2},
        "created_at": "2023-10-24T12:03:00Z",
        "nodes": nodes,
        "edges": edges,
    }


def _edge(src: str, dst: str, w: float) -> dict:
    return {"src": src, "dst": dst, "weight": w, "edge_type": "liquidity_flow"}


# ---------------------------------------------------------------------------
# AC1/AC2 — CSR layout, dtype, equivalence to dense
# ---------------------------------------------------------------------------

def test_csr_layout_and_dtype() -> None:
    g = _graph([_node("a"), _node("b"), _node("c")], [_edge("a", "b", 0.5)])
    s = sparse_adjacency_tensor(g)
    assert s.layout == torch.sparse_csr
    assert s.dtype == torch.float32
    assert s.shape == (3, 3)


def test_equivalence_to_dense_small() -> None:
    g = _graph(
        [_node("a"), _node("b"), _node("c")],
        [_edge("a", "b", 0.3), _edge("b", "c", 0.6), _edge("a", "b", 0.1)],
    )
    dense = adjacency_tensor(g)
    sparse = sparse_adjacency_tensor(g).to_dense()
    assert torch.allclose(dense, sparse, atol=1e-6)


def test_equivalence_with_build_graph() -> None:
    from engine.graph.builder import ZERO_ADDRESS, build_graph

    A, W, B = "0x" + "a" * 40, "0x" + "c" * 40, "0x" + "b" * 40
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
    dense = adjacency_tensor(g)
    sparse = sparse_adjacency_tensor(g).to_dense()
    assert torch.allclose(dense, sparse, atol=1e-6)


# ---------------------------------------------------------------------------
# AC5 — robustness
# ---------------------------------------------------------------------------

def test_unknown_src_raises() -> None:
    g = _graph([_node("a"), _node("b")], [_edge("ghost", "b", 0.5)])
    with pytest.raises(ValueError, match="src 'ghost' not in node ids"):
        sparse_adjacency_tensor(g)


def test_zero_edges_returns_zero_dense() -> None:
    g = _graph([_node("a"), _node("b"), _node("c")], [])
    s = sparse_adjacency_tensor(g)
    assert s.shape == (3, 3)
    assert torch.count_nonzero(s.to_dense()).item() == 0


# ---------------------------------------------------------------------------
# AC3 — RAM saving on a 500-node ~95% sparse graph
# ---------------------------------------------------------------------------

def _large_sparse_graph(n: int = 500, nnz_pairs: int = 6000, seed: int = 7) -> dict:
    rng = random.Random(seed)
    nodes = [_node(f"n{i}") for i in range(n)]
    seen: set[tuple[int, int]] = set()
    edges: list[dict] = []
    while len(edges) < nnz_pairs:
        i, j = rng.randrange(n), rng.randrange(n)
        if i == j:
            continue
        key = (min(i, j), max(i, j))
        if key in seen:
            continue
        seen.add(key)
        edges.append(_edge(f"n{i}", f"n{j}", rng.random()))
    return _graph(nodes, edges)


def test_ram_saving_at_95pct_sparsity(capsys) -> None:
    g = _large_sparse_graph()
    n = len(g["nodes"])
    sparse = sparse_adjacency_tensor(g)
    dense = adjacency_tensor(g)

    dense_bytes = tensor_storage_bytes(dense)
    sparse_bytes = tensor_storage_bytes(sparse)
    nnz = sparse.values().numel()
    sparsity = 1 - nnz / (n * n)
    saving = 1 - sparse_bytes / dense_bytes
    with capsys.disabled():
        print(f"\n[sparse] N={n} sparsity={sparsity:.3f} "
              f"dense={dense_bytes}B sparse={sparse_bytes}B saving={saving:.1%}")

    assert sparsity >= 0.90
    # AC3: sparse ≤ 20% of dense (≥80% RAM saving).
    assert sparse_bytes <= 0.20 * dense_bytes


# ---------------------------------------------------------------------------
# AC4 — contraction (spMV) matches dense
# ---------------------------------------------------------------------------

def test_contraction_matches_dense() -> None:
    g = _large_sparse_graph(n=200, nnz_pairs=1500)
    dense = adjacency_tensor(g)
    sparse = sparse_adjacency_tensor(g)
    x = torch.randn(len(g["nodes"]), dtype=torch.float32)
    dense_y = dense @ x
    sparse_y = sparse @ x
    assert torch.allclose(dense_y, sparse_y, atol=1e-6)
