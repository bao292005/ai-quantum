---
baseline_commit: a56e3f6
type: build
---

# Story 2C.2: Heatmap Visualization

Status: review

## Story

As a **Quant**,
I want **script vẽ adjacency heatmap + node feature bar chart từ một `GraphSnapshot`, xuất PNG + JSON legend**,
so that **mắt thường xác nhận được đồ hình/feature có hợp lý không trước khi tin vào MPS output**.

## Acceptance Criteria

1. **AC1 — CLI:** `python -m tools.visualize --input=<snapshot.json> --out=<graph.png>` chạy được, đọc GraphSnapshot JSON (schema 0.2), tạo file **PNG** tại `--out` và file **JSON legend** cạnh nó (mặc định `<out>.legend.json` hoặc `--legend`).

2. **AC2 — Nội dung PNG:** PNG chứa (a) **adjacency heatmap** (`imshow` ma trận `(N,N)` từ 2B.1, có colorbar) và (b) **node feature bar chart** (5 feature per node, 2B.2; normalize để so sánh trực quan).

3. **AC3 — JSON legend:** legend map `node index → {id, type}` (thứ tự khớp hàng/cột heatmap), kèm `feature_order` (2R.1) và mô tả ngắn mỗi trục.

4. **AC4 — README/hướng dẫn:** `docs/visualization.md` giải thích cách đọc heatmap (trục = node index → tra legend; ô sáng = liên kết mạnh; đối xứng) và bar chart.

5. **AC5 — Robustness:** input thiếu/không hợp lệ → thoát mã lỗi ≠ 0 + message rõ; validate snapshot qua `validate_graph_snapshot`. matplotlib thiếu → message rõ ràng.

6. **AC6 — Tests:** `tests/unit/test_visualize.py`: chạy trên snapshot mẫu (từ `build_graph`) → PNG + JSON legend được tạo, non-empty; legend có đúng N node + feature_order; input không tồn tại → exit code ≠ 0.

## Tasks / Subtasks

- [x] **Task 1 — `tools/visualize.py`** (AC1, AC2, AC3)
  - [x] argparse `--input`, `--out`, `--legend?`
  - [x] load + `validate_graph_snapshot`; `adjacency_tensor` + `feature_tensor`
  - [x] matplotlib Agg: subplot heatmap + bar chart; savefig PNG
  - [x] ghi JSON legend
- [x] **Task 2 — `docs/visualization.md`** (AC4)
  - [x] Hướng dẫn interpret heatmap + bar chart
- [x] **Task 3 — Tests** (AC5, AC6)
  - [x] `tests/unit/test_visualize.py`: happy path tạo file; bad input → exit ≠ 0

## Dev Notes

**Loại story:** `[BUILD]` — tool trực quan hoá, không nằm trên hot path runtime.

**Phụ thuộc (DONE):** `adjacency_tensor` (2B.1), `feature_tensor` + `FEATURE_ORDER` (2B.2), `normalize` (2B.3, để bar chart so sánh được), `validate_graph_snapshot` (core.schemas), `build_graph` (2A.3, để test tạo snapshot). matplotlib đã có trong `[project.optional-dependencies] dev` (Story 1E.3). `tools*` đã trong `packages.find include`.

**matplotlib headless:** dùng `matplotlib.use("Agg")` trước khi `import pyplot` (không cần display). Pattern giống Story 1E.3 (`render_html`).

**PNG layout gợi ý:** `fig, (ax1, ax2) = plt.subplots(1, 2)`. ax1 = `imshow(adjacency)` + colorbar; ax2 = grouped/stacked bar của feature (normalize minmax per feature để cột dễ nhìn — connectivity vốn [0,1]). Tick label = node index.

**JSON legend schema (đơn giản):**
```json
{"nodes":[{"index":0,"id":"protocol:uniswap_v3","type":"protocol"}, ...],
 "feature_order":["tvl_usd","volume_24h_usd","price_usd","volatility","connectivity"],
 "axes":{"heatmap":"symmetric adjacency weight (row/col = node index)",
         "barchart":"per-node features (minmax-normalized)"}}
```

**Robustness:** file input không tồn tại → `FileNotFoundError`/exit 2; JSON hỏng → exit ≠0; snapshot fail schema → propagate ValidationError. matplotlib ImportError → message "install matplotlib".

**Testing:** pytest sync. Gọi `tools.visualize.main([...])` trực tiếp (trả int exit code) + `tmp_path`.

### Project Structure Notes

```
tools/
  visualize.py            ← NEW
docs/
  visualization.md        ← NEW
tests/unit/
  test_visualize.py       ← NEW
```

### References

- Adjacency/feature: `engine/tensor/adjacency.py` (2B.1), `engine/tensor/features.py` (2B.2)
- Normalize: `engine/tensor/normalize.py` (2B.3)
- Validator: `core/schemas/__init__.py`
- matplotlib pattern: `tools/` Story 1E.3 report
- Epic 2 Track 2C: `_bmad-output/epics.md#Story 2C.2`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (bmad-dev-story)

### Debug Log References

`tests/unit/test_visualize.py` 5 passed. Full suite **449 passed, 1 skipped** (mock WSS), 0 regressions.

### Completion Notes List

- **AC1:** `tools/visualize.py` CLI (`python -m tools.visualize --input --out [--legend]`).
  Loads snapshot JSON, validates via `validate_graph_snapshot`, writes PNG + JSON legend
  (default `<out>.legend.json`).
- **AC2:** PNG = 2 panels — adjacency heatmap (`imshow` viridis + colorbar, from 2B.1) and
  per-node feature bar chart (5 features, minmax-normalized via 2B.3 for comparability).
  Headless `matplotlib.use("Agg")`.
- **AC3:** JSON legend maps `index → {id, type}` (row/col order), `feature_order` (2R.1),
  axis descriptions.
- **AC4:** `docs/visualization.md` — how to read heatmap (index→legend, bright=strong link,
  symmetric, dark diagonal) + bar chart + v1 placeholder-feature note.
- **AC5:** missing input → exit 2; invalid JSON → exit 2; invalid snapshot → exit 2;
  matplotlib missing → exit 3 with install hint.
- **AC6:** 5 tests — PNG+legend created & non-empty, legend content (N nodes + feature_order),
  custom legend path, missing input, invalid JSON, invalid snapshot → non-zero.

### Change Log

| Date | Change |
|---|---|
| 2026-07-26 | Added `tools/visualize.py` (adjacency heatmap + feature bar chart PNG + JSON legend CLI), `docs/visualization.md`, 5 tests. Story file created + status → review. |

### File List

- `tools/visualize.py` (NEW)
- `docs/visualization.md` (NEW)
- `tests/unit/test_visualize.py` (NEW)
- `_bmad-output/implementation-artifacts/2C-2-heatmap-visualization.md` (NEW story spec)
