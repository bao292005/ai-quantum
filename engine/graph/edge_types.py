"""Pydantic model for graph edge types (Story 2A.2).

Mirrors ``contracts/graph_snapshot.schema.json#/$defs/edge``. Edge types use the
schema's snake_case enum (`liquidity_flow`, `borrow_position`,
`shared_collateral`) — the contract is the source of truth, not the CamelCase
names used in prose.

This story defines edge STRUCTURE and the ``weight`` range ``[0, 1]`` only. The
weight *formula* (Story 2A.4) is applied later by the Graph Builder (2A.3).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EdgeType = Literal["liquidity_flow", "borrow_position", "shared_collateral"]

_MAX_METADATA_KEYS = 32


class Edge(BaseModel):
    """A single directed graph edge with a normalized ``weight`` in ``[0, 1]``."""

    model_config = ConfigDict(extra="forbid")

    src: str = Field(min_length=1, max_length=128)
    dst: str = Field(min_length=1, max_length=128)
    weight: float = Field(ge=0, le=1)
    edge_type: EdgeType
    metadata: dict[str, Any] | None = None

    @field_validator("metadata")
    @classmethod
    def _max_32_keys(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is not None and len(v) > _MAX_METADATA_KEYS:
            raise ValueError(
                f"metadata exceeds {_MAX_METADATA_KEYS} keys (got {len(v)})"
            )
        return v


__all__ = ["Edge", "EdgeType"]
