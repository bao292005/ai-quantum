"""Unit tests for the graph-snapshot JSON Schema (Story 0.2)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from core.schemas import load_graph_schema, validate_graph_snapshot

EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "examples"
    / "graph_snapshot_example.json"
)


def _load_example() -> dict:
    with EXAMPLE_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Positive tests
# ---------------------------------------------------------------------------

def test_example_validates() -> None:
    snap = _load_example()
    validate_graph_snapshot(snap)


def test_load_graph_schema_returns_dict() -> None:
    schema = load_graph_schema()
    assert isinstance(schema, dict)
    assert schema["$id"] == "https://quantumradar.io/schemas/graph_snapshot.schema.json"
    assert "node" in schema["$defs"]
    assert "edge" in schema["$defs"]


def test_example_covers_all_node_types() -> None:
    snap = _load_example()
    types = {node["type"] for node in snap["nodes"]}
    assert types == {"protocol", "pool", "token"}


def test_example_covers_all_edge_types() -> None:
    snap = _load_example()
    edge_types = {edge["edge_type"] for edge in snap["edges"]}
    assert edge_types == {"liquidity_flow", "borrow_position", "shared_collateral"}


# ---------------------------------------------------------------------------
# Negative tests — required by AC6
# ---------------------------------------------------------------------------

def _valid_snap() -> dict:
    return copy.deepcopy(_load_example())


def test_missing_snapshot_id() -> None:
    snap = _valid_snap()
    del snap["snapshot_id"]
    with pytest.raises(ValidationError):
        validate_graph_snapshot(snap)


def test_weight_out_of_range() -> None:
    snap = _valid_snap()
    snap["edges"][0]["weight"] = 1.5
    with pytest.raises(ValidationError):
        validate_graph_snapshot(snap)


def test_unknown_edge_type() -> None:
    snap = _valid_snap()
    snap["edges"][0]["edge_type"] = "unknown"
    with pytest.raises(ValidationError):
        validate_graph_snapshot(snap)


def test_connectivity_above_one() -> None:
    snap = _valid_snap()
    snap["nodes"][0]["features"]["connectivity"] = 2.0
    with pytest.raises(ValidationError):
        validate_graph_snapshot(snap)


# ---------------------------------------------------------------------------
# Runtime invariant tests (AC7)
# ---------------------------------------------------------------------------

def test_dangling_edge_src_raises() -> None:
    snap = _valid_snap()
    snap["edges"][0]["src"] = "node:ghost"
    with pytest.raises(ValueError, match="not in node ids"):
        validate_graph_snapshot(snap)


def test_dangling_edge_dst_raises() -> None:
    snap = _valid_snap()
    snap["edges"][0]["dst"] = "node:ghost"
    with pytest.raises(ValueError, match="not in node ids"):
        validate_graph_snapshot(snap)


def test_self_loop_raises() -> None:
    snap = _valid_snap()
    node_id = snap["nodes"][0]["id"]
    snap["edges"][0]["src"] = node_id
    snap["edges"][0]["dst"] = node_id
    with pytest.raises(ValueError, match="self-loop"):
        validate_graph_snapshot(snap)


def test_duplicate_node_id_raises() -> None:
    snap = _valid_snap()
    snap["nodes"].append(copy.deepcopy(snap["nodes"][0]))
    with pytest.raises(ValueError, match="Duplicate node id"):
        validate_graph_snapshot(snap)


def test_block_range_end_before_start_raises() -> None:
    snap = _valid_snap()
    snap["block_range"] = {"start": 100, "end": 50}
    with pytest.raises(ValueError, match="block_range"):
        validate_graph_snapshot(snap)


def test_empty_nodes_rejected() -> None:
    snap = _valid_snap()
    snap["nodes"] = []
    with pytest.raises(ValidationError):
        validate_graph_snapshot(snap)


def test_additional_property_on_features_rejected() -> None:
    snap = _valid_snap()
    snap["nodes"][0]["features"]["extra"] = 1.0
    with pytest.raises(ValidationError):
        validate_graph_snapshot(snap)


def test_bad_snapshot_id_pattern() -> None:
    snap = _valid_snap()
    snap["snapshot_id"] = "not-a-uuid"
    with pytest.raises(ValidationError):
        validate_graph_snapshot(snap)


def test_top_level_additional_property_rejected() -> None:
    snap = _valid_snap()
    snap["extra_field"] = "surprise"
    with pytest.raises(ValidationError):
        validate_graph_snapshot(snap)


def test_edge_metadata_maxproperties() -> None:
    snap = _valid_snap()
    snap["edges"][0]["metadata"] = {f"key_{i}": i for i in range(33)}
    with pytest.raises(ValidationError):
        validate_graph_snapshot(snap)
