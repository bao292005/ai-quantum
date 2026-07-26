"""Graph builder — tick-data events → GraphSnapshot (Story 2A.3).

`build_graph(events)` converts a list of normalized tick-data event dicts
(schema 0.1) into a `GraphSnapshot` dict (schema 0.2), applying:

- Node/edge typology from Story 2R.2 (`research/graph_topology.md`).
- Node feature policy from Story 2R.1 (`research/feature_catalog.md`).
- Edge weight formula from Story 2A.4 (`research/edge_weight_formula.md`):
  ``raw = volume · exp(-λ·Δt) · corr``, normalized snapshot-relative to [0, 1].

NetworkX is used as an intermediate structure to compute node degree for the
`connectivity` feature; the returned object is a plain dict (not an ``nx.Graph``).

v1 feature limitation (per 2R.1): ``tvl_usd``, ``price_usd`` and ``volatility``
require auxiliary reserve/price-series data not present in the event stream, so
they are emitted as ``0.0`` proxies here. ``volume_24h_usd`` uses token-native
volume (USD price anchoring deferred). ``connectivity`` is computed exactly.
"""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import networkx as nx

from core.schemas import validate_graph_snapshot
from engine.graph.edge_types import Edge
from engine.graph.node_types import Node, NodeFeatures

ZERO_ADDRESS = "0x" + "0" * 40

# Edge weight formula constants (Story 2A.4)
HALF_LIFE_S = 3600.0
LAMBDA = math.log(2) / HALF_LIFE_S
CORR: dict[str, float] = {
    "liquidity_flow": 1.0,
    "borrow_position": 0.7,
    "shared_collateral": 0.5,
}

_DEX_PROTOCOLS = {"uniswap_v3"}


def _protocol_id(protocol: str) -> str:
    return f"protocol:{protocol}"


def _pool_id(protocol: str, address: str) -> str:
    return f"pool:{protocol}:{address}"


def _token_id(address: str) -> str:
    return f"token:{address}"


