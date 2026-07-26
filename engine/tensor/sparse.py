"""Sparse (CSR) adjacency tensor variant (Story 2B.4).

A memory-efficient alternative to the dense adjacency tensor (Story 2B.1) for
large, mostly-zero graphs (v2 scope — Story 2R.2 keeps dense as the v1 default
for the small N≈10-15 whitelist graph).

``sparse_adjacency_tensor(graph)`` builds a ``torch.sparse_csr`` ``(N, N)``
float32 matrix directly from the edge list (no dense intermediate), matching the
dense builder exactly: symmetric, weights accumulated, zero diagonal unless an
explicit self-loop exists.

CSR (not COO) is used because its index overhead (``crow_indices`` of length
``N+1`` plus one ``col_indices`` per non-zero) yields ≥80% memory savings at
~95% sparsity, whereas COO's ``2 × nnz`` int64 indices only reach ~75%.
"""

from __future__ import annotations

from typing import Any

import torch


def sparse_adjacency_tensor(graph: dict[str, Any]) -> torch.Tensor:
    """Build an ``(N, N)`` float32 **CSR** adjacency tensor from a GraphSnapshot.

    Equivalent to ``engine.tensor.adjacency.adjacency_tensor`` but stored sparsely.

    Raises:
        ValueError: if an edge references a ``src``/``dst`` id absent from ``nodes``.
    """
    nodes = graph["nodes"]
    n = len(nodes)
    index: dict[str, int] = {node["id"]: i for i, node in enumerate(nodes)}

    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
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
            rows.append(i)
            cols.append(i)
            vals.append(weight)
        else:
            rows.append(i)
            cols.append(j)
            vals.append(weight)
            rows.append(j)
            cols.append(i)
            vals.append(weight)

    if vals:
        indices = torch.tensor([rows, cols], dtype=torch.int64)
        values = torch.tensor(vals, dtype=torch.float32)
        coo = torch.sparse_coo_tensor(indices, values, (n, n)).coalesce()
    else:
        coo = torch.sparse_coo_tensor(
            torch.empty((2, 0), dtype=torch.int64),
            torch.empty((0,), dtype=torch.float32),
            (n, n),
        ).coalesce()

    return coo.to_sparse_csr()


def tensor_storage_bytes(t: torch.Tensor) -> int:
    """Return the storage footprint (bytes) of a dense / COO / CSR tensor.

    Sums ``element_size() * nelement()`` over the tensor's data components
    (values plus index arrays for sparse layouts).
    """
    layout = t.layout
    if layout == torch.strided:
        return t.element_size() * t.nelement()
    if layout == torch.sparse_coo:
        t = t.coalesce()
        idx, val = t.indices(), t.values()
        return idx.element_size() * idx.nelement() + val.element_size() * val.nelement()
    if layout == torch.sparse_csr:
        crow, col, val = t.crow_indices(), t.col_indices(), t.values()
        return (
            crow.element_size() * crow.nelement()
            + col.element_size() * col.nelement()
            + val.element_size() * val.nelement()
        )
    raise ValueError(f"Unsupported tensor layout: {layout}")


__all__ = ["sparse_adjacency_tensor", "tensor_storage_bytes"]
