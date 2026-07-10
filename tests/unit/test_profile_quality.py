"""Unit tests for the data-quality profiler core (Story 1E.3)."""

from tools.profile_quality import profile, render_html


def _ev(block, ts, proto="uniswap_v3", et="swap") -> dict:
    return {
        "block_number": block,
        "block_timestamp": ts,
        "protocol": proto,
        "event_type": et,
        "amount0": "1",
        "amount1": "0",
    }


def test_counts():
    evs = [
        _ev(1, "2022-05-06T14:00:00Z"),
        _ev(1, "2022-05-06T14:00:00Z", et="mint"),
        _ev(2, "2022-05-06T14:00:12Z", proto="aave_v3", et="borrow"),
    ]
    p = profile(evs)
    assert p.total_events == 3
    assert p.per_protocol == {"uniswap_v3": 2, "aave_v3": 1}
    assert p.per_event_type["swap"] == 1
    assert p.per_event_type["borrow"] == 1
    assert p.n_blocks == 2
    assert p.block_range == (1, 2)


def test_gap_over_30():
    evs = [
        _ev(1, "2022-05-06T14:00:00Z"),
        _ev(2, "2022-05-06T14:00:12Z"),  # +12s
        _ev(3, "2022-05-06T14:00:57Z"),  # +45s
    ]
    p = profile(evs)
    assert len(p.timestamp_gaps) == 2
    assert len(p.gaps_over_30s) == 1
    assert p.gaps_over_30s[0][:2] == (2, 3)
    assert p.gaps_over_30s[0][2] == 45.0


def test_drop_rate_with_blocks_seen():
    evs = [_ev(10, "2022-05-06T14:00:00Z"), _ev(12, "2022-05-06T14:00:24Z")]
    assert profile(evs, blocks_seen=[10, 11, 12]).block_drop_rate == 0.0
    p2 = profile(evs, blocks_seen=[10, 12])  # block 11 missing → 1/3
    assert round(p2.block_drop_rate, 3) == round(1 / 3, 3)


def test_drop_rate_from_coverage():
    evs = [_ev(10, "2022-05-06T14:00:00Z"), _ev(12, "2022-05-06T14:00:24Z")]
    # No blocks_seen: derive from event coverage (2 blocks over span 3).
    assert round(profile(evs).block_drop_rate, 3) == round(1 / 3, 3)


def test_empty():
    p = profile([])
    assert p.total_events == 0 and p.block_drop_rate == 0.0 and p.gaps_over_30s == []


def test_render_html_tables():
    p = profile([_ev(1, "2022-05-06T14:00:00Z")])
    html = render_html(p, charts=False)
    assert "<html" in html.lower()
    assert "uniswap_v3" in html
    assert "gap" in html.lower()


def test_render_html_flags_gap():
    evs = [_ev(1, "2022-05-06T14:00:00Z"), _ev(2, "2022-05-06T14:00:57Z")]
    html = render_html(profile(evs), charts=False)
    assert "30s" in html or "&gt; 30" in html
    assert "57s" in html  # the 57s gap is surfaced


def test_render_html_charts():
    evs = [_ev(1, "2022-05-06T14:00:00Z"), _ev(2, "2022-05-06T14:00:57Z")]
    html = render_html(profile(evs))  # charts=True
    assert "data:image/png;base64" in html
