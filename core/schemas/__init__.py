"""Schema loaders and validators for QuantumRadar contracts.

This module exposes cached loaders for JSON Schemas under ``contracts/`` and
validator helpers that raise ``jsonschema.ValidationError`` on invalid input.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_TICK_SCHEMA_RELATIVE = Path("contracts") / "tick_data.schema.json"
_GRAPH_SCHEMA_RELATIVE = Path("contracts") / "graph_snapshot.schema.json"
_ALERT_SCHEMA_RELATIVE = Path("contracts") / "fragility_alert.schema.json"


def _find_contracts_root(sentinel: Path = _TICK_SCHEMA_RELATIVE) -> Path:
    """Walk parents until we find ``contracts/<sentinel>``.

    Supports both editable installs (schema lives at project root next to the
    ``core`` package) and future wheel layouts where the file may be shipped
    alongside the package as data. Raises ``FileNotFoundError`` with a clear
    message when the schema cannot be located.
    """
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        target = candidate / sentinel
        if target.is_file():
            return target.parent
    raise FileNotFoundError(
        f"Could not locate {sentinel} by walking up from {here}. "
        "Ensure the repo layout ships contracts/ or install in editable mode."
    )


@lru_cache(maxsize=1)
def load_tick_schema() -> dict[str, Any]:
    """Load and cache the tick-data JSON Schema."""
    schema_path = _find_contracts_root() / "tick_data.schema.json"
    with schema_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_graph_schema() -> dict[str, Any]:
    """Load and cache the graph-snapshot JSON Schema."""
    schema_path = _find_contracts_root(_GRAPH_SCHEMA_RELATIVE) / "graph_snapshot.schema.json"
    with schema_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_alert_schema() -> dict[str, Any]:
    """Load and cache the fragility-alert JSON Schema."""
    schema_path = _find_contracts_root(_ALERT_SCHEMA_RELATIVE) / "fragility_alert.schema.json"
    with schema_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _tick_validator() -> Draft202012Validator:
    """Return a cached Draft 2020-12 validator for tick-data events."""
    schema = load_tick_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@lru_cache(maxsize=1)
def _graph_validator() -> Draft202012Validator:
    """Return a cached Draft 2020-12 validator for graph snapshots."""
    schema = load_graph_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@lru_cache(maxsize=1)
def _alert_validator() -> Draft202012Validator:
    """Return a cached Draft 2020-12 validator for fragility alert payloads."""
    schema = load_alert_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_alert_payload(payload: dict[str, Any]) -> None:
    """Validate a fragility-alert webhook payload against the schema.

    Raises:
        jsonschema.ValidationError: if the payload does not match the schema
            (including cross-field `alert_level`/`fragility_score` constraints).
    """
    _alert_validator().validate(payload)


def validate_tick(event: dict[str, Any]) -> None:
    """Validate a normalized tick-data event against the schema.

    Raises:
        jsonschema.ValidationError: if the event does not match the schema.
    """
    _tick_validator().validate(event)


def validate_graph_snapshot(snap: dict[str, Any]) -> None:
    """Validate a GraphSnapshot dict against the schema + runtime invariants.

    Runtime invariants (not expressible in pure JSON Schema):

    * ``block_range.end >= block_range.start``
    * All node ``id`` values are unique.
    * Every edge ``src`` / ``dst`` references an existing ``node.id``.
    * Edges are not self-loops (``src != dst``).

    Raises:
        jsonschema.ValidationError: schema violations.
        ValueError: runtime invariant violations with a descriptive message.
    """
    _graph_validator().validate(snap)

    block_range = snap["block_range"]
    if block_range["end"] < block_range["start"]:
        raise ValueError(
            f"block_range.end ({block_range['end']}) < start ({block_range['start']})"
        )

    node_ids: list[str] = [node["id"] for node in snap["nodes"]]
    duplicates = {nid for nid in node_ids if node_ids.count(nid) > 1}
    if duplicates:
        raise ValueError(f"Duplicate node id(s): {sorted(duplicates)}")
    node_id_set = set(node_ids)

    for idx, edge in enumerate(snap["edges"]):
        src, dst = edge["src"], edge["dst"]
        # Check membership before self-loop: dangling references indicate data
        # corruption upstream and should surface with a clearer message.
        if src not in node_id_set:
            raise ValueError(f"Edge #{idx} src {src!r} not in node ids")
        if dst not in node_id_set:
            raise ValueError(f"Edge #{idx} dst {dst!r} not in node ids")
        if src == dst:
            raise ValueError(f"Edge #{idx} is a self-loop (src == dst == {src!r})")


__all__ = [
    "load_tick_schema",
    "load_graph_schema",
    "load_alert_schema",
    "validate_tick",
    "validate_graph_snapshot",
    "validate_alert_payload",
]
