"""Data-quality profiling report (Story 1E.3).

Turns a window of ring-buffer events into a self-contained HTML report: event
counts per protocol/type, block drop rate, per-protocol breakdown, and a
timestamp-gap histogram that flags any gap > 30s.

Design note: the epic named a Jupyter notebook, but jupyter is not installed and
notebooks are not unit-testable. This ships the same analysis as a pure,
testable module (:func:`profile`) plus an HTML renderer (:func:`render_html`)
with matplotlib charts embedded as base64 PNG (self-contained, no extra files).
"""

from __future__ import annotations

import argparse
import base64
import html
import io
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

_GAP_THRESHOLD_S = 30.0


@dataclass
class QualityProfile:
    total_events: int
    per_protocol: dict[str, int]
    per_event_type: dict[str, int]
    n_blocks: int
    block_range: tuple[int, int]
    block_drop_rate: float
    timestamp_gaps: list[tuple[int, int, float]] = field(default_factory=list)
    gaps_over_30s: list[tuple[int, int, float]] = field(default_factory=list)


def profile(events: list[dict], *, blocks_seen: list[int] | None = None) -> QualityProfile:
    """Compute data-quality stats over ``events`` (pure, no I/O).

    ``blocks_seen`` is the sequence of block numbers observed on the newHeads
    stream; when given, block drop rate is measured against it. Otherwise drop
    rate is derived from event coverage (a block with no whitelisted event is
    indistinguishable from a dropped block — caveat).
    """
    if not events:
        return QualityProfile(0, {}, {}, 0, (0, 0), 0.0)

    per_proto = Counter(e["protocol"] for e in events)
    per_type = Counter(e["event_type"] for e in events)

    ts_by_block: dict[int, str] = {}
    for e in events:
        ts_by_block.setdefault(e["block_number"], e["block_timestamp"])
    blocks = sorted(ts_by_block)
    lo, hi = blocks[0], blocks[-1]
    span = hi - lo + 1

    if blocks_seen:
        drop = 1 - len(set(blocks_seen)) / span
    else:
        drop = 1 - len(blocks) / span

    gaps: list[tuple[int, int, float]] = []
    for a, b in zip(blocks, blocks[1:]):
        secs = (
            datetime.fromisoformat(ts_by_block[b]) - datetime.fromisoformat(ts_by_block[a])
        ).total_seconds()
        gaps.append((a, b, secs))
    over = [g for g in gaps if g[2] > _GAP_THRESHOLD_S]

    return QualityProfile(
        total_events=len(events),
        per_protocol=dict(per_proto),
        per_event_type=dict(per_type),
        n_blocks=len(blocks),
        block_range=(lo, hi),
        block_drop_rate=max(0.0, drop),
        timestamp_gaps=gaps,
        gaps_over_30s=over,
    )


def _bar_png(labels: list[str], values: list[float], title: str) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5, 3))
    ax.bar(labels, values)
    ax.set_title(title)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _table(title: str, mapping: dict) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(str(k))}</td><td>{v}</td></tr>" for k, v in mapping.items()
    )
    return f"<h3>{html.escape(title)}</h3><table border=1>{rows}</table>"


def render_html(p: QualityProfile, *, charts: bool = True) -> str:
    """Render a self-contained HTML quality report.

    ``charts=True`` embeds 4 matplotlib bar charts as base64 PNG; if matplotlib
    is unavailable it degrades to tables only (never crashes).
    """
    parts: list[str] = [
        "<html><head><meta charset='utf-8'><title>Data Quality Report</title></head><body>",
        "<h1>QuantumRadar — Ingestion Data Quality</h1>",
        "<ul>",
        f"<li>Total events: {p.total_events}</li>",
        f"<li>Distinct blocks: {p.n_blocks} (range {p.block_range[0]}–{p.block_range[1]})</li>",
        f"<li>Block drop rate: {p.block_drop_rate * 100:.2f}%</li>",
        "</ul>",
    ]

    if charts:
        gap_secs = [g[2] for g in p.timestamp_gaps]
        chart_specs = [
            (list(p.per_protocol), list(p.per_protocol.values()), "Events per protocol"),
            (list(p.per_event_type), list(p.per_event_type.values()), "Events per type"),
            (["blocks", "dropped"], [p.n_blocks, round(p.block_drop_rate * p.n_blocks, 2)], "Block coverage"),
            ([str(i) for i in range(len(gap_secs))], gap_secs, "Timestamp gaps (s)"),
        ]
        for labels, values, title in chart_specs:
            if not labels:
                continue
            try:
                parts.append(f"<h3>{html.escape(title)}</h3><img src='{_bar_png(labels, values, title)}'/>")
            except Exception:  # matplotlib missing/broken — fall back to a table below
                parts.append(_table(title, dict(zip(labels, values))))

    parts.append(_table("Events per protocol", p.per_protocol))
    parts.append(_table("Events per event_type", p.per_event_type))

    # Timestamp-gap flagging (AC4).
    parts.append("<h3>Timestamp gaps &gt; 30s</h3>")
    if p.gaps_over_30s:
        rows = "".join(
            f"<tr style='background:#fdd'><td>{a}→{b}</td><td>{secs:.0f}s</td></tr>"
            for a, b, secs in p.gaps_over_30s
        )
        parts.append(f"<table border=1><tr><th>blocks</th><th>gap</th></tr>{rows}</table>")
    else:
        parts.append("<p>no gaps &gt; 30s ✓</p>")

    parts.append("</body></html>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="tools.profile_quality")
    p.add_argument("--source", choices=["mock", "csv"], default="csv")
    p.add_argument("--scenario", choices=["luna", "ftx", "normal"], default="luna")
    p.add_argument("--file", default=None, help="explicit CSV path (overrides --scenario)")
    p.add_argument("--wss-url", default="ws://localhost:8546")
    p.add_argument("--duration", type=float, default=300.0)
    p.add_argument("--whitelist", default="ingestion/whitelist.yaml")
    p.add_argument("--out", default="data_quality_report.html")
    return p.parse_args(argv)


def _load_events(args) -> list[dict]:
    if args.source == "csv":
        from ingestion.csv_loader import iter_csv_events
        from tools.mock_wss.replay import resolve_scenario_file

        path = args.file or resolve_scenario_file(args.scenario)
        return list(iter_csv_events(path))

    import asyncio

    from core.ring_buffer import DequeRingBuffer
    from ingestion.pipeline import run_realtime
    from ingestion.router import EventRouter

    async def _fill() -> list[dict]:
        buffer = DequeRingBuffer(capacity=100_000)
        router = EventRouter.from_yaml(args.whitelist)
        stop = asyncio.Event()
        task = asyncio.create_task(run_realtime(buffer, router, args.wss_url, stop))
        await asyncio.sleep(args.duration)
        stop.set()
        await asyncio.wait_for(task, timeout=5)
        return buffer.read_all()

    return asyncio.run(_fill())


def main(argv=None) -> int:
    from pathlib import Path

    args = _parse_args(argv)
    events = _load_events(args)
    report = render_html(profile(events))
    Path(args.out).write_text(report, encoding="utf-8")
    print(f"wrote {args.out} ({len(events)} events)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
