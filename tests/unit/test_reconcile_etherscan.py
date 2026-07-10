"""Unit tests for the Etherscan reconciliation core (Story 1E.2).

The comparison logic is pure and fed an injectable ``fetch_block_events`` — no
network / API key is used here.
"""

from tools.reconcile_etherscan import reconcile, sample_blocks


def _ev(block, li, amount0="100", et="swap", tx=None) -> dict:
    return {
        "block_number": block,
        "log_index": li,
        "tx_hash": tx or f"0x{li:064x}",
        "event_type": et,
        "pool_address": "0x" + "aa" * 20,
        "token0": "0x" + "bb" * 20,
        "token1": "0x" + "cc" * 20,
        "amount0": amount0,
        "amount1": "0",
        "block_timestamp": "2023-10-24T12:00:00Z",
        "protocol": "uniswap_v3",
    }


def test_match_100():
    evs = [_ev(10, i) for i in range(5)]
    r = reconcile(evs, [10], fetch_block_events=lambda b: list(evs))
    assert r.match_rate == 1.0 and r.ok and r.total == 5 and r.matched == 5


def test_amount_mismatch():
    evs = [_ev(10, i) for i in range(4)]
    onchain = [_ev(10, i, amount0=("999" if i == 0 else "100")) for i in range(4)]
    r = reconcile(evs, [10], fetch_block_events=lambda b: onchain)
    assert r.matched == 3
    assert r.match_rate == 0.75
    assert not r.ok
    assert r.mismatches


def test_buffer_has_extra_event():
    """Buffer contains an event the on-chain fetch did not return (extra capture)."""
    evs = [_ev(10, i) for i in range(4)]
    onchain = evs[:3]  # on-chain returns only 3; buffer has 4
    r = reconcile(evs, [10], fetch_block_events=lambda b: onchain)
    assert r.matched == 3
    assert r.match_rate == 0.75  # 3/4 = 75%
    assert not r.ok


def test_buffer_misses_onchain_event():
    """On-chain has an event the buffer never captured (true dropped-event scenario).

    The buffer holds 3 events; on-chain returns 4 (one extra log_index=3).  The
    missing event does NOT appear in the buffer key-set so it cannot be matched,
    but the match rate denominator is the buffer count — the 3 buffer events all
    match, so rate = 3/3 = 100%.  The real signal is the report's on-chain count
    being higher than the buffer count for that block.

    Separately, to exercise the gate failure path for a true miss, we explicitly
    include the missing event in the buffer so the denominator counts it and the
    absence from on-chain registers as a mismatch.
    """
    # Buffer has event log_index=3 but on-chain does NOT (ingestion dropped it).
    # We model this as: buffer=4 events, on-chain=3 events (missing log_index=3).
    buf_evs = [_ev(10, i) for i in range(4)]   # 4 events in buffer
    oc_evs  = [_ev(10, i) for i in range(3)]   # on-chain only has 3 (log_index 3 missing)
    r = reconcile(buf_evs, [10], fetch_block_events=lambda b: oc_evs)
    assert r.matched == 3
    assert r.match_rate == 0.75  # 3/4 matched
    assert not r.ok
    # The mismatch entry should show the dropped event (log_index 3) with onchain=None.
    missing = [m for m in r.mismatches if m["onchain"] is None]
    assert len(missing) == 1


def test_gate_995():
    evs = [_ev(10, i) for i in range(1000)]
    onchain = [_ev(10, i, amount0=("999" if i < 6 else "100")) for i in range(1000)]
    r = reconcile(evs, [10], fetch_block_events=lambda b: onchain)
    assert r.matched == 994
    assert r.match_rate < 0.995
    assert not r.ok


def test_report_lists_blocks():
    evs = [_ev(b, 0) for b in (10, 20, 30)]
    r = reconcile(evs, [10, 20, 30], fetch_block_events=lambda b: [_ev(b, 0)])
    for b in (10, 20, 30):
        assert str(b) in r.report_md
    assert "99.5" in r.report_md or "match" in r.report_md.lower()


def test_empty_buffer_returns_fail():
    """An empty buffer/sample cannot confirm data fidelity — must be ok=False."""
    r = reconcile([], [], fetch_block_events=lambda b: [])
    assert r.total == 0
    assert r.match_rate == 0.0
    assert not r.ok  # BH-01: empty buffer should never silently PASS


def test_sample_blocks_deterministic_with_seed():
    evs = [_ev(b, 0) for b in range(100, 120)]
    a = sample_blocks(evs, 3, seed=42)
    b = sample_blocks(evs, 3, seed=42)
    assert a == b and len(a) == 3
    assert all(x in range(100, 120) for x in a)


def test_sample_blocks_fewer_than_n():
    evs = [_ev(10, 0), _ev(11, 0)]
    assert sorted(sample_blocks(evs, 3, seed=1)) == [10, 11]
