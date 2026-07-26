"""Unit tests for tools.visualize (Story 2C.2)."""

from __future__ import annotations

import json

import pytest

from tools import visualize

pytest.importorskip("matplotlib")

from engine.graph.builder import ZERO_ADDRESS, build_graph  # noqa: E402

_TX = "0x" + "e" * 64


def _snapshot() -> dict:
    A, W, B, D = ("0x" + c * 40 for c in "acbd")
    P1, P2, P3 = ("0x" + str(i) * 40 for i in (1, 2, 3))

    def ev(block, proto, etype, pool, t0, t1, a0, a1):
        return {
            "block_number": block, "block_timestamp": "2023-10-24T12:00:00Z",
            "protocol": proto, "event_type": etype, "pool_address": pool,
            "token0": t0, "token1": t1, "amount0": a0, "amount1": a1,
            "tx_hash": _TX, "log_index": 0,
        }

    return build_graph([
        ev(1, "uniswap_v3", "swap", P1, A, W, "1000", "1"),
        ev(2, "uniswap_v3", "swap", P2, W, B, "1", "1000"),
        ev(3, "aave_v3", "borrow", P3, D, ZERO_ADDRESS, "500", "0"),
    ])


def _write_snapshot(tmp_path) -> str:
    snap = _snapshot()
    p = tmp_path / "snapshot.json"
    p.write_text(json.dumps(snap), encoding="utf-8")
    return str(p), snap


# ---------------------------------------------------------------------------
# AC1/AC2/AC3/AC6 — happy path
# ---------------------------------------------------------------------------

def test_creates_png_and_legend(tmp_path) -> None:
    input_path, snap = _write_snapshot(tmp_path)
    out = tmp_path / "graph.png"
    rc = visualize.main(["--input", input_path, "--out", str(out)])
    assert rc == 0
    legend = tmp_path / "graph.png.legend.json"
    assert out.is_file() and out.stat().st_size > 0
    assert legend.is_file()

    data = json.loads(legend.read_text(encoding="utf-8"))
    assert len(data["nodes"]) == len(snap["nodes"])
    assert data["feature_order"] == [
        "tvl_usd", "volume_24h_usd", "price_usd", "volatility", "connectivity",
    ]
    assert data["nodes"][0]["index"] == 0
    assert "id" in data["nodes"][0] and "type" in data["nodes"][0]


def test_custom_legend_path(tmp_path) -> None:
    input_path, _ = _write_snapshot(tmp_path)
    out = tmp_path / "g.png"
    legend = tmp_path / "custom.json"
    rc = visualize.main(
        ["--input", input_path, "--out", str(out), "--legend", str(legend)]
    )
    assert rc == 0
    assert legend.is_file()


# ---------------------------------------------------------------------------
# AC5 — robustness
# ---------------------------------------------------------------------------

def test_missing_input_returns_nonzero(tmp_path) -> None:
    rc = visualize.main(
        ["--input", str(tmp_path / "nope.json"), "--out", str(tmp_path / "o.png")]
    )
    assert rc == 2


def test_invalid_json_returns_nonzero(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    rc = visualize.main(["--input", str(bad), "--out", str(tmp_path / "o.png")])
    assert rc == 2


def test_invalid_snapshot_returns_nonzero(tmp_path) -> None:
    bad = tmp_path / "empty.json"
    bad.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")
    rc = visualize.main(["--input", str(bad), "--out", str(tmp_path / "o.png")])
    assert rc == 2
