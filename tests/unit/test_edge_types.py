"""Unit tests for engine.graph.edge_types (Story 2A.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.schemas import validate_graph_snapshot
from engine.graph.edge_types import Edge
from engine.graph.node_types import Node, NodeFeatures

_FEATURES = {
    "tvl_usd": 1.0,
    "volume_24h_usd": 1.0,
    "price_usd": 1.0,
    "volatility": 0.0,
    "connectivity": 0.5,
}


# ---------------------------------------------------------------------------
# Positive — one edge per type (AC5)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "edge_type",
    ["liquidity_flow", "borrow_position", "shared_collateral"],
)
def test_valid_edge_each_type(edge_type: str) -> None:
    edge = Edge(src="a", dst="b", weight=0.5, edge_type=edge_type)
    assert edge.edge_type == edge_type
    assert edge.metadata is None


def test_boundary_weight_zero_and_one() -> None:
    for w in (0.0, 1.0):
        Edge(src="a", dst="b", weight=w, edge_type="liquidity_flow")


def test_metadata_at_limit_ok() -> None:
    meta = {f"k{i}": i for i in range(32)}
    edge = Edge(src="a", dst="b", weight=0.1, edge_type="liquidity_flow", metadata=meta)
    assert len(edge.metadata) == 32


# ---------------------------------------------------------------------------
# Negative (AC3, AC5) — at least 4
# ---------------------------------------------------------------------------

def test_invalid_edge_type_rejected() -> None:
    with pytest.raises(ValidationError):
        Edge(src="a", dst="b", weight=0.5, edge_type="LiquidityFlow")


def test_weight_below_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        Edge(src="a", dst="b", weight=-0.1, edge_type="liquidity_flow")


def test_weight_above_one_rejected() -> None:
    with pytest.raises(ValidationError):
        Edge(src="a", dst="b", weight=1.1, edge_type="liquidity_flow")


def test_metadata_over_32_keys_rejected() -> None:
    meta = {f"k{i}": i for i in range(33)}
    with pytest.raises(ValidationError):
        Edge(src="a", dst="b", weight=0.5, edge_type="liquidity_flow", metadata=meta)


def test_empty_src_rejected() -> None:
    with pytest.raises(ValidationError):
        Edge(src="", dst="b", weight=0.5, edge_type="liquidity_flow")


def test_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        Edge(src="a", dst="b", weight=0.5, edge_type="liquidity_flow", foo=1)


# ---------------------------------------------------------------------------
# Round-trip against graph_snapshot.schema.json (AC4)
# ---------------------------------------------------------------------------

def test_edge_roundtrips_through_schema() -> None:
    n1 = Node(id="pool:x", type="pool", features=NodeFeatures(**_FEATURES))
    n2 = Node(id="token:y", type="token", features=NodeFeatures(**_FEATURES))
    edge = Edge(
        src="pool:x",
        dst="token:y",
        weight=0.42,
        edge_type="borrow_position",
        metadata={"position_health": 1.3},
    )
    snapshot = {
        "snapshot_id": "550e8400-e29b-41d4-a716-446655440000",
        "block_range": {"start": 1, "end": 2},
        "created_at": "2023-10-24T12:03:00Z",
        "nodes": [n1.model_dump(), n2.model_dump()],
        "edges": [edge.model_dump(exclude_none=True)],
    }
    validate_graph_snapshot(snapshot)


def test_edge_roundtrips_without_metadata() -> None:
    n1 = Node(id="pool:x", type="pool", features=NodeFeatures(**_FEATURES))
    n2 = Node(id="token:y", type="token", features=NodeFeatures(**_FEATURES))
    edge = Edge(src="pool:x", dst="token:y", weight=0.5, edge_type="liquidity_flow")
    snapshot = {
        "snapshot_id": "550e8400-e29b-41d4-a716-446655440000",
        "block_range": {"start": 1, "end": 2},
        "created_at": "2023-10-24T12:03:00Z",
        "nodes": [n1.model_dump(), n2.model_dump()],
        "edges": [edge.model_dump(exclude_none=True)],
    }
    # exclude_none drops metadata → schema does not require it.
    assert "metadata" not in snapshot["edges"][0]
    validate_graph_snapshot(snapshot)
