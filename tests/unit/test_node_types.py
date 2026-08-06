"""Unit tests for engine.graph.node_types (Story 2A.1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.schemas import validate_graph_snapshot
from engine.graph.node_types import Node, NodeFeatures

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_FEATURES = {
    "tvl_usd": 320000000.0,
    "volume_24h_usd": 180000000.0,
    "price_usd": 1815.42,
    "volatility": 0.11,
    "connectivity": 0.6,
}


def _node(node_id: str, node_type: str) -> Node:
    return Node(id=node_id, type=node_type, features=NodeFeatures(**_VALID_FEATURES))


# ---------------------------------------------------------------------------
# Positive — one node per type (AC5)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("node_id", "node_type"),
    [
        ("protocol:uniswap_v3", "protocol"),
        ("pool:uniswap_v3:0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640", "pool"),
        ("token:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "token"),
    ],
)
def test_valid_node_each_type(node_id: str, node_type: str) -> None:
    node = _node(node_id, node_type)
    assert node.type == node_type
    assert node.features.connectivity == 0.6


def test_boundary_connectivity_zero_and_one() -> None:
    for c in (0.0, 1.0):
        feats = {**_VALID_FEATURES, "connectivity": c}
        Node(id="token:x", type="token", features=NodeFeatures(**feats))


# ---------------------------------------------------------------------------
# Negative (AC5) — at least 3
# ---------------------------------------------------------------------------

def test_invalid_type_rejected() -> None:
    with pytest.raises(ValidationError):
        Node(id="n1", type="wallet", features=NodeFeatures(**_VALID_FEATURES))


def test_missing_feature_rejected() -> None:
    incomplete = {k: v for k, v in _VALID_FEATURES.items() if k != "price_usd"}
    with pytest.raises(ValidationError):
        NodeFeatures(**incomplete)


def test_connectivity_above_one_rejected() -> None:
    feats = {**_VALID_FEATURES, "connectivity": 1.5}
    with pytest.raises(ValidationError):
        NodeFeatures(**feats)


def test_negative_tvl_rejected() -> None:
    feats = {**_VALID_FEATURES, "tvl_usd": -1.0}
    with pytest.raises(ValidationError):
        NodeFeatures(**feats)


def test_extra_feature_field_rejected() -> None:
    feats = {**_VALID_FEATURES, "borrow_rate": 0.05}
    with pytest.raises(ValidationError):
        NodeFeatures(**feats)


@pytest.mark.parametrize(
    "field",
    ["tvl_usd", "volume_24h_usd", "price_usd", "volatility", "connectivity"],
)
def test_inf_and_nan_rejected(field: str) -> None:
    # P1 (Story 2A.1 code review): inf/nan must not survive validation — JSON has
    # no Infinity literal and either poisons downstream tensor math.
    for bad in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises(ValidationError):
            NodeFeatures(**{**_VALID_FEATURES, field: bad})


def test_empty_id_rejected() -> None:
    with pytest.raises(ValidationError):
        Node(id="", type="pool", features=NodeFeatures(**_VALID_FEATURES))


# ---------------------------------------------------------------------------
# Round-trip against graph_snapshot.schema.json (AC4)
# ---------------------------------------------------------------------------

def test_model_dump_roundtrips_through_schema() -> None:
    node = _node("token:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "token")
    snapshot = {
        "snapshot_id": "550e8400-e29b-41d4-a716-446655440000",
        "block_range": {"start": 18500000, "end": 18500009},
        "created_at": "2023-10-24T12:03:00Z",
        "nodes": [node.model_dump()],
        "edges": [],
    }
    # Raises jsonschema.ValidationError / ValueError if the dump diverges.
    validate_graph_snapshot(snapshot)
