"""Pydantic models for graph node types (Story 2A.1).

Defines the ``Node`` and ``NodeFeatures`` models that mirror
``contracts/graph_snapshot.schema.json#/$defs/node``. The canonical node
feature set was locked by Story 2R.1 (`research/feature_catalog.md`) to the
schema-0.2 set: ``tvl_usd``, ``volume_24h_usd``, ``price_usd``, ``volatility``,
``connectivity``.

``model_config = ConfigDict(extra="forbid")`` mirrors the schema's
``additionalProperties: false`` so a ``model_dump()`` round-trips cleanly
through ``core.schemas.validate_graph_snapshot``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NodeType = Literal["protocol", "pool", "token"]


class NodeFeatures(BaseModel):
    """Node feature vector — canonical 5-feature set (Story 2R.1).

    Ranges mirror ``graph_snapshot.schema.json``: all features are ``>= 0`` and
    ``connectivity`` is additionally bounded to ``[0, 1]``.

    ``allow_inf_nan=False`` rejects ``inf``/``nan`` explicitly (Story 2A.1 code
    review P1): JSON has no ``Infinity`` literal, and either value would poison
    downstream tensor math (Epic 2/3).
    """

    model_config = ConfigDict(extra="forbid")

    tvl_usd: float = Field(ge=0, allow_inf_nan=False)
    volume_24h_usd: float = Field(ge=0, allow_inf_nan=False)
    price_usd: float = Field(ge=0, allow_inf_nan=False)
    volatility: float = Field(ge=0, allow_inf_nan=False)
    connectivity: float = Field(ge=0, le=1, allow_inf_nan=False)


class Node(BaseModel):
    """A single graph node (``protocol`` | ``pool`` | ``token``)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    type: NodeType
    features: NodeFeatures


__all__ = ["Node", "NodeFeatures", "NodeType"]
