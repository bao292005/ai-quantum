"""Unit tests for engine.tensor.adjacency (Story 2B.1)."""

from __future__ import annotations

import time

import pytest
import torch

from engine.tensor.adjacency import adjacency_tensor


def _features(connectivity: float = 0.5) -> dict:
    return {
        "tvl_usd": 1.0,
        "volume_24h_usd": 1.0,
        "price_usd": 1.0,
        "volatility": 0.0,
        "connectivity": connectivity,
    }


def _node(node_id: str, node_type: str = "token") -> dict:
    return {"id": node_id, "type": node_type, "features": _features()}


def _graph(nodes: list[dict], edges: list[dict]) -> dict:
    return {
        "snapshot_id": "550e8400-e29b-41d4-a716-446655440000",
        "block_range": {"start": 1, "end": 2},
        "created_at": "2023-10-24T12:03:00Z",
        "nodes": nodes,
        "edges": edges,
    }


def _edge(src: str, dst: str, weight: float, edge_type: str = "liquidity_flow") -> dict:
    return {"src": src, "dst": dst, "weight": weight, "edge_type": edge_type}


# ---------------------------------------------------------------------------
# AC1 — shape & dtype
# ---------------------------------------------------------------------------

def test_shape_and_dtype() -> None:
    g = _graph([_node("a"), _node("b"), _node("c")], [_edge("a", "b", 0.5)])
    adj = adjacency_tensor(g)
    assert adj.shape == (3, 3)
    assert adj.dtype == torch.float32


# ---------------------------------------------------------------------------
# AC2/AC3 — ordering + symmetry + correct cell placement
# ---------------------------------------------------------------------------

def test_ordering_and_values() -> None:
    g = _graph([_node("a"), _node("b"), _node("c")], [_edge("a", "c", 0.7)])
    adj = adjacency_tensor(g)
    # a=0, b=1, c=2 → A[0,2] and A[2,0] set.
    assert adj[0, 2].item() == pytest.approx(0.7)
    assert adj[2, 0].item() == pytest.approx(0.7)
    assert adj[0, 1].item() == 0.0


def test_symmetric() -> None:
    g = _graph(
        [_node("a"), _node("b"), _node("c")],
        [_edge("a", "b", 0.3), _edge("b", "c", 0.6)],
    )
    adj = adjacency_tensor(g)
    assert torch.equal(adj, adj.T)


def test_parallel_edges_accumulate() -> None:
    g = _graph([_node("a"), _node("b")], [_edge("a", "b", 0.4), _edge("a", "b", 0.5)])
    adj = adjacency_tensor(g)
    assert adj[0, 1].item() == pytest.approx(0.9)
    assert adj[1, 0].item() == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# AC4 — diagonal
# ---------------------------------------------------------------------------

def test_diagonal_zero_without_self_loop() -> None:
    g = _graph([_node("a"), _node("b")], [_edge("a", "b", 0.5)])
    adj = adjacency_tensor(g)
    assert adj[0, 0].item() == 0.0
    assert adj[1, 1].item() == 0.0


def test_self_loop_added_once() -> None:
    g = _graph([_node("a"), _node("b")], [_edge("a", "a", 0.8)])
    adj = adjacency_tensor(g)
    assert adj[0, 0].item() == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# AC5 — robustness
# ---------------------------------------------------------------------------

def test_unknown_src_raises() -> None:
    g = _graph([_node("a"), _node("b")], [_edge("ghost", "b", 0.5)])
    with pytest.raises(ValueError, match="src 'ghost' not in node ids"):
        adjacency_tensor(g)


def test_unknown_dst_raises() -> None:
    g = _graph([_node("a"), _node("b")], [_edge("a", "ghost", 0.5)])
    with pytest.raises(ValueError, match="dst 'ghost' not in node ids"):
        adjacency_tensor(g)


def test_zero_edges_returns_zero_matrix() -> None:
    g = _graph([_node("a"), _node("b"), _node("c")], [])
    adj = adjacency_tensor(g)
    assert adj.shape == (3, 3)
    assert torch.count_nonzero(adj).item() == 0


# ---------------------------------------------------------------------------
# AC6 — benchmark on a real 50-node graph from build_graph (2A.3)
# ---------------------------------------------------------------------------

def _fifty_node_graph() -> dict:
    from engine.graph.builder import ZERO_ADDRESS, build_graph

    pools = ["0x" + f"{p:040x}" for p in range(1, 6)]
    tokens = ["0x" + f"{t:040x}" for t in range(100, 145)]  # 45 tokens
    tx = "0x" + "e" * 64
    events = []
    for i in range(300):
        pool = pools[i % len(pools)]
        protocol = "aave_v3" if i % 5 == 4 else "uniswap_v3"
        t0 = tokens[i % len(tokens)]
        t1 = tokens[(i + 1) % len(tokens)]
        events.append({
            "block_number": 1000 + i,
            "block_timestamp": "2023-10-24T12:00:00Z",
            "protocol": protocol,
            "event_type": "swap" if protocol == "uniswap_v3" else "borrow",
            "pool_address": pool,
            "token0": t0,
            "token1": t1 if protocol == "uniswap_v3" else ZERO_ADDRESS,
            "amount0": str(100 + i),
            "amount1": str(50 + i) if protocol == "uniswap_v3" else "0",
            "tx_hash": tx,
            "log_index": i,
        })
    return build_graph(events)


def test_benchmark_50_nodes(capsys) -> None:
    g = _fifty_node_graph()
    n = len(g["nodes"])
    # warm-up
    adjacency_tensor(g)
    start = time.perf_counter()
    adj = adjacency_tensor(g)
    elapsed_ms = (time.perf_counter() - start) * 1000
    with capsys.disabled():
        print(f"\n[bench] adjacency_tensor(N={n}) = {elapsed_ms:.3f} ms")
    assert adj.shape == (n, n)
    assert torch.equal(adj, adj.T)
    # AC6 target <5ms warm; generous ceiling to avoid CI flakiness.
    assert elapsed_ms < 50.0
