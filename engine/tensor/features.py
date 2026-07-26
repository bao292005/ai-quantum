"""Node feature tensor constructor (Story 2B.2).

Converts a ``GraphSnapshot`` dict (schema 0.2) into an ``(N, F)`` float32 node
feature matrix for the MPS engine (Epic 3), paired with the adjacency tensor
(Story 2B.1) using the **same** node ordering.

The canonical feature set and column order are locked by Story 2R.1
(`research/feature_catalog.md`): ``FEATURE_ORDER``. ``F = 5``.

Sanitization (2R.1 missing-data policy): any ``NaN`` / ``inf`` feature value is
replaced with ``0.0`` and a warning is emitted — such values must never reach
the tensor math.
"""

from __future__ import annotations

import math
import warnings
from typing import Any

import torch

# Canonical feature column order — locked by Story 2R.1. Do not reorder.
FEATURE_ORDER: tuple[str, ...] = (
    "tvl_usd",
    "volume_24h_usd",
    "price_usd",
    "volatility",
    "connectivity",
)


def feature_tensor(graph: dict[str, Any]) -> torch.Tensor:
    """Build an ``(N, F)`` float32 node feature tensor from a GraphSnapshot.

    Rows follow the order of ``graph["nodes"]`` (identical to
    ``engine.tensor.adjacency.adjacency_tensor``); columns follow
    ``FEATURE_ORDER`` (F = 5).

    ``NaN`` / ``inf`` values are replaced with ``0.0`` and a warning is emitted
    (per the Story 2R.1 missing-data policy).

    Args:
        graph: a GraphSnapshot dict with ``nodes`` (each having ``id`` and a
            ``features`` mapping containing every key in ``FEATURE_ORDER``).

    Returns:
        A ``torch.float32`` tensor of shape ``(N, F)``.

    Raises:
        ValueError: if ``nodes`` is empty, or a node is missing a required
            feature key.
    """
    nodes = graph["nodes"]
    if not nodes:
        raise ValueError("feature_tensor requires at least one node")

    rows: list[list[float]] = []
    for node in nodes:
        node_id = node.get("id", "<unknown>")
        features = node["features"]
        row: list[float] = []
        for key in FEATURE_ORDER:
            if key not in features:
                raise ValueError(
                    f"Node {node_id!r} missing required feature {key!r}"
                )
            value = float(features[key])
            if math.isnan(value) or math.isinf(value):
                warnings.warn(
                    f"Node {node_id!r} feature {key!r} is {value}; substituting 0.0",
                    stacklevel=2,
                )
                value = 0.0
            row.append(value)
        rows.append(row)

    return torch.tensor(rows, dtype=torch.float32)


__all__ = ["feature_tensor", "FEATURE_ORDER"]
