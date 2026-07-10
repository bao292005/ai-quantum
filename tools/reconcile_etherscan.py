"""Etherscan reconciliation tool (Story 1E.2).

Samples a few blocks from a live ring buffer, re-fetches those blocks' events
from Etherscan, compares them field-by-field, and writes ``reconcile_report.md``.
Exits non-zero if the match rate falls below 99.5% — objective on-chain evidence
that ingestion (Track 1A/1B/1C) captured events faithfully.

Usage:
    python -m tools.reconcile_etherscan [--wss-url ...] [--duration 300]
                                        [--samples 3] [--seed N] [--out PATH]

The comparison core (:func:`reconcile`) is pure and takes an injectable
``fetch_block_events`` so it is unit-tested without any network access.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

_COMPARE_FIELDS = ("event_type", "pool_address", "token0", "token1", "amount0", "amount1")
_GATE = 0.995


@dataclass
class ReconcileResult:
    match_rate: float
    ok: bool
    total: int
    matched: int
    mismatches: list[dict] = field(default_factory=list)
    report_md: str = ""


def _key(e: dict) -> tuple[str, int]:
    return (str(e["tx_hash"]).lower(), int(e["log_index"]))


def _norm(e: dict) -> tuple:
    return tuple(str(e[f]).lower() for f in _COMPARE_FIELDS)


def sample_blocks(events: list[dict], n: int, seed: int | None = None) -> list[int]:
    """Pick up to ``n`` distinct block numbers from ``events`` (seeded, sorted)."""
    blocks = sorted({e["block_number"] for e in events})
    rng = random.Random(seed)
    return sorted(rng.sample(blocks, min(n, len(blocks))))


def render_report(
    sample: list[int],
    buf: list[dict],
    onchain: dict,
    matched: int,
    total: int,
    rate: float,
    mismatches: list[dict],
) -> str:
    lines = [
        "# Etherscan Reconciliation Report",
        "",
        f"- Sampled blocks: {sample}",
        f"- Buffer events (sampled blocks): {total}",
        f"- On-chain events fetched: {len(onchain)}",
        f"- Matched: {matched}",
        f"- **Match rate: {rate * 100:.2f}%** (gate: {_GATE * 100:.1f}%) — "
        f"{'PASS' if rate >= _GATE else 'FAIL'}",
        "",
        "## Per-block",
    ]
    for b in sample:
        bc = sum(1 for e in buf if e["block_number"] == b)
        oc = sum(1 for k in onchain if onchain[k].get("block_number") == b)
        lines.append(f"- block {b}: buffer={bc}, on-chain={oc}")
    if mismatches:
        lines += ["", "## Mismatches", ""]
        for m in mismatches:
            lines.append(f"- `{m['key']}` buffer={m['buffer']} onchain={m['onchain']}")
    return "\n".join(lines) + "\n"


def reconcile(
    events: list[dict],
    sample: list[int],
    fetch_block_events: Callable[[int], list[dict]],
) -> ReconcileResult:
    """Compare buffer ``events`` in ``sample`` blocks against on-chain events.

    ``fetch_block_events(block)`` returns normalized on-chain event dicts for a
    block. Match keyed by ``(tx_hash, log_index)``; an event counts as matched
    only if the compared content fields are identical. Rate = matched / buffer
    events in the sampled blocks.
    """
    sample_set = set(sample)
    buf = [e for e in events if e["block_number"] in sample_set]
    onchain: dict[tuple, dict] = {}
    for b in sample:
        for oe in fetch_block_events(b):
            onchain[_key(oe)] = oe

    matched = 0
    mismatches: list[dict] = []
    for e in buf:
        oe = onchain.get(_key(e))
        if oe is not None and _norm(oe) == _norm(e):
            matched += 1
        else:
            mismatches.append({
                "key": _key(e),
                "buffer": _norm(e),
                "onchain": _norm(oe) if oe is not None else None,
            })
    total = len(buf)
    if total == 0:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "reconcile: no buffer events in sampled blocks %s — "
            "returning ok=False (empty buffer cannot confirm data fidelity)",
            sample,
        )
        rate = 0.0
    else:
        rate = matched / total
    return ReconcileResult(
        match_rate=rate,
        ok=(rate >= _GATE),
        total=total,
        matched=matched,
        mismatches=mismatches,
        report_md=render_report(sample, buf, onchain, matched, total, rate, mismatches),
    )


# ---------------------------------------------------------------------------
# Etherscan fetch adapter (network) — reuses tools.extract_fixtures + Track 1B.
# ---------------------------------------------------------------------------

def make_etherscan_fetcher(whitelist, router, api_key: str) -> Callable[[int], list[dict]]:
    """Build a ``fetch_block_events`` that pulls a block's logs from Etherscan.

    Reuses ``tools.extract_fixtures.etherscan_get_logs`` for the HTTP client and
    the Track 1B ``EventRouter`` to normalize raw logs (so per-pool token
    metadata comes from the same whitelist the pipeline used).
    """
    from ingestion.decoders.aave_v3 import (
        BORROW_TOPIC,
        LIQUIDATION_TOPIC,
        SUPPLY_TOPIC,
        WITHDRAW_TOPIC,
    )
    from ingestion.decoders.uniswap_v3 import BURN_TOPIC, MINT_TOPIC, SWAP_TOPIC
    from tools.extract_fixtures import etherscan_get_logs

    topics = {
        "uniswap_v3": [SWAP_TOPIC, MINT_TOPIC, BURN_TOPIC],
        "aave_v3": [SUPPLY_TOPIC, BORROW_TOPIC, WITHDRAW_TOPIC, LIQUIDATION_TOPIC],
    }

    def fetch(block: int) -> list[dict]:
        out: list[dict] = []
        for addr in whitelist.addresses():
            entry = whitelist.get(addr)
            for topic0 in topics.get(entry.protocol, []):
                logs = etherscan_get_logs(
                    from_block=block, to_block=block, address=addr,
                    topic0=topic0, api_key=api_key,
                )
                for log in logs:
                    block_ts = int(log["timeStamp"], 16)
                    event = router.route(log, block_ts)
                    if event is not None:
                        out.append(event.to_dict())
        return out

    return fetch


async def _fill_buffer(wss_url: str, whitelist_path: str, duration: float):
    """Run realtime ingestion for ``duration`` seconds and return the buffer."""
    from core.ring_buffer import DequeRingBuffer
    from ingestion.pipeline import run_realtime
    from ingestion.router import EventRouter

    # Large capacity: keep the whole window so sampled blocks are not evicted.
    buffer = DequeRingBuffer(capacity=100_000)
    router = EventRouter.from_yaml(whitelist_path)
    stop = asyncio.Event()
    task = asyncio.create_task(run_realtime(buffer, router, wss_url, stop))
    await asyncio.sleep(duration)
    stop.set()
    await asyncio.wait_for(task, timeout=5)
    return buffer, router


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="tools.reconcile_etherscan")
    p.add_argument("--wss-url", default="ws://localhost:8546")
    p.add_argument("--duration", type=float, default=300.0, help="realtime ingest window (s)")
    p.add_argument("--samples", type=int, default=3)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--whitelist", default="ingestion/whitelist.yaml")
    p.add_argument("--out", default="reconcile_report.md")
    return p.parse_args(argv)


def main(argv=None) -> int:
    from tools.extract_fixtures import _get_api_key

    args = _parse_args(argv)
    buffer, router = asyncio.run(_fill_buffer(args.wss_url, args.whitelist, args.duration))
    events = buffer.read_all()
    sample = sample_blocks(events, args.samples, seed=args.seed)
    if not sample:
        print("reconcile: buffer empty — nothing to reconcile", file=sys.stderr)
        return 1
    fetch = make_etherscan_fetcher(router.whitelist, router, _get_api_key())
    result = reconcile(events, sample, fetch)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(result.report_md)
    print(result.report_md)
    if not result.ok:
        print(f"reconcile FAILED: match rate {result.match_rate * 100:.2f}% < "
              f"{_GATE * 100:.1f}%", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