def _parse_ts(ts: str) -> datetime:
    # datetime.fromisoformat handles the trailing 'Z' offset only on 3.11+;
    # normalize explicitly for safety.
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _abs_amount(amount: str | float | int) -> float:
    return abs(float(amount))


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def build_graph(
    events: list[dict[str, Any]], *, snapshot_id: str | None = None
) -> dict[str, Any]:
    """Build a schema-0.2 GraphSnapshot dict from tick-data events.

    Raises:
        ValueError: if ``events`` is empty (schema requires ``nodes minItems:1``).
    """
    if not events:
        raise ValueError(
            "build_graph requires at least one event (schema requires nodes minItems:1)"
        )

    ts_by_event = [_parse_ts(e["block_timestamp"]) for e in events]
    t_latest = max(ts_by_event)
    blocks = [int(e["block_number"]) for e in events]

    pool_protocol: dict[str, str] = {}
    pool_token_vol: dict[tuple[str, str], float] = defaultdict(float)
    pool_token_ts: dict[tuple[str, str], datetime] = {}
    token_pools: dict[str, set[str]] = defaultdict(set)

    for event, ts in zip(events, ts_by_event):
        protocol = event["protocol"]
        pool = event["pool_address"]
        pool_protocol[pool] = protocol
        for token, amount in (
            (event["token0"], event.get("amount0", "0")),
            (event["token1"], event.get("amount1", "0")),
        ):
            if token == ZERO_ADDRESS:
                continue
            key = (pool, token)
            pool_token_vol[key] += _abs_amount(amount)
            pool_token_ts[key] = max(pool_token_ts.get(key, ts), ts)
            token_pools[token].add(pool)

    # ---- Assemble raw edges: (src, dst, edge_type, volume, latest_ts) --------
    raw_edges: list[tuple[str, str, str, float, datetime]] = []

    # pool -> token (liquidity_flow for DEX, borrow_position for lending)
    for (pool, token), vol in pool_token_vol.items():
        protocol = pool_protocol[pool]
        etype = "liquidity_flow" if protocol in _DEX_PROTOCOLS else "borrow_position"
        raw_edges.append(
            (_pool_id(protocol, pool), _token_id(token), etype, vol, pool_token_ts[(pool, token)])
        )

    # protocol -> pool (liquidity_flow); volume = sum of the pool's token volume
    for pool, protocol in pool_protocol.items():
        pool_vol = sum(v for (p, _), v in pool_token_vol.items() if p == pool)
        pool_ts = max(
            (t for (p, _), t in pool_token_ts.items() if p == pool), default=t_latest
        )
        raw_edges.append(
            (_protocol_id(protocol), _pool_id(protocol, pool), "liquidity_flow", pool_vol, pool_ts)
        )

    # shared_collateral: pools sharing a token (contagion channel)
    for token, pools in token_pools.items():
        if len(pools) < 2:
            continue
        ordered = sorted(pools)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                pa, pb = ordered[i], ordered[j]
                va = pool_token_vol[(pa, token)]
                vb = pool_token_vol[(pb, token)]
                exposure = min(va, vb)
                latest = max(pool_token_ts[(pa, token)], pool_token_ts[(pb, token)])
                raw_edges.append(
                    (
                        _pool_id(pool_protocol[pa], pa),
                        _pool_id(pool_protocol[pb], pb),
                        "shared_collateral",
                        exposure,
                        latest,
                    )
                )

    # ---- Weight normalization (Story 2A.4) ----------------------------------
    scored: list[tuple[str, str, str, float]] = []
    max_raw = 0.0
    for src, dst, etype, vol, ts in raw_edges:
        dt = (t_latest - ts).total_seconds()
        raw = vol * math.exp(-LAMBDA * dt) * CORR[etype]
        scored.append((src, dst, etype, raw))
        max_raw = max(max_raw, raw)

    # ---- Build node set + connectivity via NetworkX -------------------------
    node_types: dict[str, str] = {}
    for pool, protocol in pool_protocol.items():
        node_types[_protocol_id(protocol)] = "protocol"
        node_types[_pool_id(protocol, pool)] = "pool"
    for token in token_pools:
        node_types[_token_id(token)] = "token"

    g = nx.Graph()
    g.add_nodes_from(node_types)
    for src, dst, _etype, _raw in scored:
        g.add_edge(src, dst)

    n = g.number_of_nodes()
    denom = (n - 1) if n > 1 else 1

    # node volume (proxy) for volume_24h_usd
    node_volume: dict[str, float] = defaultdict(float)
    for (pool, token), vol in pool_token_vol.items():
        protocol = pool_protocol[pool]
        node_volume[_token_id(token)] += vol
        node_volume[_pool_id(protocol, pool)] += vol
        node_volume[_protocol_id(protocol)] += vol

    nodes: list[dict[str, Any]] = []
    for node_id, node_type in node_types.items():
        connectivity = _clamp01(g.degree(node_id) / denom)
        features = NodeFeatures(
            tvl_usd=0.0,
            volume_24h_usd=node_volume.get(node_id, 0.0),
            price_usd=0.0,
            volatility=0.0,
            connectivity=connectivity,
        )
        nodes.append(
            Node(id=node_id, type=node_type, features=features).model_dump()
        )

    edges: list[dict[str, Any]] = []
    for src, dst, etype, raw in scored:
        weight = (raw / max_raw) if max_raw > 0 else 0.0
        edges.append(
            Edge(src=src, dst=dst, weight=weight, edge_type=etype).model_dump(
                exclude_none=True
            )
        )

    snapshot: dict[str, Any] = {
        "snapshot_id": snapshot_id or str(uuid.uuid4()),
        "block_range": {"start": min(blocks), "end": max(blocks)},
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nodes": nodes,
        "edges": edges,
    }
    validate_graph_snapshot(snapshot)
    return snapshot


__all__ = ["build_graph", "HALF_LIFE_S", "LAMBDA", "CORR", "ZERO_ADDRESS"]
