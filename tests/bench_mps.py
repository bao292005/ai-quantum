"""MPS forward-pass latency benchmark harness (Story 3A.2).

Run explicitly — this file is intentionally named ``bench_*`` so the default
suite (``python_files = test_*.py``) does NOT collect it:

    pytest tests/bench_mps.py --benchmark-only

Measures p50/p95/p99 latency of ``engine.mps.naive.fragility_raw``, writes
``bench_report/{report.html,latency.json}``, and FAILS if p95 regresses more
than 10% over ``bench_report/baseline.json`` (the CI regression gate). The
official baseline is locked by Story 3A.4 (git tag ``baseline-v0``); until then
this harness bootstraps a baseline from the first run.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from engine.mps.naive import fragility_raw

REPORT_DIR = Path(__file__).resolve().parent.parent / "bench_report"
BASELINE_PATH = REPORT_DIR / "baseline.json"
REGRESSION_TOL = 0.10  # fail if p95 > baseline * (1 + TOL)
GATE_MS = 30.0  # Story 3E.1 — MPS forward-pass p95 hard budget (NFR1 subcomponent)


def _synth(n: int, seed: int = 0) -> tuple[torch.Tensor, torch.Tensor]:
    """Deterministic symmetric non-negative (A, X) of size n."""
    g = torch.Generator().manual_seed(seed)
    raw = torch.rand(n, n, generator=g)
    adj = (raw + raw.t()) / 2
    adj.fill_diagonal_(0.0)
    feats = torch.rand(n, 5, generator=g)
    return adj, feats


def _percentiles_ms(benchmark) -> dict[str, float]:
    data = np.asarray(benchmark.stats.stats.data, dtype=float) * 1000.0  # ms
    return {
        "p50": float(np.percentile(data, 50)),
        "p95": float(np.percentile(data, 95)),
        "p99": float(np.percentile(data, 99)),
        "mean": float(data.mean()),
        "rounds": int(data.size),
    }


def _load_baseline() -> dict[str, dict]:
    if BASELINE_PATH.exists():
        return json.loads(BASELINE_PATH.read_text())
    return {}


def _write_html(results: dict[str, dict]) -> None:
    rows = "".join(
        f"<tr><td>{name}</td><td>{s['p50']:.4f}</td><td>{s['p95']:.4f}</td>"
        f"<td>{s['p99']:.4f}</td><td>{s['mean']:.4f}</td><td>{s['rounds']}</td></tr>"
        for name, s in results.items()
    )
    (REPORT_DIR / "report.html").write_text(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>MPS forward-pass benchmark</title></head><body>"
        "<h1>MPS forward-pass latency (Story 3A.2)</h1>"
        "<p><code>engine.mps.naive.fragility_raw</code> — times in milliseconds.</p>"
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<tr><th>benchmark</th><th>p50</th><th>p95</th><th>p99</th>"
        "<th>mean</th><th>rounds</th></tr>"
        f"{rows}</table></body></html>"
    )


@pytest.fixture(scope="session")
def bench_results():
    """Collect per-benchmark stats and emit the report on session teardown."""
    results: dict[str, dict] = {}
    yield results
    if not results:
        return
    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / "latency.json").write_text(json.dumps(results, indent=2))
    _write_html(results)
    # Bootstrap baseline entries that don't exist yet; never overwrite an
    # existing (3A.4-locked) baseline value.
    baseline = _load_baseline()
    missing = {n: {"p95": s["p95"]} for n, s in results.items() if n not in baseline}
    if missing:
        baseline.update(missing)
        BASELINE_PATH.write_text(json.dumps(baseline, indent=2))


def _run(benchmark, results: dict, name: str, n: int) -> None:
    adj, feats = _synth(n)
    out = benchmark(fragility_raw, adj, feats)
    assert 0.0 <= out <= 1.0
    stat = _percentiles_ms(benchmark)
    results[name] = stat

    # Story 3E.1 — hard latency gate on the MPS forward pass.
    assert stat["p95"] < GATE_MS, (
        f"{name} p95 {stat['p95']:.4f}ms exceeds 3E.1 gate {GATE_MS}ms"
    )

    baseline = _load_baseline()
    if name in baseline:
        limit = baseline[name]["p95"] * (1 + REGRESSION_TOL)
        assert stat["p95"] <= limit, (
            f"{name} p95 regression: {stat['p95']:.4f}ms > {limit:.4f}ms "
            f"(baseline {baseline[name]['p95']:.4f}ms + {int(REGRESSION_TOL * 100)}%)"
        )


@pytest.mark.benchmark(group="mps-forward")
def test_bench_fragility_n15(benchmark, bench_results):
    """Realtime v1 scale (N ≈ 10–15, Story 2R.2)."""
    _run(benchmark, bench_results, "mps-forward:n15", 15)


@pytest.mark.benchmark(group="mps-forward")
def test_bench_fragility_n50(benchmark, bench_results):
    """Story 3A.1 AC input size (50-node graph)."""
    _run(benchmark, bench_results, "mps-forward:n50", 50)
