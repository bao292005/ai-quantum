# Graph Snapshot Visualization (Story 2C.2)

`tools/visualize.py` renders a `GraphSnapshot` (schema 0.2) into a PNG and a JSON
legend so you can eyeball whether the graph topology and node features look sane
before trusting the MPS engine output.

## Usage

```bash
python -m tools.visualize --input snapshot.json --out graph.png
# → writes graph.png  and  graph.png.legend.json
# optional: --legend custom_legend.json
```

Exit codes: `0` success, `2` bad/missing input or invalid snapshot, `3`
matplotlib not installed (`pip install matplotlib`).

## What the PNG shows

The figure has two panels:

### 1. Adjacency heatmap (left)

- A colored `N × N` grid. **Row and column indices are node indices** — look them
  up in the legend (`nodes[i].id`).
- Cell `(i, j)` brightness = **edge weight** between node `i` and node `j`
  (viridis colormap: dark = 0, bright = high). Brighter = stronger liquidity /
  risk-propagation link.
- The matrix is **symmetric** (v1 treats edges as undirected), so the heatmap is
  mirrored across the diagonal.
- The **diagonal is dark (0)** unless a node has an explicit self-loop.
- A cell can exceed a single edge's `[0,1]` weight when multiple edges connect the
  same pair (weights accumulate).

### 2. Node feature bar chart (right)

- For each node index (x-axis), five bars show its features **min-max normalized
  per feature** (so features on very different scales are visually comparable).
- Feature order (locked by Story 2R.1): `tvl_usd`, `volume_24h_usd`, `price_usd`,
  `volatility`, `connectivity`.
- `connectivity` is already in `[0, 1]` (node degree / (N−1)); the others are
  normalized only for display.

## JSON legend

```json
{
  "nodes": [{"index": 0, "id": "protocol:uniswap_v3", "type": "protocol"}, ...],
  "feature_order": ["tvl_usd", "volume_24h_usd", "price_usd", "volatility", "connectivity"],
  "axes": {
    "heatmap": "symmetric adjacency weight (row/col = node index)",
    "barchart": "per-node features (minmax-normalized per feature)"
  }
}
```

Use `nodes[i].id` to translate a heatmap/bar index back to the real
protocol/pool/token identifier.

## How to read it quickly

- **Bright off-diagonal block** → a tightly-coupled cluster of pools/tokens (a
  potential contagion channel).
- **A row/column that is mostly dark** → an isolated node (low `connectivity`).
- **Feature bars all near zero for `tvl_usd`/`price_usd`/`volatility`** → expected
  in v1: those features are `0.0` placeholders pending reserve/price sourcing
  (see `research/feature_catalog.md`, Story 2R.1).
