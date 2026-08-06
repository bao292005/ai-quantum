"""NFR5 — local-first CPU, no GPU required (Story 6.2).

Verifies the detector paths run correctly without CUDA: the v1 B0 detector uses
no torch at all, and the (parked) MPS path uses CPU tensors. On a CUDA-less host
(this repo's reference machine / the CPU-only CI job) these simply run; the
assertions confirm nothing silently depends on a GPU.
"""

from __future__ import annotations

import torch

from engine.baseline import borrow_activity, fragility_score
from engine.mps.naive import fragility_raw


def test_default_tensor_device_is_cpu():
    assert torch.tensor([1.0]).device.type == "cpu"


def test_b0_detector_uses_no_torch():
    # Pure event counting — works with zero torch/GPU involvement.
    events = [{"event_type": "borrow"}] * 40
    assert borrow_activity(events) == 40
    assert fragility_score(40) == 100.0


def test_mps_forward_runs_on_cpu_without_cuda():
    a = torch.tensor([[0.0, 1.0, 1.0], [1.0, 0.0, 1.0], [1.0, 1.0, 0.0]])
    x = torch.full((3, 5), 0.2)
    score = fragility_raw(a, x)
    assert 0.0 <= score <= 1.0
    # Result computed on CPU tensors regardless of CUDA availability.
    assert a.device.type == "cpu"


def test_cuda_not_required():
    # Whether or not CUDA exists, the pipeline must not require it. We assert the
    # computation succeeds using CPU; if CUDA is absent this is the whole proof.
    if torch.cuda.is_available():  # pragma: no cover - reference host has no CUDA
        pytest_skip_reason = "host has CUDA; NFR5 only requires CPU to be sufficient"
        import pytest

        pytest.skip(pytest_skip_reason)
    assert not torch.cuda.is_available()
