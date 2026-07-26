"""Adjacency tensor constructor (Story 2B.1).

Converts a ``GraphSnapshot`` dict (schema 0.2) into an ``(N, N)`` float32
adjacency matrix for the MPS engine (Epic 3).

Design decisions (v1):

- **Node ordering** is the order of appearance in ``graph["nodes"]`` (row/col
  index ``0..N-1``).
- **Symmetric / undirected:** every edge contributes to both ``A[i, j]`` and
  ``A[j, i]``. All edge types (including the naturally-directed
  ``borrow_position``) are symmetrized in v1 — a modelling assumption to be
  ratified/overridden by Story 2R.2 / 3R.1 if a directed matrix is ever needed.
- **Aggregation:** multiple edges between the same node pair accumulate
  (``+=``); a cell value may therefore exceed 1 even though per-edge ``weight``
  is bounded to ``[0, 1]``.
- **Diagonal:** ``0`` unless an explicit self-loop edge (``src == dst``) exists,
  in which case its weight is added once to the diagonal.
"""

from __future__ import annotations

from typing import Any

import torch


def adjacency_tensor(graph: dict[str, Any]) -> torch.Tensor:
    """Build an ``(N, N)`` float32 symmetric adjacency tensor from a GraphSnapshot.

    Args:
        graph: a GraphSnapshot dict with ``nodes`` (each having an ``id``) and
            ``edges`` (each having ``src``, ``dst``, ``weight``).

    Returns:
        A ``torch.float32`` tensor of shape ``(N, N)`` where ``N = len(nodes)``.

    Raises:
        ValueError: if an edge references a ``src``/``dst`` id not present in
            ``nodes`` (dangling reference — surfaced, never silently dropped).
    """
    nodes = graph["nodes"]
    n = len(nodes)
    index: dict[str, int] = {}
    for i, node in enumerate(nodes):
        index[node["id"]] = i

    adj = torch.zeros((n, n), dtype=torch.float32)

    for edge in graph["edges"]:
        src, dst = edge["src"], edge["dst"]
        try:
            i = index[src]
        except KeyError as exc:
            raise ValueError(f"Edge src {src!r} not in node ids") from exc
        try:
            j = index[dst]
        except KeyError as exc:
            raise ValueError(f"Edge dst {dst!r} not in node ids") from exc

        weight = float(edge["weight"])
        if i == j:
            adj[i, i] += weight
        else:
            adj[i, j] += weight
            adj[j, i] += weight

    return adj


__all__ = ["adjacency_tensor"]
