"""Graph snapshot visualizer (Story 2C.2).

Renders a ``GraphSnapshot`` as an adjacency heatmap plus a per-node feature bar
chart (PNG), and writes a JSON legend mapping node indices to ids/types.

Usage::

    python -m tools.visualize --input snapshot.json --out graph.png
    # writes graph.png and graph.png.legend.json (or --legend PATH)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from core.schemas import validate_graph_snapshot
from engine.tensor.adjacency import adjacency_tensor
from engine.tensor.features import FEATURE_ORDER, feature_tensor
from engine.tensor.normalize import normalize


def _load_snapshot(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _build_legend(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "nodes": [
            {"index": i, "id": node["id"], "type": node["type"]}
            for i, node in enumerate(snapshot["nodes"])
        ],
        "feature_order": list(FEATURE_ORDER),
        "axes": {
            "heatmap": "symmetric adjacency weight (row/col = node index)",
            "barchart": "per-node features (minmax-normalized per feature)",
        },
    }


def render(
    snapshot: dict[str, Any], out_png: Path, legend_path: Path | None = None
) -> tuple[Path, Path]:
    """Render ``snapshot`` to ``out_png`` and write the JSON legend.

    Returns the ``(png_path, legend_path)`` written.

    Raises:
        ImportError: if matplotlib is not installed.
    """
    try:
        import matplotlib
    except ImportError as exc:  # pragma: no cover - exercised via message
        raise ImportError(
            "matplotlib is required for visualization; install it "
            "(e.g. `pip install matplotlib`)."
        ) from exc

    matplotlib.use("Agg")  # headless
    import matplotlib.pyplot as plt

    adj = adjacency_tensor(snapshot).numpy()
    feats = feature_tensor(snapshot)
    feats_norm, _ = normalize(feats, method="minmax")
    feats_norm = feats_norm.numpy()
    n = adj.shape[0]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    im = ax1.imshow(adj, cmap="viridis", aspect="auto")
    ax1.set_title("Adjacency heatmap")
    ax1.set_xlabel("node index")
    ax1.set_ylabel("node index")
    fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04, label="edge weight")

    x = range(n)
    n_feat = len(FEATURE_ORDER)
    bar_w = 0.8 / n_feat
    for f, name in enumerate(FEATURE_ORDER):
        offsets = [xi + (f - n_feat / 2) * bar_w + bar_w / 2 for xi in x]
        ax2.bar(offsets, feats_norm[:, f], width=bar_w, label=name)
    ax2.set_title("Node features (minmax-normalized)")
    ax2.set_xlabel("node index")
    ax2.set_ylabel("normalized value")
    ax2.set_xticks(list(x))
    ax2.legend(fontsize=8, ncol=2)

    fig.tight_layout()
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=120)
    plt.close(fig)

    if legend_path is None:
        legend_path = out_png.with_suffix(out_png.suffix + ".legend.json")
    legend_path = Path(legend_path)
    with legend_path.open("w", encoding="utf-8") as fh:
        json.dump(_build_legend(snapshot), fh, indent=2)

    return out_png, legend_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.visualize", description=__doc__)
    parser.add_argument("--input", required=True, help="Path to GraphSnapshot JSON")
    parser.add_argument("--out", required=True, help="Output PNG path")
    parser.add_argument("--legend", default=None, help="Output JSON legend path")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"error: input not found: {input_path}", file=sys.stderr)
        return 2

    try:
        snapshot = _load_snapshot(input_path)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {input_path}: {exc}", file=sys.stderr)
        return 2

    try:
        validate_graph_snapshot(snapshot)
    except Exception as exc:  # ValidationError / ValueError
        print(f"error: invalid GraphSnapshot: {exc}", file=sys.stderr)
        return 2

    try:
        png, legend = render(
            snapshot, Path(args.out), Path(args.legend) if args.legend else None
        )
    except ImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    print(f"wrote {png} and {legend}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
