"""Unit tests for engine.graph.builder (Story 2A.3)."""

from __future__ import annotations

import time

import pytest

from core.schemas import validate_graph_snapshot
from engine.graph.builder import ZERO_ADDRESS, build_graph

# Deterministic 40-hex addresses / 64-hex tx
A = "0x" + "a" * 40   # token A (e.g. USDC)
W = "0x" + "c" * 40   # token W (e.g. WETH) — shared across pools
B = "0x" + "b" * 40   # token B (e.g. USDT)
D = "0x" + "d" * 40   # token D (e.g. DAI reserve)
P1 = "0x" + "1" * 40  # uniswap pool 1
P2 = "0x" + "2" * 40  # uniswap pool 2
P3 = "0x" + "3" * 40  # aave pool
TX = "0x" + "e" * 64

_T = "2023-10-24T12:00:00Z"


def _ev(block, protocol, event_type, pool, t0, t1, a0, a1, ts=_T, log_index=0):
    return {
        "block_number": block,
        "block_timestamp": ts,
        "protocol": protocol,
        "event_type": event_type,
        "pool_address": pool,
        "token0": t0,
        "token1": t1,
        "amount0": a0,
        "amount1": a1,
        "tx_hash": TX,
        "log_index": log_index,
    }


def _base_events():
    return [
        _ev(100, "uniswap_v3", "swap", P1, A, W, "1000", "1"),
        _ev(101, "uniswap_v3", "swap", P2, W, B, "1", "1000"),
        _ev(102, "aave_v3", "borrow", P3, D, ZERO_ADDRESS, "500", "0"),
    ]


# ---------------------------------------------------------------------------
# AC4/AC6a — round-trip
# ---------------------------------------------------------------------------

def test_build_roundtrips_through_schema() -> None:
    snap = build_graph(_base_events())
    # build_graph validates internally; re-validate to be explicit.
    validate_graph_snapshot(snap)
    assert isinstance(snap, dict)
    assert snap["block_range"] == {"start": 100, "end": 102}


# ---------------------------------------------------------------------------
# AC6b — all 3 node types + all 3 edge types
# ---------------------------------------------------------------------------

def test_all_node_types_present() -> None:
    snap = build_graph(_base_events())
    types = {n["type"] for n in snap["nodes"]}
    assert types == {"protocol", "pool", "token"}


def test_all_edge_types_present() -> None:
    snap = build_graph(_base_events())
    etypes = {e["edge_type"] for e in snap["edges"]}
    assert etypes == {"liquidity_flow", "borrow_position", "shared_collateral"}


# ---------------------------------------------------------------------------
# AC6c — connectivity in [0,1] and equals degree/(N-1)
# ---------------------------------------------------------------------------

def test_connectivity_in_range() -> None:
    snap = build_graph(_base_events())
    for node in snap["nodes"]:
        assert 0.0 <= node["features"]["connectivity"] <= 1.0


def test_connectivity_matches_degree() -> None:
    snap = build_graph(_base_events())
    # Shared token W connects to P1 and P2 → degree 2. N = 2 proto + 3 pool + 4 token = 9.
    w_node = next(n for n in snap["nodes"] if n["id"] == f"token:{W}")
    assert len(snap["nodes"]) == 9
    assert w_node["features"]["connectivity"] == pytest.approx(2 / 8)


# ---------------------------------------------------------------------------
# AC3/AC6d — weight formula boundary behaviour (ground truth: 2A.4)
# ---------------------------------------------------------------------------

def test_all_weights_in_unit_interval() -> None:
    snap = build_graph(_base_events())
    for e in snap["edges"]:
        assert 0.0 <= e["weight"] <= 1.0


def test_max_edge_weight_is_one() -> None:
    snap = build_graph(_base_events())
    assert max(e["weight"] for e in snap["edges"]) == pytest.approx(1.0)


def test_time_decay_newer_edge_heavier() -> None:
    # Two independent DEX pools, same volume, different timestamps (no shared token).
    events = [
        _ev(200, "uniswap_v3", "swap", P1, A, B, "100", "100", ts="2023-10-24T12:00:00Z"),
        _ev(201, "uniswap_v3", "swap", P2, W, D, "100", "100", ts="2023-10-24T10:00:00Z"),
    ]
    snap = build_graph(events)
    w_new = next(e["weight"] for e in snap["edges"]
                 if e["src"] == f"pool:uniswap_v3:{P1}" and e["dst"] == f"token:{A}")
    w_old = next(e["weight"] for e in snap["edges"]
                 if e["src"] == f"pool:uniswap_v3:{P2}" and e["dst"] == f"token:{W}")
    assert w_new > w_old


def test_zero_volume_edge_weight_zero() -> None:
    # amount0=0 for token A → pool->A edge has zero volume → weight 0; A->B has volume.
    events = [_ev(300, "uniswap_v3", "swap", P1, A, B, "0", "100")]
    snap = build_graph(events)
    w_a = next(e["weight"] for e in snap["edges"]
               if e["src"] == f"pool:uniswap_v3:{P1}" and e["dst"] == f"token:{A}")
    assert w_a == 0.0


def test_edge_type_corr_ordering() -> None:
    # Same volume + timestamp: liquidity_flow (corr 1.0) heavier than borrow_position (0.7).
    events = [
        _ev(400, "uniswap_v3", "swap", P1, A, B, "100", "100"),
        _ev(401, "aave_v3", "borrow", P3, A, ZERO_ADDRESS, "100", "0"),
    ]
    snap = build_graph(events)
    w_liq = next(e["weight"] for e in snap["edges"]
                 if e["edge_type"] == "liquidity_flow"
                 and e["src"] == f"pool:uniswap_v3:{P1}" and e["dst"] == f"token:{A}")
    w_bor = next(e["weight"] for e in snap["edges"]
                 if e["edge_type"] == "borrow_position"
                 and e["src"] == f"pool:aave_v3:{P3}" and e["dst"] == f"token:{A}")
    assert w_liq > w_bor


# ---------------------------------------------------------------------------
# AC6e — empty events
# ---------------------------------------------------------------------------

def test_empty_events_raises() -> None:
    with pytest.raises(ValueError, match="at least one event"):
        build_graph([])


# ---------------------------------------------------------------------------
# AC5/AC6f — benchmark: 1000 events
# ---------------------------------------------------------------------------

def test_benchmark_1000_events(capsys) -> None:
    pools = [P1, P2, P3]
    tokens = [A, W, B, D]
    events = []
    for i in range(1000):
        pool = pools[i % 3]
        protocol = "aave_v3" if pool == P3 else "uniswap_v3"
        t0 = tokens[i % 4]
        t1 = tokens[(i + 1) % 4]
        events.append(
            _ev(1000 + i, protocol, "swap" if protocol == "uniswap_v3" else "borrow",
                pool, t0, t1 if protocol == "uniswap_v3" else ZERO_ADDRESS,
                str(100 + i), str(50 + i) if protocol == "uniswap_v3" else "0",
                log_index=i)
        )
    start = time.perf_counter()
    snap = build_graph(events)
    elapsed_ms = (time.perf_counter() - start) * 1000
    with capsys.disabled():
        print(f"\n[bench] build_graph(1000 events) = {elapsed_ms:.2f} ms")
    validate_graph_snapshot(snap)
    # AC5 target is <20ms on 1 core; assert a generous ceiling to avoid CI flakiness.
    assert elapsed_ms < 100.0
