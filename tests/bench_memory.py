"""MPS forward-pass memory profiler (Story 3A.3).

Run explicitly (``bench_*`` name → NOT collected by the default suite):

    pytest tests/bench_memory.py -s

Profiles ``engine.mps.naive.fragility_raw`` with :mod:`tracemalloc` (steady-state
forward-pass allocations + top allocation breakdown) and reports process peak RSS
via :func:`resource.getrusage`. Writes ``bench_report/memory.md`` and FAILS if the
traced forward-pass peak exceeds the 500 MB PoC limit.

Note on the gate: the 500 MB limit is checked against the **tracemalloc traced
peak of the forward pass** (the isolatable, controllable metric), NOT whole-process
RSS — the PyTorch runtime's base RSS footprint is large and constant, so gating on
RSS would be flaky. RSS is reported for context only.
"""

from __future__ import annotations

import resource
import sys
import tracemalloc
from pathlib import Path

import torch

from engine.mps.naive import fragility_raw

REPORT_DIR = Path(__file__).resolve().parent.parent / "bench_report"
PEAK_LIMIT_MB = 500.0
_PROFILE_SIZES = (15, 50, 128)
_ROUNDS = 50
_MB = 1024 * 1024


def _synth(n: int, seed: int = 0) -> tuple[torch.Tensor, torch.Tensor]:
    g = torch.Generator().manual_seed(seed)
    raw = torch.rand(n, n, generator=g)
    adj = (raw + raw.t()) / 2
    adj.fill_diagonal_(0.0)
    feats = torch.rand(n, 5, generator=g)
    return adj, feats


def _peak_rss_mb() -> float:
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux reports kilobytes.
    return ru / _MB if sys.platform == "darwin" else ru / 1024


def _profile(n: int) -> tuple[float, float, list]:
    adj, feats = _synth(n)
    fragility_raw(adj, feats)  # warm-up: exclude one-time torch/internal allocs
    tracemalloc.start()
    for _ in range(_ROUNDS):
        fragility_raw(adj, feats)
    current, peak = tracemalloc.get_traced_memory()
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()
    top = snapshot.statistics("lineno")[:10]
    return current / _MB, peak / _MB, top


def _write_md(results: dict[int, dict], rss_mb: float) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    lines = [
        "# MPS Forward-Pass Memory Profile (Story 3A.3)",
        "",
        f"`fragility_raw` over {_ROUNDS} steady-state rounds (post warm-up).",
        f"PoC gate: traced forward-pass peak < **{PEAK_LIMIT_MB:.0f} MB**.",
        "",
        "| N | traced current (MB) | traced peak (MB) | gate |",
        "|---:|---:|---:|:--:|",
    ]
    for n, r in results.items():
        gate = "PASS" if r["peak"] < PEAK_LIMIT_MB else "FAIL"
        lines.append(f"| {n} | {r['current']:.4f} | {r['peak']:.4f} | {gate} |")
    lines += [
        "",
        f"Process peak RSS (informational, incl. PyTorch runtime base): "
        f"**{rss_mb:.1f} MB**.",
        "",
        f"## Top allocation sites (N={_PROFILE_SIZES[-1]}, by size)",
        "",
        "| # | location | size (KB) | count |",
        "|---:|---|---:|---:|",
    ]
    for i, stat in enumerate(results[_PROFILE_SIZES[-1]]["top"], start=1):
        frame = stat.traceback[0]
        loc = f"{Path(frame.filename).name}:{frame.lineno}"
        lines.append(f"| {i} | {loc} | {stat.size / 1024:.2f} | {stat.count} |")
    lines.append("")
    (REPORT_DIR / "memory.md").write_text("\n".join(lines))


def test_memory_profile_forward_pass():
    results: dict[int, dict] = {}
    for n in _PROFILE_SIZES:
        current, peak, top = _profile(n)
        results[n] = {"current": current, "peak": peak, "top": top}

    rss_mb = _peak_rss_mb()
    _write_md(results, rss_mb)

    worst_peak = max(r["peak"] for r in results.values())
    assert worst_peak < PEAK_LIMIT_MB, (
        f"forward-pass traced peak {worst_peak:.2f}MB exceeds {PEAK_LIMIT_MB}MB PoC limit"
    )
