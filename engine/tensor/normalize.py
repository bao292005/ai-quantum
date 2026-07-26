"""Per-column feature normalization (Story 2B.3).

`normalize(tensor, method)` standardizes an ``(N, F)`` feature tensor column-wise
and returns a ``NormalizationState`` capturing the fitted parameters so the exact
same transform can be re-applied at inference time (avoids train-serve skew).

Methods:

- ``"minmax"``  → each column mapped to ``[0, 1]`` (``(x - min) / (max - min)``).
- ``"zscore"``  → each column to ``mean≈0, std≈1`` (population std, ``unbiased=False``).

Division-by-zero is guarded: a constant column (``max == min`` or ``std == 0``)
produces ``0.0`` for that column instead of ``NaN``.

Per-feature refinements suggested by Story 2R.1 (log1p for heavy-tailed monetary
features, per-token z-score for price, skipping the already-[0,1] ``connectivity``)
are intentionally deferred to a future iteration — this story ships the generic
toggle only.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

_VALID_METHODS = ("minmax", "zscore")


@dataclass(frozen=True)
class NormalizationState:
    """Fitted per-column normalization parameters, reusable at inference.

    Attributes:
        method: ``"minmax"`` or ``"zscore"``.
        offset: per-column subtractive term (``min`` for minmax, ``mean`` for zscore).
        scale: per-column divisor (``max - min`` for minmax, ``std`` for zscore),
            with zero entries replaced by ``1`` so ``apply`` never divides by zero
            (the corresponding column is zeroed via ``zero_mask``).
        zero_mask: per-column boolean; ``True`` where the original scale was ``0``
            (constant column) → output forced to ``0``.
    """

    method: str
    offset: torch.Tensor
    scale: torch.Tensor
    zero_mask: torch.Tensor

    def apply(self, tensor: torch.Tensor) -> torch.Tensor:
        """Apply the fitted transform to ``tensor`` (shape ``(*, F)``)."""
        out = (tensor.to(torch.float32) - self.offset) / self.scale
        out = torch.where(self.zero_mask, torch.zeros_like(out), out)
        return out.to(torch.float32)


def normalize(
    tensor: torch.Tensor, method: str = "minmax"
) -> tuple[torch.Tensor, NormalizationState]:
    """Column-wise normalize ``tensor`` and return ``(normalized, state)``.

    Args:
        tensor: an ``(N, F)`` tensor (cast to float32).
        method: ``"minmax"`` or ``"zscore"``.

    Returns:
        The normalized ``(N, F)`` float32 tensor and the fitted
        ``NormalizationState`` (reusable via ``state.apply``).

    Raises:
        ValueError: if ``method`` is not one of ``{"minmax", "zscore"}``.
    """
    if method not in _VALID_METHODS:
        raise ValueError(
            f"Unknown method {method!r}; expected one of {_VALID_METHODS}"
        )

    x = tensor.to(torch.float32)

    if method == "minmax":
        offset = x.min(dim=0).values
        scale = x.max(dim=0).values - offset
    else:  # zscore
        offset = x.mean(dim=0)
        scale = x.std(dim=0, unbiased=False)

    zero_mask = scale == 0
    safe_scale = torch.where(zero_mask, torch.ones_like(scale), scale)

    state = NormalizationState(
        method=method, offset=offset, scale=safe_scale, zero_mask=zero_mask
    )
    return state.apply(x), state


__all__ = ["normalize", "NormalizationState"]
